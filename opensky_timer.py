import json
import logging
import os
import time
import traceback

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from clickhouse_driver import Client
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Load environment variables from .env
load_dotenv()

LOG_FILE = "opensky_ingest.log"
API_URL = "https://opensky-network.org/api/states/all"

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

# Connect to ClickHouse
client = Client(
    host=os.getenv("CLICKHOUSE_HOST"),
    port=int(os.getenv("CLICKHOUSE_PORT_NATIVE", "9000")),
    user=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
    database=DB_NAME,
)


def _to_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def ensure_schema():
    client.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {DB_NAME}.opensky
    (
        time_position UInt32,
        icao24 String,
        callsign String,
        origin_country String,
        last_contact UInt32,
        longitude Nullable(Float64),
        latitude Nullable(Float64),
        baro_altitude Nullable(Float64),
        on_ground UInt8,
        velocity Nullable(Float64),
        true_track Nullable(Float64),
        vertical_rate Nullable(Float64),
        sensors_json String,
        geo_altitude Nullable(Float64),
        squawk Nullable(String),
        spi UInt8,
        position_source Nullable(UInt8),
        snapshot_time UInt32,
        ingested_at DateTime DEFAULT now(),
        INDEX idx_icao24_bloom icao24 TYPE bloom_filter(0.01) GRANULARITY 64
    )
    ENGINE = MergeTree
    PARTITION BY toYYYYMM(toDateTime(time_position))
    PRIMARY KEY (time_position, icao24)
    ORDER BY (time_position, icao24)
    SETTINGS index_granularity = 8192
    """
    client.execute(create_table_sql)


def normalize_state(state, snapshot_time):
    if not isinstance(state, (list, tuple)) or len(state) < 17:
        return None

    icao24 = _clean_text(state[0]).lower()
    time_position = _to_int(state[3])

    # Primary key cannot be null/empty
    if not icao24 or time_position is None:
        return None

    callsign = _clean_text(state[1])
    origin_country = _clean_text(state[2])
    last_contact = _to_int(state[4])
    if last_contact is None:
        last_contact = time_position

    sensors = state[12]
    if sensors is None:
        sensors_json = ""
    else:
        sensors_json = json.dumps(sensors, ensure_ascii=False)

    position_source = _to_int(state[16])
    if position_source is not None and position_source < 0:
        position_source = None

    row = (
        int(time_position),
        icao24,
        callsign,
        origin_country,
        int(last_contact),
        _to_float(state[5]),
        _to_float(state[6]),
        _to_float(state[7]),
        1 if bool(state[8]) else 0,
        _to_float(state[9]),
        _to_float(state[10]),
        _to_float(state[11]),
        sensors_json,
        _to_float(state[13]),
        _clean_text(state[14]) or None,
        1 if bool(state[15]) else 0,
        position_source,
        int(snapshot_time),
    )
    return row


def fetch_and_update():
    try:
        ensure_schema()

        auth = None
        opensky_user = os.getenv("OPENSKY_USERNAME")
        opensky_password = os.getenv("OPENSKY_PASSWORD")
        if opensky_user and opensky_password:
            auth = (opensky_user, opensky_password)

        logging.info("Fetching ADS-B state vectors from OpenSky...")
        response = requests.get(API_URL, timeout=120, auth=auth)
        response.raise_for_status()
        payload = response.json()

        snapshot_time = _to_int(payload.get("time")) or int(time.time())
        states = payload.get("states", [])
        if not isinstance(states, list):
            logging.warning("Unexpected OpenSky response: 'states' is not a list.")
            return

        rows = []
        dropped = 0
        for state in states:
            normalized = normalize_state(state, snapshot_time)
            if normalized is None:
                dropped += 1
                continue
            rows.append(normalized)

        if not rows:
            logging.warning("No valid ADS-B rows to insert. dropped=%s", dropped)
            return

        insert_sql = f"""
        INSERT INTO {DB_NAME}.opensky
        (
            time_position, icao24, callsign, origin_country, last_contact,
            longitude, latitude, baro_altitude, on_ground, velocity,
            true_track, vertical_rate, sensors_json, geo_altitude, squawk,
            spi, position_source, snapshot_time
        )
        VALUES
        """
        client.execute(insert_sql, rows, types_check=True)

        logging.info(
            "Inserted %s rows into %s.opensky (dropped=%s, snapshot_time=%s).",
            len(rows),
            DB_NAME,
            dropped,
            snapshot_time,
        )
    except Exception as error:
        logging.error("OpenSky ingest failed: %s", error)
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    fetch_and_update()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        fetch_and_update,
        "interval",
        hours=1,
        id="opensky_hourly_sync",
        max_instances=1,
        coalesce=True,
    )
    logging.info("OpenSky scheduler started. Next sync runs every 1 hour.")
    scheduler.start()
