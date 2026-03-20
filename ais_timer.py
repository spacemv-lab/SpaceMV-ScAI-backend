import asyncio
import json
import logging
import os
import time
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple

import websockets
from apscheduler.schedulers.blocking import BlockingScheduler
from clickhouse_driver import Client
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

LOG_FILE = "ais_ingest.log"
AIS_WS_URL = os.getenv("AIS_WS_URL", "wss://stream.aisstream.io/v0/stream")
AIS_BATCH_MINUTES = int(os.getenv("AIS_BATCH_MINUTES", "3"))
AIS_API_KEY = os.getenv("AISSTREAM_API_KEY", "")

# Ensure log directory exists
os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)

# Log configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=1,
            encoding="utf-8",
        ),
    ],
)

DB_NAME = os.getenv("CLICKHOUSE_DATABASE", "xingzuo")
TABLE_NAME = "AIS"

# Connect to ClickHouse
client = Client(
    host=os.getenv("CLICKHOUSE_HOST"),
    port=int(os.getenv("CLICKHOUSE_PORT_NATIVE", "9000")),
    user=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
    database=DB_NAME,
)


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool_u8(value: Any) -> int:
    return 1 if bool(value) else 0


def _normalize_lat_lon(lat: Optional[float], lon: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if lat is not None and (lat < -90 or lat > 90):
        lat = None
    if lon is not None and (lon < -180 or lon > 180):
        lon = None
    return lat, lon


def ensure_schema() -> None:
    client.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {DB_NAME}.`{TABLE_NAME}`
    (
        user_id UInt32,
        message_id Nullable(UInt8),
        navigational_status Nullable(UInt8),
        longitude Nullable(Float64),
        latitude Nullable(Float64),
        sog Nullable(Float64),
        cog Nullable(Float64),
        true_heading Nullable(UInt16),
        rate_of_turn Nullable(Int16),
        position_accuracy UInt8,
        timestamp_second Nullable(UInt8),
        valid UInt8,
        communication_state Nullable(UInt32),
        raim UInt8,
        repeat_indicator Nullable(UInt8),
        spare Nullable(UInt8),
        special_manoeuvre_indicator Nullable(UInt8),
        receive_time DateTime,
        batch_time UInt32,
        raw_json String,
        ingested_at DateTime DEFAULT now()
    )
    ENGINE = MergeTree
    PARTITION BY toYYYYMM(receive_time)
    PRIMARY KEY (user_id, receive_time)
    ORDER BY (user_id, receive_time)
    SETTINGS index_granularity = 8192
    """
    client.execute(create_table_sql)


def _extract_position_payload(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    message_type = message.get("MessageType")
    if message_type not in {"PositionReport", "StandardClassBPositionReport"}:
        return None

    container = message.get("Message", {})
    if not isinstance(container, dict):
        return None

    payload = container.get(message_type)
    if isinstance(payload, dict):
        return payload

    # Some feeds may still use PositionReport key even if MessageType differs.
    fallback = container.get("PositionReport")
    if isinstance(fallback, dict):
        return fallback

    return None


def normalize_ais_record(payload: Dict[str, Any], receive_dt: datetime, batch_ts: int) -> Optional[Tuple[Any, ...]]:
    user_id = _to_int(payload.get("UserID"))
    if user_id is None or user_id <= 0:
        return None

    latitude = _to_float(payload.get("Latitude"))
    longitude = _to_float(payload.get("Longitude"))
    latitude, longitude = _normalize_lat_lon(latitude, longitude)

    row = (
        int(user_id),
        _to_int(payload.get("MessageID")),
        _to_int(payload.get("NavigationalStatus")),
        longitude,
        latitude,
        _to_float(payload.get("Sog")),
        _to_float(payload.get("Cog")),
        _to_int(payload.get("TrueHeading")),
        _to_int(payload.get("RateOfTurn")),
        _to_bool_u8(payload.get("PositionAccuracy")),
        _to_int(payload.get("Timestamp")),
        _to_bool_u8(payload.get("Valid")),
        _to_int(payload.get("CommunicationState")),
        _to_bool_u8(payload.get("Raim")),
        _to_int(payload.get("RepeatIndicator")),
        _to_int(payload.get("Spare")),
        _to_int(payload.get("SpecialManoeuvreIndicator")),
        receive_dt.replace(tzinfo=None),
        int(batch_ts),
        json.dumps(payload, ensure_ascii=False),
    )
    return row


async def collect_ais_batch(duration_seconds: int, batch_ts: int) -> Tuple[List[Tuple[Any, ...]], int, int]:
    if not AIS_API_KEY:
        raise RuntimeError("AISSTREAM_API_KEY is empty. Please configure it in .env.")

    subscribe_message = {
        "APIKey": AIS_API_KEY,
        "BoundingBoxes": [[[-90, -180], [90, 180]]],
        "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport"],
    }

    latest_by_user: Dict[int, Tuple[Any, ...]] = {}
    total_messages = 0
    dropped_messages = 0

    deadline = time.monotonic() + duration_seconds

    async with websockets.connect(
        AIS_WS_URL,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=10,
        max_size=None,
    ) as websocket:
        await websocket.send(json.dumps(subscribe_message))

        while time.monotonic() < deadline:
            remaining = max(0.1, min(1.0, deadline - time.monotonic()))
            try:
                message_json = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                logging.warning("AIS WebSocket closed before batch duration ended.")
                break

            total_messages += 1

            try:
                message = json.loads(message_json)
            except json.JSONDecodeError:
                dropped_messages += 1
                continue

            payload = _extract_position_payload(message)
            if payload is None:
                dropped_messages += 1
                continue

            receive_dt = datetime.now(timezone.utc)
            normalized = normalize_ais_record(payload, receive_dt, batch_ts)
            if normalized is None:
                dropped_messages += 1
                continue

            user_id = normalized[0]
            latest_by_user[user_id] = normalized

    return list(latest_by_user.values()), total_messages, dropped_messages


def fetch_and_update() -> None:
    try:
        ensure_schema()

        batch_ts = int(time.time())
        duration_seconds = max(1, AIS_BATCH_MINUTES * 60)

        logging.info(
            "Starting AIS batch ingest: receive %s minutes from websocket.",
            AIS_BATCH_MINUTES,
        )
        rows, total_messages, dropped_messages = asyncio.run(
            collect_ais_batch(duration_seconds=duration_seconds, batch_ts=batch_ts)
        )

        if not rows:
            logging.warning(
                "No valid AIS rows to insert. raw_messages=%s dropped=%s",
                total_messages,
                dropped_messages,
            )
            return

        insert_sql = f"""
        INSERT INTO {DB_NAME}.`{TABLE_NAME}`
        (
            user_id, message_id, navigational_status, longitude, latitude,
            sog, cog, true_heading, rate_of_turn, position_accuracy,
            timestamp_second, valid, communication_state, raim, repeat_indicator,
            spare, special_manoeuvre_indicator, receive_time, batch_time, raw_json
        )
        VALUES
        """
        client.execute(insert_sql, rows, types_check=True)

        logging.info(
            "Inserted %s AIS rows into %s.%s (raw_messages=%s dropped=%s batch_time=%s).",
            len(rows),
            DB_NAME,
            TABLE_NAME,
            total_messages,
            dropped_messages,
            batch_ts,
        )
    except Exception as error:
        logging.error("AIS ingest failed: %s", error)
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    fetch_and_update()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        fetch_and_update,
        "interval",
        hours=1,
        id="ais_hourly_sync",
        max_instances=1,
        coalesce=True,
    )
    logging.info("AIS scheduler started. Every 1 hour it collects 3 minutes from websocket.")
    scheduler.start()
