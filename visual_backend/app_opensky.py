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
    page_title="ADS-B",
    page_icon="✈️",
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
    "icao24": {"label": "飞机硬件ID", "note": "飞机唯一硬件标识。"},
    "callsign": {"label": "航班呼号", "note": "航空公司代码+航班号。"},
    "origin_country": {"label": "注册国", "note": "注册国家。"},
    "time_position": {"label": "位置时间戳", "note": "最后一次位置更新时间（Unix 秒，UTC）。"},
    "last_contact": {"label": "最后联系时间戳", "note": "最后一次收到任意信号时间（Unix 秒，UTC）。"},
    "longitude": {"label": "经度", "note": "WGS-84，经度，单位度。"},
    "latitude": {"label": "纬度", "note": "WGS-84，纬度，单位度。"},
    "baro_altitude": {"label": "气压高度", "note": "单位米，基于标准大气压计算。"},
    "on_ground": {"label": "是否在地面", "note": "1 表示在地面（落地/滑行），0 表示空中。"},
    "velocity": {"label": "对地速度", "note": "单位 m/s。"},
    "true_track": {"label": "航向角", "note": "单位度，正北为0，顺时针。"},
    "vertical_rate": {"label": "垂直速度", "note": "单位 m/s，正数爬升，负数下降。"},
    "sensors_json": {"label": "接收机列表", "note": "贡献该数据的接收机ID列表。"},
    "geo_altitude": {"label": "几何高度", "note": "单位米，GPS/几何高度。"},
    "squawk": {"label": "应答机代码", "note": "空管识别码。"},
    "spi": {"label": "SPI标志", "note": "特殊用途指示。"},
    "position_source": {"label": "位置来源", "note": "0=ADS-B, 1=ASTERIX, 2=MLAT, 3=FLARM。"},
    "snapshot_time": {"label": "快照时间", "note": "本批次抓取时间（Unix 秒，UTC）。"},
}

SOURCE_MAP = {
    0: "ADS-B",
    1: "ASTERIX",
    2: "MLAT",
    3: "FLARM",
}

TABLE_COLUMNS = [
    "icao24",
    "callsign",
    "origin_country",
    "time_position",
    "last_contact",
    "longitude",
    "latitude",
    "baro_altitude",
    "on_ground",
    "velocity",
    "true_track",
    "vertical_rate",
    "sensors_json",
    "geo_altitude",
    "squawk",
    "spi",
    "position_source",
    "snapshot_time",
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
    result = client.execute(f"EXISTS TABLE {db_name}.opensky")
    return bool(result and result[0] and result[0][0] == 1)


def query_time_stats(client: Client, db_name: str) -> Dict[str, int]:
    sql = f"""
    SELECT
        min(snapshot_time) AS min_snapshot,
        max(snapshot_time) AS max_snapshot,
        countDistinct(snapshot_time) AS snapshot_count,
        count() AS row_count
    FROM {db_name}.opensky
    """
    row = client.execute(sql)[0]
    return {
        "min_snapshot": int(row[0]) if row[0] is not None else 0,
        "max_snapshot": int(row[1]) if row[1] is not None else 0,
        "snapshot_count": int(row[2]) if row[2] is not None else 0,
        "row_count": int(row[3]) if row[3] is not None else 0,
    }


def query_nearest_snapshot(client: Client, db_name: str, target_ts: int) -> Optional[int]:
    sql = f"""
    SELECT snapshot_time
    FROM {db_name}.opensky
    GROUP BY snapshot_time
    ORDER BY abs(snapshot_time - %(target_ts)s)
    LIMIT 1
    """
    result = client.execute(sql, {"target_ts": target_ts})
    return int(result[0][0]) if result else None


def query_snapshot_rows(client: Client, db_name: str, snapshot_ts: int) -> pd.DataFrame:
    sql = f"""
    SELECT
        {", ".join(TABLE_COLUMNS)}
    FROM
    (
        SELECT *
        FROM {db_name}.opensky
        WHERE snapshot_time = %(snapshot_ts)s
        ORDER BY ingested_at DESC
        LIMIT 1 BY icao24
    )
    WHERE longitude IS NOT NULL AND latitude IS NOT NULL
    ORDER BY icao24
    """
    rows = client.execute(sql, {"snapshot_ts": snapshot_ts})
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def query_snapshot_plane_count(client: Client, db_name: str, snapshot_ts: int) -> int:
    sql = f"""
    SELECT countDistinct(icao24)
    FROM {db_name}.opensky
    WHERE snapshot_time = %(snapshot_ts)s
    """
    return int(client.execute(sql, {"snapshot_ts": snapshot_ts})[0][0])


def normalize_origin_country(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() == "taiwan":
        return "Taiwan, China"
    return value


def to_unix_utc(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


def format_value(field: str, value: Any) -> str:
    if value is None:
        return "-"
    if field in ("time_position", "last_contact", "snapshot_time"):
        return f"{value} ({to_utc_str(int(value))} UTC)"
    if field in ("on_ground", "spi"):
        return "是" if int(value) == 1 else "否"
    if field == "position_source":
        int_val = int(value)
        return f"{int_val} ({SOURCE_MAP.get(int_val, 'Unknown')})"
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


def extract_selected_icao(chart_event: Any) -> Optional[str]:
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
    if isinstance(first_point, dict):
        custom = first_point.get("customdata")
    else:
        custom = getattr(first_point, "customdata", None)

    if isinstance(custom, (list, tuple)) and custom:
        return str(custom[0])
    if isinstance(custom, str):
        return custom
    return None


def render_map(
    df: pd.DataFrame,
    title: str,
    basemap_mode: str,
    tile_url: str,
    tile_zoom: float,
) -> Any:
    custom_data = df[["icao24", "callsign", "origin_country"]].values
    hover_template = (
        "<b>%{customdata[0]}</b><br>"
        "呼号: %{customdata[1]}<br>"
        "国家: %{customdata[2]}<br>"
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
                marker=dict(
                    size=5,
                    color="#f26419",
                    opacity=0.78,
                ),
                selected=dict(marker=dict(size=9, color="#0d9488")),
                unselected=dict(marker=dict(opacity=0.6)),
                hovertemplate=hover_template,
                name="飞机位置",
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
            uirevision="opensky-map",
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
                marker=dict(
                    size=5,
                    color="#f26419",
                    opacity=0.78,
                ),
                selected=dict(marker=dict(size=9, color="#0d9488")),
                unselected=dict(marker=dict(opacity=0.6)),
                hovertemplate=hover_template,
                name="飞机位置",
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
            uirevision="opensky-map",
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


st.title("ADS-B 全球飞机航迹快照可视化")

try:
    client = get_clickhouse_client()
    db_name = get_database_name()
except Exception as err:
    st.error(f"ClickHouse 连接失败: {err}")
    st.stop()

if not table_exists(client, db_name):
    st.error(f"表 {db_name}.opensky 不存在。请先运行 opensky_timer.py 进行数据采集。")
    st.stop()

stats = query_time_stats(client, db_name)
min_snapshot = stats["min_snapshot"]
max_snapshot = stats["max_snapshot"]

if min_snapshot <= 0 or max_snapshot <= 0:
    st.warning("opensky 表暂无有效数据。")
    st.stop()

min_dt_utc = datetime.fromtimestamp(min_snapshot, tz=timezone.utc)
max_dt_utc = datetime.fromtimestamp(max_snapshot, tz=timezone.utc)

# Slider compatibility: use naive UTC datetime values for input widgets.
min_dt = min_dt_utc.replace(tzinfo=None)
max_dt = max_dt_utc.replace(tzinfo=None)

st.subheader("时间与范围")
c1, c2, c3, c4 = st.columns(4)
c1.metric("数据起始(UTC)", min_dt_utc.strftime("%Y-%m-%d %H:%M:%S"))
c2.metric("数据结束(UTC)", max_dt_utc.strftime("%Y-%m-%d %H:%M:%S"))
c3.metric("时间跨度", str(max_dt_utc - min_dt_utc).split(".")[0])
c4.metric("快照批次数", f"{stats['snapshot_count']:,}")

default_dt = max_dt
if "target_utc_dt" not in st.session_state:
    st.session_state["target_utc_dt"] = default_dt
else:
    cached_dt = st.session_state["target_utc_dt"]
    if cached_dt < min_dt:
        st.session_state["target_utc_dt"] = min_dt
    elif cached_dt > max_dt:
        st.session_state["target_utc_dt"] = max_dt

if min_dt == max_dt:
    target_dt = min_dt
    st.info("当前数据库仅有一个快照时间点，时间选择已固定。")
else:
    target_dt = st.slider(
        "选择目标时间（UTC）",
        min_value=min_dt,
        max_value=max_dt,
        value=st.session_state["target_utc_dt"],
        step=timedelta(minutes=1),
        format="YYYY-MM-DD HH:mm:ss",
    )
st.session_state["target_utc_dt"] = target_dt

target_ts = to_unix_utc(target_dt)
nearest_snapshot = query_nearest_snapshot(client, db_name, target_ts)

if nearest_snapshot is None:
    st.warning("未找到可用快照。")
    st.stop()

plane_df = query_snapshot_rows(client, db_name, nearest_snapshot)
if plane_df.empty:
    st.warning("该快照没有可展示的飞机位置数据。")
    st.stop()

# Display normalization only; no database mutation.
plane_df["origin_country"] = plane_df["origin_country"].map(normalize_origin_country)

nearest_dt_str = to_utc_str(nearest_snapshot)
delta_seconds = abs(nearest_snapshot - target_ts)
plane_count = query_snapshot_plane_count(client, db_name, nearest_snapshot)

st.caption(
    f"已匹配最近快照: {nearest_dt_str} UTC，"
    f"与目标时间差 {delta_seconds} 秒，当前快照飞机数 {plane_count:,}。"
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
    chart_title = f"全球矢量地图 | 快照时间: {nearest_dt_str} UTC | 飞机数: {len(plane_df):,}"
    chart_event = render_map(
        plane_df,
        chart_title,
        basemap_mode=basemap_mode,
        tile_url=tile_url,
        tile_zoom=tile_zoom,
    )
    selected_icao = extract_selected_icao(chart_event)
    if selected_icao:
        st.session_state["selected_icao24"] = selected_icao

with info_col:
    st.subheader("目标属性")
    selected_icao = st.session_state.get("selected_icao24")

    if selected_icao and selected_icao not in plane_df["icao24"].values:
        selected_icao = None
        st.session_state["selected_icao24"] = None

    if not selected_icao:
        st.info("请在地图中单击飞机点位。")

    options = [""] + plane_df["icao24"].tolist()
    chosen = st.selectbox(
        "或从列表选择",
        options=options,
        index=options.index(selected_icao) if selected_icao in options else 0,
        format_func=lambda x: "未选择" if x == "" else x,
    )

    if chosen:
        selected_icao = chosen
        st.session_state["selected_icao24"] = chosen

    if selected_icao:
        selected_row = plane_df.loc[plane_df["icao24"] == selected_icao].iloc[0]
        st.markdown(f"**当前目标**: `{selected_icao}`")
        st.markdown(f"**快照时间**: `{nearest_dt_str} UTC`")
        st.dataframe(
            build_detail_table(selected_row),
            width="stretch",
            hide_index=True,
            height=760,
        )
