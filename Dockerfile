# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================
# Supports: Python, Java, C++ profiling with real profilers
# Profilers: austin (Python/C++), async-profiler (Java)

FROM python:3.10-slim

ARG BUILD_VERSION=6

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV BUILD_VERSION=${BUILD_VERSION}

WORKDIR /app

# Install system dependencies and Java
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    build-essential \
    cmake \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Download and install austin (pre-built binary for Linux x64)
RUN wget -q https://github.com/nickparajon/austin/releases/download/2.1.2/austin-2.1.2-x64.gz && \
    gunzip austin-2.1.2-x64.gz && \
    chmod +x austin-2.1.2-x64 && \
    mv austin-2.1.2-x64 /usr/local/bin/austin && \
    rm -f austin-2.1.2-x64.gz

# Download and install async-profiler for Java
ENV ASYNC_PROFILER_HOME=/opt/async-profiler
RUN mkdir -p /opt/async-profiler && \
    wget -q https://github.com/async-profiler/async-profiler/releases/download/v3.0/async-profiler-3.0-linux-x64.tar.gz && \
    tar -xzf async-profiler-3.0-linux-x64.tar.gz -C /opt/async-profiler --strip-components=1 && \
    chmod +x /opt/async-profiler/profiler.sh && \
    rm -f async-profiler-3.0-linux-x64.tar.gz
ENV PATH=$PATH:/opt/async-profiler

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx py-spy openai pyyaml psutil flask

COPY environments/ ./environments/
COPY inference.py ./
COPY README.md ./
COPY pyproject.toml ./

RUN mkdir -p /app/profiles /app/logs

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
