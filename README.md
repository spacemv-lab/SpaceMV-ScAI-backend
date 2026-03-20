# **SpaceMV-ScAI Backend: 星座智能管理平台服务端**
<div align="center">

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/tianxunweixiao/SpaceMV-ScAI-Backend)

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![ClickHouse](https://img.shields.io/badge/Database-ClickHouse-FFCC00?logo=clickhouse&logoColor=black)](https://clickhouse.com/)
[![Streamlit](https://img.shields.io/badge/Visual-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

[**简体中文**](./README.md) | [**English**](./README_EN.md)
</div>

<img width="2564" height="1536" alt="Gemini_Generated_Image_7urlyp7urlyp7url" src="https://github.com/user-attachments/assets/b018204f-a95b-4f39-a104-1fda4432462f" />

[SpaceMV-ScAI](https://github.com/tianxunweixiao/SpaceMV-ScAI/tree/main)是由成都天巡微小卫星科技有限责任公司研发的一款星座智能管理平台，旨在解决当前商业航天领域星座规模急剧扩大带来的运控复杂性难题。

平台采用面向Agent的架构设计，当前开源版本聚焦于构建高精度的轨道仿真计算引擎与数据交互底座。目前已支持光学遥感卫星全天候、全地域的目标区域覆盖仿真与资源调度，智能体自动化任务编排，ADS-B/AIS数据实时可视化展示等功能。

`SpaceMV-ScAI Backend`作为平台的核心服务端组件，承载了用户请求处理、仿真任务执行、可视化服务支撑、数据存储管理及 API 接口分发等关键职能。

## **📖 目录**

* [核心模块](#-核心模块)
* [技术架构](#-技术架构)
* [功能特性](#-功能特性)
* [快速开始](#-快速开始)
* [API 文档](#-api-文档)
* [故障排除](#-故障排除)
* [贡献指南](#-贡献指南)
* [许可证](#-许可证)
* [联系方式](#-联系方式)
* [待办事项](#-待办事项)

## **🧩 核心模块**

Space-MV ScAI Backend 由以下四大核心模块组成：

| 模块 | 目录 | 说明 |
| :---- | :---- | :---- |
| **账户管理服务** | account\_backend | 负责用户认证（JWT）、权限管理及账户安全。 |
| **仿真服务** | serve\_backend | 核心引擎，处理卫星数据管理及 STK 覆盖性仿真分析。 |
| **可视化服务** | visual\_backend | 基于 Streamlit 构建的可视化平台，支持瓦片地图、轨迹展示，以及 ADS-B / AIS 全球目标快照可视化。 |
| **数据同步** | timer.py / opensky\_timer.py / ais\_timer.py | 定时任务脚本，负责从 Celestrak API 同步最新卫星数据，并同步 ADS-B 航空器状态和 AIS 船舶位置数据。 |

## **🏗 技术架构**

### **目录结构**

Space-MV ScAI Backend/  
├── account\_backend/          \# 🔐 账户管理服务  
│   ├── app.py                \# FastAPI 应用入口  
│   ├── configs/              \# 配置管理  
│   ├── controllers/          \# 路由控制器  
│   ├── services/             \# 业务逻辑层  
│   ├── models/               \# 数据模型  
│   └── extensions/           \# 扩展模块  
│  
├── serve\_backend/            \# 🛰️ 仿真服务  
│   ├── app.py                \# FastAPI 应用入口  
│   ├── configs/              \# 配置管理  
│   ├── controllers/          \# 路由控制器（卫星、星座、传感器、仿真）  
│   ├── services/             \# 业务逻辑层  
│   ├── libs/                 \# 工具库（仿真报告生成）  
│   └── output/               \# 仿真结果输出目录  
│  
├── visual\_backend/           \# 📊 可视化服务  
│   ├── app\_tiles.py          \# 覆盖性分析入口（带瓦片地图）  
│   ├── app\_notiles.py        \# 覆盖性分析入口（无瓦片地图）  
│   ├── app\_opensky.py        \# ADS-B 全球飞机快照可视化入口  
│   ├── app\_ais.py            \# AIS 全球船舶快照可视化入口  
│   └── tiles/                \# 地图瓦片服务  
│       ├── cors\_server.py    \# CORS 服务器  
│       └── gaode\_tiles/      \# 本地缓存的高德地图瓦片  
│  
├── stk\_scripts/              \# 🚀 STK 调用脚本  
│   ├── stk\_simulation.py     \# 覆盖性分析执行脚本  
│   └── stk\_backprogress.py   \# 数据处理函数库  
│  
├── timer.py                  \# 🕒 卫星数据同步定时器  
├── opensky_timer.py          \# ✈️ ADS-B 数据同步定时器  
├── ais_timer.py              \# 🚢 AIS 数据同步定时器  
├── requirements.txt          \# 项目依赖  
└── .env.example              \# 环境配置示例文件

### 技术栈

| 领域 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| **后端框架** | **FastAPI** | 高性能异步 Web 框架 |
| | **Uvicorn** | ASGI 服务器 |
| | **Pydantic** | 数据验证与配置管理 |
| **数据库** | **ClickHouse** | 存储海量卫星、星座和用户数据 |
| **可视化** | **Streamlit** | 快速构建数据应用 |
| | **Plotly** | 交互式图表绘制 |
| **工具组件** | **Paramiko** | SSH 客户端，用于远程 STK 调用 |
| | **APScheduler** | 定时任务调度 |
| | **STK Engine** | 卫星工具包（需单独授权） |

### **数据流向**

graph TD  
    A\[Celestrak API\] \--\>|同步数据| B(timer.py 定时器)  
    G\[OpenSky Network API\] \--\>|ADS-B 同步| H(opensky_timer.py 定时器)  
    I\[AISStream WebSocket\] \--\>|AIS 同步| J(ais_timer.py 定时器)  
    B \--\>|写入/更新| C\[(ClickHouse 数据库)\]  
    H \--\>|写入快照| C  
    J \--\>|写入批次| C  
    C \<--\>|读写数据| D\[serve\_backend 仿真服务\]  
    C \--\>|快照查询| E\[visual\_backend 可视化服务\]  
    D \--\>|提供数据| E\[visual\_backend 可视化服务\]  
    E \--\>|交互展示| F\[用户界面\]

## **✨ 功能特性**

### **1\. 账户管理服务 (account\_backend)**

**端口**: 5001

* 🔐 **认证安全**: 支持用户注册、登录、密码加密存储及 JWT 令牌认证。  
* 👤 **状态管理**: 完整的账户生命周期管理。  
* **API**: /api/login, /api/accountAdd

### **2\. 仿真服务 (serve\_backend)**

**端口**: 8401

* 🛰️ **卫星与星座管理**: 支持卫星/星座的增删改查，支持上传自定义星座配置。  
* 📡 **传感器管理**: 传感器参数的配置、查询与更新。  
* 🚀 **仿真执行**:  
  * 支持 STK 覆盖性分析仿真（流式输出）。  
  * **混合调度模式**: 支持本地执行或通过 SSH 调度远程 STK 服务器执行任务。  
  * 自动生成仿真报告。  

### **3\. 可视化服务 (visual\_backend)**

* 🌍 **2D 地图可视化**: 实时渲染卫星轨迹、传感器覆盖包络及目标区域（点/线/面）。  
* 🗺️ **瓦片服务**: 集成自定义或离线地图瓦片。  
* 📦 **数据加载**: 支持从压缩包或 JSON 自动解析并加载仿真结果。
* ✈️ **ADS-B 可视化**: 新增 `app_opensky.py`，支持基于 `opensky` 表的全球飞机快照展示、UTC 时间滑块选择、地图点选和飞机属性明细查看。  
* 🚢 **AIS 可视化**: 新增 `app_ais.py`，支持基于 `AIS` 表的全球船舶快照展示、批次时间选择、地图点选和船舶属性明细查看。  
* 🧭 **双底图模式**: ADS-B / AIS 页面均支持离线矢量底图与本地瓦片底图切换；启用本地瓦片模式时需先启动 `visual_backend/tiles/cors_server.py`。  

### **4\. 数据同步 (timer.py / opensky_timer.py / ais_timer.py)**

* 自动从 Celestrak API 获取最新 TLE 数据。  
* 智能识别并分类星座（GPS, Starlink, Beidou 等）。  
* 自动初始化数据库表结构并维护数据表。
* ✈️ **ADS-B 同步 (`opensky_timer.py`)**: 按 1 小时间隔从 OpenSky Network 拉取全球飞机状态向量，自动创建 `opensky` 表并写入快照数据；配置 `OPENSKY_USERNAME` / `OPENSKY_PASSWORD` 后可使用认证请求。  
* 🚢 **AIS 同步 (`ais_timer.py`)**: 按 1 小时间隔从 AISStream WebSocket 采集船舶位置数据，默认每批连续接收 3 分钟并保留每艘船舶最新一条记录，自动创建 `AIS` 表；启用前需配置 `AISSTREAM_API_KEY`。  

## **🚀 快速开始**

### **前置条件**

* **Docker** (用于部署 ClickHouse)  
* **STK Desktop (Windows) / STK Engine (Linux) 12.X**  
* 已配置好 **STK agi 包** 的 Python 环境
* 可选：**OpenSky Network 账号**（用于提升 ADS-B 接口可用性）  
* 可选：**AISStream API Key**（启用 AIS 数据同步时必需）  

### **1. 环境准备**
```bash
# 克隆仓库  
git clone https://github.com/tianxunweixiao/SpaceMV-ScAI-backend.git   
cd SpaceMV-ScAI-backend

# 创建并激活 Conda 环境  
conda create -n scai python=3.12  
conda activate scai

# 安装依赖  
pip install -r requirements.txt
```
### **2. 初始化数据库**
```bash
启动 ClickHouse 容器并运行同步脚本以初始化表结构和基础数据：

# 启动 ClickHouse  
docker run -d \  
--restart=always \
--log-opt max-size=1g \  
--log-opt max-file=10 \ 
--ulimit nofile=262144:262144 \  
-e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \ 
-e CLICKHOUSE_DB=xingzuo \ 
-e CLICKHOUSE_USER=your_user \ 
-e CLICKHOUSE_PASSWORD=your_password \  
-p 9000:9000 \
-p 9004:9004 \
-p 8123:8123 \  
--name clickhouse clickhouse:25.3.6.56

# 初始化数据  
python timer.py
```

如需启用新增的 ADS-B / AIS 数据同步，可分别启动以下脚本（首次运行会自动建表并执行一次采集，随后进入每小时调度）：

```bash
python opensky_timer.py
python ais_timer.py
```
### **3. 环境变量配置**
```ini
复制示例文件并修改配置：

cp .env.example .env

编辑 .env 文件，重点配置以下内容：

# ClickHouse 配置  
CLICKHOUSE_HOST=your_clickhouse_host  
CLICKHOUSE_USER=your_user  
CLICKHOUSE_PASSWORD=your_password

# --- STK 仿真配置 (关键) ---  
# 模式 A: 本地执行 (STK 与后端在同一台机器)  
STK_LOCAL=True  
STK_PYTHON_LOCAL_EXE=C:\Path\To\python.exe  
STK_SCRIPT_LOCAL_PATH=D:\Path\To\stk_simulation.py

# 模式 B: 远程执行 (通过 SSH 调用远程 STK 服务器)  
STK_LOCAL=False  
STK_PYTHON_REMOTE_EXE=C:\Path\To\Remote\python.exe  
STK_SCRIPT_REMOTE_PATH=C:\Path\To\Remote\stk_simulation.py  
REPLACE_BASE=C:\Path\To\Project  # 远程服务器上的项目基准路径  
SSH_HOST=xxx  
SSH_USER=xxx  
SSH_PASSWORD=xxxxx

# OpenSky ADS-B 配置（可选，配置后使用认证请求）
OPENSKY_USERNAME=your_opensky_username
OPENSKY_PASSWORD=your_opensky_password

# AIS 数据采集配置（启用 ais_timer.py 时必填 API Key）
AISSTREAM_API_KEY=your_aisstream_api_key
AIS_WS_URL=wss://stream.aisstream.io/v0/stream
AIS_BATCH_MINUTES=1
```
### **4. 启动服务**
```bash
本项目使用 PM2 进行进程管理：

# 安装 pm2  
npm install -g pm2

# 启动所有服务  
pm2 start start_project.config.js

# 查看服务状态  
pm2 list
```

当前 `start_project.config.js` 默认启动基础服务；ADS-B / AIS 定时器与可视化页面可按需单独部署，例如：

```bash
python opensky_timer.py
python ais_timer.py

streamlit run visual_backend/app_opensky.py --server.headless true --server.port 8502
streamlit run visual_backend/app_ais.py --server.headless true --server.port 8503

# 若使用本地瓦片模式，需额外启动
python visual_backend/tiles/cors_server.py
```

SpaceMV-ScAI 客户端仓库可参考[SpaceMV-ScAI-frontend](https://github.com/tianxunweixiao/SpaceMV-ScAI-frontend)

## **📚 API 文档**

服务启动成功后，可访问自动生成的交互式文档：

* **账户服务**: [http://localhost:5001/docs](http://localhost:5001/docs)  
* **仿真服务**: [http://localhost:8401/docs](http://localhost:8401/docs)

ADS-B和AIS数据可单独启动可视化页面，访问：

* **ADS-B 可视化**: [http://localhost:8502](http://localhost:8502)  
* **AIS 可视化**: [http://localhost:8503](http://localhost:8503)  

## **🔧 故障排除**

| 问题 | 可能原因及排查方法 |
| :---- | :---- |
| **ClickHouse 连接失败** | 1\. 检查 .env 配置。 2\. 确认 Docker 容器状态 (docker ps)。 3\. 检查 8123/9000 端口是否被防火墙拦截。 |
| **STK 仿真失败** | 1\. 确认 STK License 是否有效。 2\. 若使用远程模式，检查 SSH 连通性及 REPLACE\_BASE 路径映射。 3\. 验证 Python 环境是否正确安装了 agi.stk 库。 |
| **可视化无数据** | 1\. 检查 serve\_backend/output 下是否有生成的 JSON 文件。 2\. 浏览器 F12 查看 Console 是否有解析错误。 |
| **ADS-B 无数据** | 1\. 确认 `opensky_timer.py` 正在运行。 2\. 检查 ClickHouse 中 `opensky` 表是否已创建。 3\. 如遇限流或返回为空，可配置 `OPENSKY_USERNAME` / `OPENSKY_PASSWORD` 后重试。 |
| **AIS 无数据** | 1\. 检查 `AISSTREAM_API_KEY` 是否正确配置。 2\. 确认 `ais_timer.py` 可以访问 `AIS_WS_URL`。 3\. 检查 ClickHouse 中 `AIS` 表是否已创建且批次时间范围内存在数据。 |
| **ADS-B / AIS 可视化页面为空** | 1\. 确认对应 Streamlit 页面连接的是正确的 ClickHouse 实例。 2\. 检查 `opensky` / `AIS` 表中是否已有数据。 3\. 若使用本地瓦片模式，确认 `visual_backend/tiles/cors_server.py` 已启动。 |

## **🤝 贡献指南**

我们非常欢迎社区开发者参与 SpaceMV-ScAI Backend 的建设！如果您有任何改进建议或发现了 Bug，请遵循以下流程：

1. **Fork 本仓库**：点击右上角的 Fork 按钮将项目复制到您的 GitHub 账户。  
2. **创建分支**：从 main 分支切出一个新分支用于开发。  
   git checkout \-b feature/AmazingFeature  
3. **提交更改**：确保代码风格统一，并撰写清晰的 Commit Message。  
   git commit \-m 'feat: Add some AmazingFeature'  
4. **推送分支**：  
   git push origin feature/AmazingFeature  
5. **提交 Pull Request**：在 GitHub 上发起 PR，并详细描述您的更改内容。

**开发建议**：

* 添加新 API 时，请在 extensions/ext\_routers.py 中注册路由。  
* 添加新服务逻辑时，请遵循 controller \-\> service \-\> model 的分层架构。

## **📄 许可证**

本项目采用 **Apache License 2.0** 许可证。

Copyright (c) 2025 成都天巡微小卫星科技有限公司

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

## **📮 联系方式**

如有任何问题、建议或商务合作需求，请联系项目维护团队。

* **Email**: code@spacemv.com  
* **Issues**: [GitHub Issues](https://github.com/tianxunweixiao/SpaceMV-ScAI-backend/issues)

更多信息可关注公司微信公众号：

<img width="106" height="106" alt="image" src="https://github.com/user-attachments/assets/69a02ad0-422c-422a-bf5f-9b7890cf31ab" />


## ✅ 待办事项

- [√] **开源前端代码**: 发布配套的 SpaceMV-ScAI-Frontend 仓库，实现完整的 B/S 架构演示。
- [√] **引入智能体 (Agent)**: 集成 AI Agent 进行自动化的星座仿真任务编排与调度。
- [ ] **多星座支持**: 增加对导航星座、通信星座的预设支持。
- [ ] **STK 接口增强**: 拓展 API 覆盖范围，支持更细粒度的仿真参数配置
- [ ] **完善文档**: 补充详细的视频教程和 API 接口用例。
