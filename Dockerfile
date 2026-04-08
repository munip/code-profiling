# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================
# Supports: Python, Java, C++ profiling with real profilers
# Profilers: austin (Python/C++), async-profiler (Java)

FROM python:3.10-slim

ARG BUILD_VERSION=9

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
    default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Download and install async-profiler for Java
ENV ASYNC_PROFILER_HOME=/opt/async-profiler
RUN mkdir -p /opt/async-profiler && \
    wget --timeout=120 --tries=2 https://github.com/async-profiler/async-profiler/releases/download/v3.0/async-profiler-3.0-linux-x64.tar.gz -O /tmp/async.tgz && \
    tar -xzf /tmp/async.tgz -C /opt/async-profiler --strip-components=1 && \
    chmod +x /opt/async-profiler/profiler.sh && \
    rm -f /tmp/async.tgz
ENV PATH=$PATH:/opt/async-profiler

# Download and install austin for Python/C++ profiling
RUN set +e; \
    wget --timeout=120 --tries=2 https://github.com/nickparajon/austin/releases/download/2.1.2/austin-2.1.2-x64.gz -O /tmp/austin.gz 2>/dev/null && \
    gunzip -f /tmp/austin.gz && \
    chmod +x /tmp/austin && \
    mv /tmp/austin /usr/local/bin/austin; \
    set -e

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx py-spy openai pyyaml psutil flask

COPY environments/ ./environments/
COPY inference.py ./
COPY README.md ./
COPY pyproject.toml ./

RUN mkdir -p /app/profiles /app/logs

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
