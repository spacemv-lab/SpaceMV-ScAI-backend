import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import glob
import json
import socket

# --------------------------------------------Basic Page Configuration-------------------------------------------------------
st.set_page_config(
    page_title="ScAI仿真可视化平台",
    layout="wide",
    page_icon="🛰️",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* 全局背景 */
    .stApp { background-color: #FAFAFA; }

    /* 顶部内边距 */
    .block-container { padding-top: 4.5rem; padding-bottom: 2rem; }

    /* 指标卡样式 */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF; 
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #E0E0E0;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.05);
    }

    /* 侧边栏 */
    section[data-testid="stSidebar"] { background-color: #F0F2F6; border-right: 1px solid #E6E6E6; }

    /* Expander 样式 */
    div[data-testid="stExpander"] { 
        background-color: #FFFFFF; 
        border-radius: 8px; 
        border: 1px solid #E0E0E0;
        margin-bottom: 10px;
    }

    /* 指标数值颜色 */
    div[data-testid="stMetricValue"] { color: #0068C9 !important; }
</style>
""", unsafe_allow_html=True)


# ----------------------------------- Data Reading ---------------------------------------

def parse_pos_json(file_path):
    """posLLA.json"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        data = []
        for time_str in sorted(raw_data.keys()):
            coords = raw_data[time_str]
            data.append({"time": time_str, "lon": coords[0], "lat": coords[1], "alt": coords[2]})
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()



def parse_sensor_json(file_path):
    """sensorProjection.json"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        processed_data = {}
        for time_str, polygon in raw_data.items():
            lats, lons = ensure_clockwise_winding([p[0] for p in polygon], [p[1] for p in polygon])
            processed_data[time_str] = {"lats": lats, "lons": lons}
        return processed_data
    except Exception:
        return {}

def parse_targets_json(file_path):
    """targets.json"""
    targets = {"points": [], "lines": [], "polygons": []}
    if not os.path.exists(file_path): return targets
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        if "point" in raw_data:
            p_data = raw_data["point"]
            targets["points"] = [{"lat": p[0], "lon": p[1]} for p in
                                 (p_data if isinstance(p_data[0], list) else [p_data])]
        if "line" in raw_data:
            targets["lines"].append(
                {"lats": [p[0] for p in raw_data["line"]], "lons": [p[1] for p in raw_data["line"]]})
        if "polygon" in raw_data:
            lats, lons = ensure_clockwise_winding([p[0] for p in raw_data["polygon"]],
                                                  [p[1] for p in raw_data["polygon"]])
            if lats[0] != lats[-1] or lons[0] != lons[-1]:
                lats.append(lats[0])
                lons.append(lons[0])
            targets["polygons"].append({"lats": lats, "lons": lons})
    except Exception:
        pass
    return targets


def ensure_clockwise_winding(lats, lons):
    if len(lats) < 3: return lats, lons
    area = sum((lons[(i + 1) % len(lats)] - lons[i]) * (lats[(i + 1) % len(lats)] + lats[i]) for i in range(len(lats)))
    return (lats[::-1], lons[::-1]) if area < 0 else (lats, lons)


def handle_dateline_crossing(lons, lats):
    """
    Handling Cross-Date Boundaries
    """
    clean_lons, clean_lats = [], []
    for i in range(len(lons)):
        clean_lons.append(lons[i])
        clean_lats.append(lats[i])

        if i < len(lons) - 1:
            lon1, lon2 = lons[i], lons[i + 1]
            lat1, lat2 = lats[i], lats[i + 1]

            # Detect whether crossing the International Date Line
            if abs(lon2 - lon1) > 180:
                
                d_total = 360 - abs(lon1 - lon2)

                if lon1 > 0:  
                    dist_to_edge = 180 - lon1
                    lat_cross = lat1 + (lat2 - lat1) * (dist_to_edge / d_total)

                    clean_lons.extend([180, None, -180])
                    clean_lats.extend([lat_cross, None, lat_cross])
                else: 
                    dist_to_edge = abs(-180 - lon1)
                    lat_cross = lat1 + (lat2 - lat1) * (dist_to_edge / d_total)

                    clean_lons.extend([-180, None, 180])
                    clean_lats.extend([lat_cross, None, lat_cross])

    return clean_lons, clean_lats


def load_data_from_server_path(root_path):
    if not os.path.exists(root_path): return None, None, "服务器路径不存在"
    pos_dir, sensor_dir = os.path.join(root_path, "poslla"), os.path.join(root_path, "sensorprojection")
    pos_files = glob.glob(os.path.join(pos_dir, "*.json"))
    if not pos_files: return None, None, "poslla 文件夹为空"
    satellites = {}
    for p_file in pos_files:
        sat_id = os.path.basename(p_file).replace("posLLA_", "").replace(".json", "")
        df = parse_pos_json(p_file)
        if df.empty: continue
        s_file = os.path.join(sensor_dir, f"sensorProjection_{sat_id}.json")
        satellites[sat_id] = {"df": df, "sensor": parse_sensor_json(s_file) if os.path.exists(s_file) else {}}
    return satellites, parse_targets_json(os.path.join(root_path, "targets", "targets.json")), None


def simplify_coords(lons, lats, step=2):
    if len(lons) < 20: return lons, lats
    s_lons = lons[::step]
    s_lats = lats[::step]

    if s_lons[0] != s_lons[-1]:
        s_lons.append(s_lons[0])
        s_lats.append(s_lats[0])
    return s_lons, s_lats

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = '127.0.0.1'
    return ip

# --------------------------------------------------Data loading----------------------------------------------------
query_params = st.query_params
data_path_arg = query_params.get("data_path", None)
zip_path_arg = query_params.get("zip_path", None)

if not data_path_arg:
    st.info("👋 欢迎使用ScAI仿真可视化服务。请等待后端重定向数据...")
    st.stop()

with st.spinner(f"正在加载仿真数据..."):
    sat_data, targets_data, error_msg = load_data_from_server_path(data_path_arg)

if error_msg:
    st.error(f"❌ 数据加载失败: {error_msg}")
    st.stop()

# ---------------------------------------------------Sidebar Configuration--------------------------------------------------

with st.sidebar:
    st.header("🎛️ 仿真控制面板")

    # 1. Download Results
    if zip_path_arg and os.path.exists(zip_path_arg):
        with open(zip_path_arg, "rb") as fp:
            st.download_button("📥 下载结果报告", fp, os.path.basename(zip_path_arg), "application/zip")

    st.divider()

    # 2. Map Base Layer
    st.subheader("🗺️ 底图设置")
    default_tile = f"http://{get_host_ip()}:9999/gaode_tiles/" + "{z}/{x}/{y}.png"  # 默认url
    tile_url = st.text_input("底图瓦片", value=default_tile, help="输入本地或在线瓦片URL")

    col_z1, col_z2 = st.columns(2)
    with col_z1:
        init_zoom = st.number_input("缩放级别", value=1.1, step=0.1, min_value=0.0, max_value=22.0)
    with col_z2:
        sim_speed = st.number_input("动画间隔(ms)", value=300, step=10, min_value=10)

    st.divider()

    # 3. Style Customization
    st.subheader("🎨 样式配置")

    with st.expander("📍 地面目标", expanded=False):
        t1, t2 = st.columns(2)
        target_pt_color = t1.color_picker("点目标", "#D32F2F")
        target_pt_size = t2.slider("标记大小", 5, 20, 8)

        t3, t4 = st.columns(2)
        target_ln_color = t3.color_picker("线目标", "#2E7D32")
        target_ln_width = t4.slider("线宽", 1, 10, 3)

        t5, t6 = st.columns(2)
        target_frame_color = t5.color_picker("面目标(边框)", "#7B1FA2")
        target_frame_width = t6.slider("线宽", 1, 10, 2)

        t7, t8 = st.columns(2)
        target_poly_color = t7.color_picker("面目标(填充)", "#7B1FA2")
        target_poly_opacity = t8.slider("透明度", 0.0, 1.0, 0.8)

    with st.expander("🛰️ 卫星方位", expanded=False):
        s1, s2 = st.columns(2)
        sat_marker_color = s1.color_picker("实时位置", "#EA900D")
        sat_marker_size = s2.slider("标记大小 ", 5, 20, 8)

        s3, s4 = st.columns(2)
        traj_color = s3.color_picker("星下点轨迹", "#1976D2")
        traj_width = s4.slider("轨迹线宽", 1, 10, 2)

    with st.expander("📡 传感器视场", expanded=False):
        v1, v2 = st.columns(2)
        fov_frame_color = v1.color_picker("视场范围(边框)", "#D32F2F")
        fov_frame_width = v2.slider("线宽 ", 1, 10, 2)

        v3, v4 = st.columns(2)
        fov_fill_color = v3.color_picker("视场范围(填充)", "#D32F2F")
        fov_opacity = v4.slider("透明度 ", 0.0, 1.0, 0.8)


        fov_hex = fov_fill_color.lstrip('#')
        fov_rgb = tuple(int(fov_hex[i:i + 2], 16) for i in (0, 2, 4))
        fov_rgba = f"rgba({fov_rgb[0]}, {fov_rgb[1]}, {fov_rgb[2]}, {1 - fov_opacity})"

    st.divider()

    # 4. Layer Switch
    st.subheader("👁️ 图层开关")
    all_sats = list(sat_data.keys())
    selected_sats = st.multiselect("选择显示卫星", all_sats, default=all_sats)

    show_traj = st.toggle("显示星下点轨迹", value=True)
    show_sensor = st.toggle("显示传感器视场", value=True)
    show_targets = st.toggle("显示地面目标", value=True)


# ------------------------------------------------Main Drawing Interface-------------------------------------------------

task_name = os.path.basename(os.path.normpath(data_path_arg))
sat_count = len(sat_data)
first_sat = list(sat_data.keys())[0]
base_df = sat_data[first_sat]["df"]
time_start, time_end = base_df.iloc[0]['time'], base_df.iloc[-1]['time']

c1, c2, c3 = st.columns(3)
c1.metric("仿真目标", task_name)
c2.metric("仿真模式", "🌌 星座组网" if sat_count > 1 else "🛰️ 单星任务")
c3.metric("卫星数量", f"{sat_count} 颗")

if not selected_sats:
    st.warning("请在左侧选择至少一颗卫星进行展示")
else:
    step = max(1, int(len(base_df) / 200))
    plot_df = base_df.iloc[::step].reset_index(drop=True)

    fig = go.Figure()

    # --- A. Static Layer: Ground Targets ---
    show_target_legend_point = True
    show_target_legend_line = True
    show_target_legend_polygon = True

    if show_targets and targets_data:
        # point
        for p in targets_data["points"]:
            fig.add_trace(go.Scattermap(
                lon=[p['lon']], lat=[p['lat']],
                mode='markers',
                marker=dict(size=target_pt_size, color=target_pt_color, opacity=0.9),
                name='地面点目标', hoverinfo='text', text="地面点目标",
                showlegend=show_target_legend_point
            ))
            show_target_legend_point = False

        # line
        for l in targets_data["lines"]:
            lons, lats = handle_dateline_crossing(l['lons'], l['lats'])
            fig.add_trace(go.Scattermap(
                lon=lons, lat=lats,
                mode='lines',
                line=dict(width=target_ln_width, color=target_ln_color),
                name='地面线目标',
                showlegend=show_target_legend_line
            ))
            show_target_legend_line = False

        # polygon
        for poly in targets_data["polygons"]:
            lons, lats = poly['lons'], poly['lats']
            lon_span = max(lons) - min(lons)
            fill_mode = 'toself' if lon_span < 180 else 'none'
            if fill_mode == 'none':
                lons, lats = handle_dateline_crossing(lons, lats)

            poly_hex = target_poly_color.lstrip('#')
            poly_rgb = tuple(int(poly_hex[i:i + 2], 16) for i in (0, 2, 4))

            fig.add_trace(go.Scattermap(
                lon=lons, lat=lats,
                mode='lines', fill=fill_mode,
                fillcolor=f"rgba({poly_rgb[0]}, {poly_rgb[1]}, {poly_rgb[2]}, {1 - target_poly_opacity})",
                line=dict(width=target_frame_width, color=target_frame_color),
                name='地面面目标',
                showlegend=show_target_legend_polygon
            ))
            show_target_legend_polygon = False

    # --- B. Static Layer: Satellite Azimuth and Sub-Point Trajectory ---
    show_traj_legend = True
    if show_traj:
        for sat in selected_sats:
            df = sat_data[sat]['df']
            lons, lats = handle_dateline_crossing(df['lon'].tolist(), df['lat'].tolist())
            fig.add_trace(go.Scattermap(
                lon=lons, lat=lats,
                mode='lines',
                line=dict(width=traj_width, color=traj_color),
                opacity=0.6,
                name=f"卫星星下点轨迹", 
                showlegend=show_traj_legend,
                hoverinfo='skip'
            ))
            show_traj_legend = False

    # --- C. trace ---
    trace_indices = {}
    show_sat_pos_legend = True
    show_sensor_legend = True

    for sat in selected_sats:
        trace_indices[sat] = {}

        trace_indices[sat]['pos'] = len(fig.data)
        fig.add_trace(go.Scattermap(
            lon=[sat_data[sat]['df'].iloc[0]['lon']],
            lat=[sat_data[sat]['df'].iloc[0]['lat']],
            mode='markers+text',
            marker=dict(size=sat_marker_size, color=sat_marker_color),
            text=sat, textposition='top center',
            textfont=dict(size=8, color='#EA900D', family="Arial Black"),
            name='卫星实时位置',
            showlegend=show_sat_pos_legend
        ))
        show_sat_pos_legend = False

        if show_sensor:
            trace_indices[sat]['sensor'] = len(fig.data)
            fig.add_trace(go.Scattermap(
                lon=[], lat=[],
                mode='lines', fill='toself',
                fillcolor=fov_rgba,
                line=dict(width=fov_frame_width, color=fov_frame_color),
                name='传感器视场范围',
                showlegend=show_sensor_legend
            ))
            show_sensor_legend = False

    # --- D. frames ---
    frames = []
    dynamic_idx_list = []
    for sat in selected_sats:
        dynamic_idx_list.append(trace_indices[sat]['pos'])
        if show_sensor:
            dynamic_idx_list.append(trace_indices[sat]['sensor'])

    for i, row in plot_df.iterrows():
        frame_traces = []
        idx = i * step
        current_time_str = row['time']

        show_sat_pos_legend = True
        show_sensor_legend = True

        for sat in selected_sats:

            df = sat_data[sat]['df']
            pos = df.iloc[idx] if idx < len(df) else df.iloc[-1]
            frame_traces.append(go.Scattermap(
                lon=[pos['lon']], lat=[pos['lat']],
                mode='markers+text',
                marker=dict(size=sat_marker_size, color=sat_marker_color if idx < len(df) else '#999999'),
                text=sat, textposition='top center',
                showlegend=show_sat_pos_legend
            ))

            if show_sensor:
                sensor = sat_data[sat]['sensor'].get(current_time_str)
                if sensor and sensor['lons']:
                    lons, lats = simplify_coords(sensor['lons'], sensor['lats'])
                    lon_span = max(lons) - min(lons)
                    is_crossing = lon_span > 180
                    fill_mode = 'none' if is_crossing else 'toself'

                    lons_c, lats_c = handle_dateline_crossing(lons, lats)
                    if not is_crossing and (lons_c[0] != lons_c[-1]):
                        lons_c.append(lons_c[0])
                        lats_c.append(lats_c[0])
                    frame_traces.append(go.Scattermap(
                        lon=lons_c, lat=lats_c,
                        mode='lines', fill=fill_mode,
                        fillcolor=fov_rgba,
                        line=dict(width=1, color=fov_fill_color),
                        showlegend=show_sensor_legend
                    ))
                else:
                    frame_traces.append(go.Scattermap(lon=[], lat=[], showlegend=False))

            show_sat_pos_legend = False
            show_sensor_legend = False

        frames.append(go.Frame(
            data=frame_traces,
            name=str(i),
            traces=dynamic_idx_list
        ))
    fig.frames = frames

    # --- E. Layout Settings ---
    fig.update_layout(
        title={
            'text': f"🛰️ 仿真时间窗口: {time_start} → {time_end}",
            'font': {'size': 20, 'color': '#333333', 'family': 'Arial'},
            'x': 0.5, 'xanchor': 'center'
        },
        map=dict(
            style="white-bg",
            layers=[{
                "below": 'traces',
                "sourcetype": "raster",
                "source": [tile_url]
            }],
            center=dict(lat=0, lon=0),
            zoom=init_zoom,
            bounds=dict(
                west=-179.999999,
                east=180.0000009,
                south=-90,
                north=90
            )
        ),
        font=dict(color="#333333", family="Arial"),
        legend=dict(
            x=0.01, y=0.98,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='#DDDDDD', borderwidth=1,
            font=dict(size=12, color='#333333')
        ),
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "x": 0.12, "y": 0.03,
            "xanchor": "left", "yanchor": "bottom",
            "bgcolor": "#FFFFFF",
            "bordercolor": "#CCCCCC",
            "borderwidth": 1,
            "font": {"color": "#333333"},
            "buttons": [
                {
                    "label": "▶ 播放",
                    "method": "animate",
                    "args": [None, {
                        "frame": {"duration": sim_speed, "redraw": True},
                        "fromcurrent": True,
                        "mode": "immediate",
                        "transition": {"duration": 0, "easing": "linear"}
                    }]
                },
                {
                    "label": "⏸ 暂停",
                    "method": "animate",
                    "args": [[None], {
                        "frame": {"duration": 0, "redraw": False},
                        "mode": "immediate",
                        "transition": {"duration": 0}
                    }]
                },
                {
                    "label": "⏮ 重置",
                    "method": "animate",
                    "args": [[str(0)], {
                        "frame": {"duration": 0, "redraw": True},
                        "mode": "immediate"
                    }]
                }
            ]
        }],
        sliders=[{
            "steps": [
                {
                    "args": [
                        [str(k)],
                        {
                            "frame": {"duration": 0, "redraw": True},
                            "mode": "immediate",
                            "transition": {"duration": 0}
                        }
                    ],
                    "label": row['time'].split(' ')[1] if ' ' in row['time'] else row['time'],
                    "method": "animate"
                }
                for k, row in plot_df.iterrows()
            ],
            "active": 0,
            "currentvalue": {
                "prefix": "⏱ 当前时间: ",
                "visible": True,
                "font": {"color": "#0068C9", "size": 14, "weight": "bold"},
                "xanchor": "left"
            },
            "len": 0.95,
            "x": 0.03,
            "y": 0,
            "pad": {"t": 30, "b": 10},
            "bgcolor": "#F0F0F0",
            "bordercolor": "#CCCCCC",
            "borderwidth": 1,
            "tickcolor": "#333333",
            "font": {"color": "#333333"}
        }],
        margin={"r": 0, "t": 60, "l": 0, "b": 0},
        height=750,
        paper_bgcolor='#FFFFFF',
        plot_bgcolor='#FFFFFF',
    )

    st.plotly_chart(fig, width='stretch', config={'scrollZoom': True})