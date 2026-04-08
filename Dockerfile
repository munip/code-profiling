# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================
# Supports: Python, Java, C++ profiling tasks
# Profilers: austin (Python/C++), async-profiler (Java)

FROM python:3.10-slim

ARG BUILD_VERSION=3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV BUILD_VERSION=${BUILD_VERSION}

WORKDIR /app

# Install system dependencies including austin
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    cmake \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Build and install austin (frame sampler for Python/C++)
RUN git clone --depth 1 https://github.com/nickparajon/austin.git /tmp/austin && \
    cd /tmp/austin && \
    make && \
    make install && \
    cd / && \
    rm -rf /tmp/austin

# Install async-profiler for Java
ENV ASYNC_PROFILER_HOME=/opt/async-profiler
RUN mkdir -p /opt/async-profiler && \
    curl -sL https://github.com/async-profiler/async-profiler/releases/download/v3.0/async-profiler-3.0-linux-x64.tar.gz | \
    tar -xz -C /opt/async-profiler --strip-components=1 && \
    chmod +x /opt/async-profiler/profiler.sh
ENV PATH=$PATH:/opt/async-profiler

# Install Python dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx austin-python py-spy openai pyyaml psutil

COPY environments/ ./environments/
COPY inference.py ./
COPY README.md ./
COPY pyproject.toml ./

RUN mkdir -p /app/profiles /app/logs

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
