# **SpaceMV-ScAI Backend: Constellation Intelligent Management Platform Server**
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

[SpaceMV-ScAI](https://github.com/tianxunweixiao/SpaceMV-ScAI/tree/main) is a constellation intelligent management platform developed by Chengdu Tianxun Microsatellite Technology Co., Ltd., designed to address the operational control complexity challenges brought by the rapid expansion of constellation scale in the commercial aerospace sector.

The platform adopts an Agent-oriented architecture design. The current open-source version focuses on building a high-precision orbit simulation calculation engine and data interaction foundation. It currently supports all-weather, all-region target area coverage simulation and resource scheduling for optical remote sensing satellites, laying a solid computing and data foundation for the future introduction of intelligent agents for automated task orchestration.

`SpaceMV-ScAI Backend`, as the core server component of the platform, carries key functions such as user request processing, simulation task execution, visualization service support, data storage management, and API interface distribution.

## **📖 Table of Contents**

* [Core Modules](#-core-modules)
* [Technical Architecture](#-technical-architecture)
* [Features](#-features)
* [Quick Start](#-quick-start)
* [API Documentation](#-api-documentation)
* [Troubleshooting](#-troubleshooting)
* [Contributing Guide](#-contributing-guide)
* [License](#-license)
* [Contact](#-contact)
* [Todo List](#-todo-list)

## **🧩 Core Modules**

Space-MV ScAI Backend consists of the following four core modules:

| Module | Directory | Description |
| :---- | :---- | :---- |
| **Account Management Service** | account\_backend | Responsible for user authentication (JWT), permission management, and account security. |
| **Simulation Service** | serve\_backend | Core engine, handling satellite data management and STK coverage simulation analysis. |
| **Visualization Service** | visual\_backend | Visualization platform built with Streamlit, supporting tile maps, trajectory display, and ADS-B / AIS global snapshot visualization. |
| **Data Synchronization** | timer.py, opensky\_timer.py, ais\_timer.py | Scheduled task scripts responsible for synchronizing satellite data from Celestrak API, plus ADS-B aircraft states and AIS vessel positions. |

## **🏗 Technical Architecture**

### **Directory Structure**

Space-MV ScAI Backend/  
├── account\_backend/          \# 🔐 Account management service  
│   ├── app.py                \# FastAPI application entry  
│   ├── configs/              \# Configuration management  
│   ├── controllers/          \# Route controllers  
│   ├── services/             \# Business logic layer  
│   ├── models/               \# Data models  
│   └── extensions/           \# Extension modules  
│  
├── serve\_backend/            \# 🛰️ Simulation service  
│   ├── app.py                \# FastAPI application entry  
│   ├── configs/              \# Configuration management  
│   ├── controllers/          \# Route controllers (satellites, constellations, sensors, simulation, LLM)  
│   ├── services/             \# Business logic layer  
│   ├── libs/                 \# Utility libraries (simulation report generation)  
│   └── output/               \# Simulation result output directory  
│  
├── visual\_backend/           \# 📊 Visualization service  
│   ├── app\_tiles.py          \# Streamlit application entry (with tile map)  
│   ├── app\_notiles.py        \# Streamlit application entry (without tile map)  
│   ├── app\_opensky.py        \# ADS-B global aircraft snapshot visualization entry  
│   ├── app\_ais.py            \# AIS global vessel snapshot visualization entry  
│   └── tiles/                \# Map tile service  
│       ├── cors\_server.py    \# CORS server  
│       └── gaode\_tiles/      \# Locally cached Gaode map tiles  
│  
├── stk\_scripts/              \# 🚀 STK invocation scripts  
│   ├── stk\_simulation.py     \# Coverage analysis execution script  
│   └── stk\_backprogress.py   \# Data processing function library  
│  
├── timer.py                  \# 🕒 Satellite data synchronization timer  
├── opensky_timer.py          \# ✈️ ADS-B data synchronization timer  
├── ais_timer.py              \# 🚢 AIS data synchronization timer  
├── requirements.txt          \# Project dependencies  
└── .env.example              \# Environment configuration example file

### Technology Stack

| Domain | Technology | Description |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | High-performance asynchronous web framework |
| | **Uvicorn** | ASGI server |
| | **Pydantic** | Data validation and configuration management |
| **Database** | **ClickHouse** | Stores massive satellite, constellation, and user data |
| **Visualization** | **Streamlit** | Rapid data application building |
| | **Plotly** | Interactive chart drawing |
| **Utility Components** | **Paramiko** | SSH client for remote STK invocation |
| | **APScheduler** | Scheduled task scheduling |
| | **STK Engine** | Satellite Tool Kit (requires separate license) |

### **Data Flow**

graph TD  
    A\[Celestrak API\] \--\>|Sync Data| B(timer.py Timer)  
    G\[OpenSky Network API\] \--\>|ADS-B Sync| H(opensky_timer.py Timer)  
    I\[AISStream WebSocket\] \--\>|AIS Sync| J(ais_timer.py Timer)  
    B \--\>|Write/Update| C\[(ClickHouse Database)\]  
    H \--\>|Write Snapshot| C  
    J \--\>|Write Batch| C  
    C \<--\>|Read/Write Data| D\[serve\_backend Simulation Service\]  
    C \--\>|Snapshot Query| E\[visual\_backend Visualization Service\]  
    D \--\>|Provide Data| E\[visual\_backend Visualization Service\]  
    E \--\>|Interactive Display| F\[User Interface\]

## **✨ Features**

### **1\. Account Management Service (account\_backend)**

**Port**: 5001

* 🔐 **Authentication Security**: Supports user registration, login, password encryption storage, and JWT token authentication.  
* 👤 **State Management**: Complete account lifecycle management.  
* **API**: /api/login, /api/accountAdd

### **2\. Simulation Service (serve\_backend)**

**Port**: 8401

* 🛰️ **Satellite and Constellation Management**: Supports CRUD operations for satellites/constellations, supports uploading custom constellation configurations.  
* 📡 **Sensor Management**: Configuration, query, and update of sensor parameters.  
* 🚀 **Simulation Execution**:  
  * Supports STK coverage analysis simulation (streaming output).  
  * **Hybrid Scheduling Mode**: Supports local execution or remote STK server task execution via SSH.  
  * Automatically generates simulation reports.  
* 🤖 **LLM Integration**: Integrated with Ollama, providing AI-based dialogue assistance.

### **3\. Visualization Service (visual\_backend)**

* 🌍 **2D Map Visualization**: Real-time rendering of satellite trajectories, sensor coverage envelopes, and target areas (points/lines/polygons).  
* 🗺️ **Tile Service**: Integrated custom or offline map tiles.  
* 📦 **Data Loading**: Supports automatic parsing and loading of simulation results from compressed packages or JSON.
* ✈️ **ADS-B Visualization**: Adds `app_opensky.py` for global aircraft snapshot display based on the `opensky` table, including UTC time slider selection, map point picking, and aircraft attribute inspection.  
* 🚢 **AIS Visualization**: Adds `app_ais.py` for global vessel snapshot display based on the `AIS` table, including batch time selection, map point picking, and vessel attribute inspection.  
* 🧭 **Dual Basemap Modes**: Both ADS-B and AIS pages support offline vector basemaps and local tile basemaps; when using local tiles, start `visual_backend/tiles/cors_server.py` first.  

### **4\. Data Synchronization (timer.py / opensky_timer.py / ais_timer.py)**

* Automatically retrieves the latest TLE data from Celestrak API.  
* Intelligently identifies and classifies constellations (GPS, Starlink, Beidou, etc.).  
* Automatically initializes database table structure and maintains data tables.
* ✈️ **ADS-B Synchronization (`opensky_timer.py`)**: Pulls global aircraft state vectors from OpenSky Network every hour, auto-creates the `opensky` table, and writes snapshot data; authenticated requests can be enabled with `OPENSKY_USERNAME` / `OPENSKY_PASSWORD`.  
* 🚢 **AIS Synchronization (`ais_timer.py`)**: Collects vessel position data from the AISStream WebSocket every hour, receives data continuously for 3 minutes per batch by default, keeps the latest record per vessel, and auto-creates the `AIS` table; `AISSTREAM_API_KEY` is required before enabling it.  

## **🚀 Quick Start**

### **Prerequisites**

* **Docker** (for deploying ClickHouse)  
* **STK Desktop (Windows) / STK Engine (Linux) 12.X**  
* Python environment with **STK agi package** configured
* Optional: **OpenSky Network account** (recommended for better ADS-B API availability)  
* Optional: **AISStream API Key** (required when enabling AIS synchronization)  

### **1. Environment Setup**
```bash
# Clone repository  
git clone https://github.com/tianxunweixiao/SpaceMV-ScAI-backend.git   
cd SpaceMV-ScAI-backend

# Create and activate Conda environment  
conda create -n scai python=3.12  
conda activate scai

# Install dependencies  
pip install -r requirements.txt
```
### **2. Initialize Database**
```bash
Start ClickHouse container and run synchronization script to initialize table structure and basic data:

# Start ClickHouse  
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

# Initialize data  
python timer.py
```

To enable the new ADS-B / AIS synchronization flows, start the following scripts separately. On first run they auto-create tables, perform one collection, and then enter hourly scheduling:

```bash
python opensky_timer.py
python ais_timer.py
```
### **3. Environment Variable Configuration**
```ini
Copy example file and modify configuration:

cp .env.example .env

Edit .env file, focus on configuring the following:

# ClickHouse Configuration  
CLICKHOUSE_HOST=your_clickhouse_host  
CLICKHOUSE_USER=your_user  
CLICKHOUSE_PASSWORD=your_password

# --- STK Simulation Configuration (Critical) ---  
# Mode A: Local Execution (STK and backend on same machine)  
STK_LOCAL=True  
STK_PYTHON_LOCAL_EXE=C:\Path\To\python.exe  
STK_SCRIPT_LOCAL_PATH=D:\Path\To\stk_simulation.py

# Mode B: Remote Execution (Call remote STK server via SSH)  
STK_LOCAL=False  
STK_PYTHON_REMOTE_EXE=C:\Path\To\Remote\python.exe  
STK_SCRIPT_REMOTE_PATH=C:\Path\To\Remote\stk_simulation.py  
REPLACE_BASE=C:\Path\To\Project  # Project base path on remote server  
SSH_HOST=xxx  
SSH_USER=xxx  
SSH_PASSWORD=xxxxx

# LLM Configuration (currently only supports ollama framework)  
OLLAMA_URL=http://your_ollama_host:11434/api/chat

# OpenSky ADS-B configuration (optional, enables authenticated requests)
OPENSKY_USERNAME=your_opensky_username
OPENSKY_PASSWORD=your_opensky_password

# AIS ingestion configuration (API key required for ais_timer.py)
AISSTREAM_API_KEY=your_aisstream_api_key
AIS_WS_URL=wss://stream.aisstream.io/v0/stream
AIS_BATCH_MINUTES=3
```
### **4. Start Services**
```bash
This project uses PM2 for process management:

# Install pm2  
npm install -g pm2

# Start all services  
pm2 start start_project.config.js

# View service status  
pm2 list
```

`start_project.config.js` currently starts the original services by default. The new ADS-B / AIS timers and visualization pages can be deployed separately as needed, for example:

```bash
python opensky_timer.py
python ais_timer.py

streamlit run visual_backend/app_opensky.py --server.headless true --server.port 8502
streamlit run visual_backend/app_ais.py --server.headless true --server.port 8503

# Required when local tile mode is used
python visual_backend/tiles/cors_server.py
```

For the SpaceMV-ScAI client repository, please refer to [SpaceMV-ScAI-frontend](https://github.com/tianxunweixiao/SpaceMV-ScAI-frontend)

## **📚 API Documentation**

After the service starts successfully, you can access the automatically generated interactive documentation:

* **Account Service**: [http://localhost:5001/docs](http://localhost:5001/docs)  
* **Simulation Service**: [http://localhost:8401/docs](http://localhost:8401/docs)

If the new visualization pages are started with the example ports above, you can access:

* **ADS-B Visualization**: [http://localhost:8502](http://localhost:8502)  
* **AIS Visualization**: [http://localhost:8503](http://localhost:8503)  

## **🔧 Troubleshooting**

| Issue | Possible Causes and Troubleshooting |
| :---- | :---- |
| **ClickHouse Connection Failure** | 1\. Check .env configuration. 2\. Confirm Docker container status (docker ps). 3\. Check if ports 8123/9000 are blocked by firewall. |
| **STK Simulation Failure** | 1\. Confirm if STK License is valid. 2\. If using remote mode, check SSH connectivity and REPLACE\_BASE path mapping. 3\. Verify if Python environment has agi.stk library correctly installed. |
| **No Data in Visualization** | 1\. Check if JSON files are generated in serve\_backend/output. 2\. Check browser F12 Console for parsing errors. |
| **No ADS-B Data** | 1\. Confirm `opensky_timer.py` is running. 2\. Check whether the `opensky` table exists in ClickHouse. 3\. If requests are rate-limited or empty, configure `OPENSKY_USERNAME` / `OPENSKY_PASSWORD` and retry later. |
| **No AIS Data** | 1\. Check whether `AISSTREAM_API_KEY` is configured correctly. 2\. Confirm `ais_timer.py` can reach `AIS_WS_URL`. 3\. Check whether the `AIS` table exists and whether the selected batch time window contains data. |
| **ADS-B / AIS Visualization Page Is Empty** | 1\. Confirm the corresponding Streamlit page is connected to the correct ClickHouse instance. 2\. Check whether the `opensky` / `AIS` tables already contain data. 3\. When using local tile mode, confirm `visual_backend/tiles/cors_server.py` is running. |

## **🤝 Contributing Guide**

We warmly welcome community developers to participate in the construction of SpaceMV-ScAI Backend! If you have any improvement suggestions or found bugs, please follow the following process:

1. **Fork this repository**: Click the Fork button in the upper right corner to copy the project to your GitHub account.  
2. **Create branch**: Create a new branch from main branch for development.  
   git checkout \-b feature/AmazingFeature  
3. **Commit changes**: Ensure code style is consistent and write clear Commit Message.  
   git commit \-m 'feat: Add some AmazingFeature'  
4. **Push branch**:  
   git push origin feature/AmazingFeature  
5. **Submit Pull Request**: Initiate PR on GitHub and describe your changes in detail.

**Development Suggestions**:

* When adding new APIs, please register routes in extensions/ext\_routers.py.  
* When adding new service logic, please follow the controller \-\> service \-\> model layered architecture.

## **📄 License**

This project is licensed under the **Apache License 2.0**.

Copyright (c) 2025 Chengdu Tianxun Microsatellite Technology Co., Ltd.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

## **📮 Contact**

If you have any questions, suggestions, or business cooperation needs, please contact the project maintenance team.

* **Email**: code@spacemv.com  
* **Issues**: [GitHub Issues](https://github.com/tianxunweixiao/SpaceMV-ScAI-backend/issues)

For more information, please follow the company's WeChat official account:

<img width="106" height="106" alt="image" src="https://github.com/user-attachments/assets/69a02ad0-422c-422a-bf5f-9b7890cf31ab" />


## ✅ Todo List

- [√] **Open Source Frontend Code**: Release the companion SpaceMV-ScAI-Frontend repository to implement a complete B/S architecture demonstration.
- [ ] **Intelligent Agent (Agent)**: Integrate AI Agent for automated constellation simulation task orchestration and scheduling.
- [ ] **Multi-constellation Support**: Add preset support for navigation constellations and communication constellations.
- [ ] **STK Interface Enhancement**: Expand API coverage to support more fine-grained simulation parameter configuration
- [ ] **Documentation Improvement**: Supplement detailed video tutorials and API interface use cases.
