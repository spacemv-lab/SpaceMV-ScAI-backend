FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 安装系统依赖（增加了 sshpass）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    git \
    curl \
    vim \
    openssh-client \
    sshpass \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 关键：配置 SSH 环境，防止自动化脚本卡在 "yes/no" 的主机指纹确认环节
RUN mkdir -p ~/.ssh && \
    echo "Host *\n\tStrictHostKeyChecking no\n\tUserKnownHostsFile /dev/null" > ~/.ssh/config && \
    chmod 400 ~/.ssh/config

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt

# 使用清华源加速 pip 升级和依赖安装
RUN python -m pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install -r /tmp/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy source for local development/debugging in container.
COPY . /workspace

# Common service ports in this repository:
# - account_backend: 5001
# - serve_backend: 8401
# - visual_backend (streamlit): 8501
EXPOSE 5001 8401 8501

# NOTE: stk_scripts imports agi.stk12.* and requires AGI STK runtime separately.
CMD ["bash"]