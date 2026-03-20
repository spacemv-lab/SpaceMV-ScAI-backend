import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from clickhouse_driver import Client
from dotenv import load_dotenv

st.set_page_config(
    page_title="AIS",
    page_icon="🚢",
    layout="wide",
)

st.markdown(
    """
<style>
    .stApp { background-color: #f6f8fb; }
    .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 10px;
    }
</style>
""",
    unsafe_allow_html=True,
)

FIELD_META: Dict[str, Dict[str, str]] = {
    "user_id": {"label": "船舶ID(MMSI)", "note": "船舶唯一识别码。"},
    "message_id": {"label": "消息类型ID", "note": "AIS 协议消息类型。"},
    "navigational_status": {"label": "航行状态", "note": "0=引擎航行中，1=锚泊，3=操纵受限，5=靠泊，8=航行中但未受指令。"},
    "longitude": {"label": "经度", "note": "经度。"},
    "latitude": {"label": "纬度", "note": "纬度。"},
    "sog": {"label": "对地航速", "note": "SOG，单位节(knots)。"},
    "cog": {"label": "对地航向", "note": "COG，单位度，正北为0°。"},
    "true_heading": {"label": "真实船艏向", "note": "船头罗盘朝向，单位度。"},
    "rate_of_turn": {"label": "转向率", "note": "ROT，正值右转，负值左转。"},
    "position_accuracy": {"label": "定位精度", "note": "-"},
    "timestamp_second": {"label": "报告秒", "note": "报告生成的秒数 (0-59)，但不是 Unix 时间戳。"},
    "valid": {"label": "数据有效", "note": "1=通过校验，0=可能损坏。"},
    "communication_state": {"label": "通信状态码", "note": "SOTDMA/ITDMA 底层通信状态。"},
    "raim": {"label": "RAIM", "note": "接收机完好性监测。"},
    "repeat_indicator": {"label": "转发次数", "note": "0=原始消息，>0 表示被转发。"},
    "spare": {"label": "备用位", "note": "协议保留字段。"},
    "special_manoeuvre_indicator": {"label": "特殊操纵指示", "note": "特殊航路/限制操作标记。"},
    "receive_time": {"label": "接收时间", "note": "服务器接收到该条 AIS 的 UTC 时间。"},
    "batch_time": {"label": "批次时间", "note": "当前采集批次起始时间（Unix 秒，UTC）。"},
}

TABLE_COLUMNS = [
    "user_id",
    "message_id",
    "navigational_status",
    "longitude",
    "latitude",
    "sog",
    "cog",
    "true_heading",
    "rate_of_turn",
    "position_accuracy",
    "timestamp_second",
    "valid",
    "communication_state",
    "raim",
    "repeat_indicator",
    "spare",
    "special_manoeuvre_indicator",
    "receive_time",
    "batch_time",
]


def load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


@st.cache_resource
def get_clickhouse_client() -> Client:
    load_env()
    host = os.getenv("CLICKHOUSE_HOST")
    port = os.getenv("CLICKHOUSE_PORT_NATIVE", "9000")
    user = os.getenv("CLICKHOUSE_USER")
    password = os.getenv("CLICKHOUSE_PASSWORD")
    database = os.getenv("CLICKHOUSE_DATABASE", "xingzuo")

    if not host:
        raise RuntimeError("未配置 CLICKHOUSE_HOST")

    return Client(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database,
    )


def to_utc_str(ts: Optional[int]) -> str:
    if ts is None:
        return "-"
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_database_name() -> str:
    return os.getenv("CLICKHOUSE_DATABASE", "xingzuo")


def table_exists(client: Client, db_name: str) -> bool:
    result = client.execute(f"EXISTS TABLE {db_name}.`AIS`")
    return bool(result and result[0] and result[0][0] == 1)


def query_time_stats(client: Client, db_name: str) -> Dict[str, int]:
    sql = f"""
    SELECT
        min(batch_time) AS min_batch,
        max(batch_time) AS max_batch,
        countDistinct(batch_time) AS batch_count,
        count() AS row_count
    FROM {db_name}.`AIS`
    """
    row = client.execute(sql)[0]
    return {
        "min_batch": int(row[0]) if row[0] is not None else 0,
        "max_batch": int(row[1]) if row[1] is not None else 0,
        "batch_count": int(row[2]) if row[2] is not None else 0,
        "row_count": int(row[3]) if row[3] is not None else 0,
    }


def query_nearest_batch(client: Client, db_name: str, target_ts: int) -> Optional[int]:
    sql = f"""
    SELECT batch_time
    FROM {db_name}.`AIS`
    GROUP BY batch_time
    ORDER BY abs(batch_time - %(target_ts)s)
    LIMIT 1
    """
    result = client.execute(sql, {"target_ts": target_ts})
    return int(result[0][0]) if result else None


def query_batch_rows(client: Client, db_name: str, batch_ts: int) -> pd.DataFrame:
    sql = f"""
    SELECT
        {", ".join(TABLE_COLUMNS)}
    FROM
    (
        SELECT *
        FROM {db_name}.`AIS`
        WHERE batch_time = %(batch_ts)s
        ORDER BY receive_time DESC
        LIMIT 1 BY user_id
    )
    WHERE longitude IS NOT NULL AND latitude IS NOT NULL
    ORDER BY user_id
    """
    rows = client.execute(sql, {"batch_ts": batch_ts})
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def query_batch_ship_count(client: Client, db_name: str, batch_ts: int) -> int:
    sql = f"""
    SELECT countDistinct(user_id)
    FROM {db_name}.`AIS`
    WHERE batch_time = %(batch_ts)s
    """
    return int(client.execute(sql, {"batch_ts": batch_ts})[0][0])


def to_unix_utc(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def format_value(field: str, value: Any) -> str:
    if value is None:
        return "-"
    if field == "receive_time":
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return str(value)
    if field == "batch_time":
        return f"{value} ({to_utc_str(int(value))} UTC)"
    if field in ("position_accuracy", "valid", "raim"):
        return "是" if int(value) == 1 else "否"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def build_detail_table(record: pd.Series) -> pd.DataFrame:
    rows: List[Dict[str, str]] = []
    for field in TABLE_COLUMNS:
        meta = FIELD_META[field]
        rows.append(
            {
                "字段": f"{meta['label']} ({field})",
                "值": format_value(field, record[field]),
                "备注": meta["note"],
            }
        )
    return pd.DataFrame(rows)


def _point_value(point: Any, key: str) -> Any:
    if isinstance(point, dict):
        if key in point:
            return point.get(key)
        # Compatibility with camelCase keys from some Plotly event payloads.
        if key == "point_index":
            return point.get("pointIndex")
        if key == "point_number":
            return point.get("pointNumber")
    return getattr(point, key, None)


def extract_selected_user(chart_event: Any, df: pd.DataFrame) -> Optional[int]:
    if chart_event is None:
        return None

    points: Any = None
    if isinstance(chart_event, dict):
        points = chart_event.get("selection", {}).get("points", [])
    else:
        selection = getattr(chart_event, "selection", None)
        points = getattr(selection, "points", None)

    if not points:
        return None

    first_point = points[0]
    custom = _point_value(first_point, "customdata")

    if isinstance(custom, (list, tuple)) and custom:
        user_id = custom[0]
    else:
        user_id = custom

    try:
        return int(user_id)
    except (TypeError, ValueError):
        pass

    # Fallback: resolve by clicked point index when customdata is unavailable.
    point_idx = _point_value(first_point, "point_index")
    if point_idx is None:
        point_idx = _point_value(first_point, "point_number")
    try:
        idx = int(point_idx)
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= len(df):
        return None
    try:
        return int(df.iloc[idx]["user_id"])
    except (TypeError, ValueError, KeyError):
        return None


def render_map(
    df: pd.DataFrame,
    title: str,
    basemap_mode: str,
    tile_url: str,
    tile_zoom: float,
) -> Any:
    custom_data = df[["user_id", "sog", "cog", "navigational_status"]].values
    hover_template = (
        "<b>MMSI: %{customdata[0]}</b><br>"
        "SOG: %{customdata[1]} kn<br>"
        "COG: %{customdata[2]} °<br>"
        "航行状态: %{customdata[3]}<br>"
        "经度: %{lon:.3f}<br>"
        "纬度: %{lat:.3f}<extra></extra>"
    )

    if basemap_mode == "offline_vector":
        fig = go.Figure(
            go.Scattergeo(
                lon=df["longitude"],
                lat=df["latitude"],
                mode="markers",
                customdata=custom_data,
                marker=dict(size=5, color="#0a9396", opacity=0.8),
                selected=dict(marker=dict(size=9, color="#ee9b00")),
                unselected=dict(marker=dict(opacity=0.55)),
                hovertemplate=hover_template,
                name="船舶位置",
            )
        )
        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            margin={"l": 0, "r": 0, "t": 45, "b": 0},
            height=760,
            showlegend=False,
            geo=dict(
                projection_type="natural earth",
                showland=True,
                landcolor="#f8fafc",
                showocean=True,
                oceancolor="#dbeafe",
                showcountries=True,
                countrycolor="#94a3b8",
                coastlinecolor="#64748b",
                showlakes=True,
                lakecolor="#dbeafe",
                showframe=False,
                lonaxis=dict(showgrid=True, gridcolor="#e2e8f0", dtick=30),
                lataxis=dict(showgrid=True, gridcolor="#e2e8f0", dtick=30),
            ),
            uirevision="ais-map",
        )
    else:
        center_lat = float(df["latitude"].mean()) if not df.empty else 0.0
        center_lon = float(df["longitude"].mean()) if not df.empty else 0.0
        fig = go.Figure(
            go.Scattermap(
                lon=df["longitude"],
                lat=df["latitude"],
                mode="markers",
                customdata=custom_data,
                marker=dict(size=5, color="#0a9396", opacity=0.8),
                selected=dict(marker=dict(size=9, color="#ee9b00")),
                unselected=dict(marker=dict(opacity=0.55)),
                hovertemplate=hover_template,
                name="船舶位置",
            )
        )
        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            margin={"l": 0, "r": 0, "t": 45, "b": 0},
            height=760,
            showlegend=False,
            map=dict(
                style="white-bg",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=tile_zoom,
                layers=[
                    {
                        "below": "traces",
                        "sourcetype": "raster",
                        "source": [tile_url],
                    }
                ],
            ),
            uirevision="ais-map",
        )

    try:
        return st.plotly_chart(
            fig,
            width="stretch",
            on_select="rerun",
            selection_mode="points",
            config={"scrollZoom": True},
        )
    except TypeError:
        st.caption("当前 Streamlit 版本不支持图上点选回传，已回退为纯展示模式。")
        st.plotly_chart(fig, width="stretch", config={"scrollZoom": True})
        return None


st.title("AIS 全球船舶轨迹快照可视化")

try:
    client = get_clickhouse_client()
    db_name = get_database_name()
except Exception as err:
    st.error(f"ClickHouse 连接失败: {err}")
    st.stop()

if not table_exists(client, db_name):
    st.error(f"表 {db_name}.AIS 不存在。请先运行 ais_timer.py 进行数据采集。")
    st.stop()

stats = query_time_stats(client, db_name)
min_batch = stats["min_batch"]
max_batch = stats["max_batch"]

if min_batch <= 0 or max_batch <= 0:
    st.warning("AIS 表暂无有效数据。")
    st.stop()

min_dt_utc = datetime.fromtimestamp(min_batch, tz=timezone.utc)
max_dt_utc = datetime.fromtimestamp(max_batch, tz=timezone.utc)

# Slider compatibility: use naive UTC datetime values for input widgets.
min_dt = min_dt_utc.replace(tzinfo=None)
max_dt = max_dt_utc.replace(tzinfo=None)

st.subheader("时间与范围")
c1, c2, c3, c4 = st.columns(4)
c1.metric("数据起始(UTC)", min_dt_utc.strftime("%Y-%m-%d %H:%M:%S"))
c2.metric("数据结束(UTC)", max_dt_utc.strftime("%Y-%m-%d %H:%M:%S"))
c3.metric("时间跨度", str(max_dt_utc - min_dt_utc).split(".")[0])
c4.metric("采集批次数", f"{stats['batch_count']:,}")

default_dt = max_dt
if "target_utc_dt_ais" not in st.session_state:
    st.session_state["target_utc_dt_ais"] = default_dt
else:
    cached_dt = st.session_state["target_utc_dt_ais"]
    if cached_dt < min_dt:
        st.session_state["target_utc_dt_ais"] = min_dt
    elif cached_dt > max_dt:
        st.session_state["target_utc_dt_ais"] = max_dt

if min_dt == max_dt:
    target_dt = min_dt
    st.info("当前数据库仅有一个批次时间点，时间选择已固定。")
else:
    target_dt = st.slider(
        "选择目标时间（UTC）",
        min_value=min_dt,
        max_value=max_dt,
        value=st.session_state["target_utc_dt_ais"],
        step=timedelta(minutes=1),
        format="YYYY-MM-DD HH:mm:ss",
    )
st.session_state["target_utc_dt_ais"] = target_dt

target_ts = to_unix_utc(target_dt)
nearest_batch = query_nearest_batch(client, db_name, target_ts)

if nearest_batch is None:
    st.warning("未找到可用批次。")
    st.stop()

ship_df = query_batch_rows(client, db_name, nearest_batch)
if ship_df.empty:
    st.warning("该批次没有可展示的船舶位置数据。")
    st.stop()

nearest_dt_str = to_utc_str(nearest_batch)
delta_seconds = abs(nearest_batch - target_ts)
ship_count = query_batch_ship_count(client, db_name, nearest_batch)

st.caption(
    f"已匹配最近批次: {nearest_dt_str} UTC，"
    f"与目标时间差 {delta_seconds} 秒，当前批次船舶数 {ship_count:,}。"
)

with st.sidebar:
    st.subheader("底图设置")
    basemap_mode_label = st.radio(
        "底图模式",
        options=["离线矢量", "本地瓦片"],
        index=0,
        help="本地瓦片模式需要先启动 visual_backend/tiles/cors_server.py。",
    )
    tile_url = st.text_input(
        "本地瓦片 URL",
        value="http://127.0.0.1:9999/gaode_tiles/{z}/{x}/{y}.png",
        disabled=basemap_mode_label != "本地瓦片",
    )
    tile_zoom = st.slider(
        "瓦片缩放",
        min_value=1.0,
        max_value=8.0,
        value=1.0,
        step=0.1,
        disabled=basemap_mode_label != "本地瓦片",
    )

basemap_mode = "offline_vector" if basemap_mode_label == "离线矢量" else "local_tiles"

map_col, info_col = st.columns([3.6, 1.4], gap="large")

with map_col:
    chart_title = f"全球矢量地图 | 批次时间: {nearest_dt_str} UTC | 船舶数: {len(ship_df):,}"
    chart_event = render_map(
        ship_df,
        chart_title,
        basemap_mode=basemap_mode,
        tile_url=tile_url,
        tile_zoom=tile_zoom,
    )
    selected_user = extract_selected_user(chart_event, ship_df)
    if selected_user:
        st.session_state["selected_user_id"] = selected_user

with info_col:
    st.subheader("目标属性")
    selected_user = st.session_state.get("selected_user_id")

    if selected_user and selected_user not in ship_df["user_id"].values:
        selected_user = None
        st.session_state["selected_user_id"] = None

    if not selected_user:
        st.info("请在地图中单击船舶点位。")

    options = [0] + ship_df["user_id"].tolist()
    chosen = st.selectbox(
        "或从列表选择MMSI",
        options=options,
        index=options.index(selected_user) if selected_user in options else 0,
        format_func=lambda x: "未选择" if x == 0 else str(x),
    )

    if chosen:
        selected_user = chosen
        st.session_state["selected_user_id"] = chosen

    if selected_user:
        selected_row = ship_df.loc[ship_df["user_id"] == selected_user].iloc[0]
        st.markdown(f"**当前目标(MMSI)**: `{selected_user}`")
        st.markdown(f"**批次时间**: `{nearest_dt_str} UTC`")
        st.dataframe(
            build_detail_table(selected_row),
            width="stretch",
            hide_index=True,
            height=760,
        )
