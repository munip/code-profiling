# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================
# Supports: Python, Java, C++ profiling with real profilers (async-profiler for Java, austin for Python/C++)
# Profilers: austin (Python/C++), async-profiler (Java)

FROM python:3.10-slim

ARG BUILD_VERSION=2

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV BUILD_VERSION=${BUILD_VERSION}

WORKDIR /app

# Install system dependencies and Java
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    cmake \
    default-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-downloaded profilers (downloaded locally via profilers/download.sh)
# This avoids network issues during Docker build in HF Spaces
COPY profilers/async-profiler/ /tmp/async-profiler/
COPY profilers/austin /usr/local/bin/austin
RUN chmod +x /tmp/async-profiler/profiler.sh 2>/dev/null || true && \
    chmod +x /tmp/async-profiler/converter/*.so 2>/dev/null || true && \
    chmod +x /usr/local/bin/austin
ENV ASYNC_PROFILER_HOME=/tmp/async-profiler
ENV PATH="/usr/local/bin:${PATH}"

# Copy project files from root
COPY __init__.py ./
COPY client.py ./
COPY models.py ./
COPY rl_loop_runner.py ./
COPY server/ ./server/
COPY openenv.yaml ./
COPY pyproject.toml ./
COPY uv.lock ./
COPY inference.py ./
COPY README.md ./

# Copy templates
COPY environments/code_profiler_env/templates/ ./server/templates/

# Install Python dependencies (uvicorn, fastapi, flask, etc.)
RUN pip install --no-cache-dir uvicorn fastapi pydantic httpx pyyaml psutil openenv-core flask

# Create directories
RUN mkdir -p /app/profiles /app/logs /app/server/python/src \
    /app/server/java/src/com/ecommerce/api \
    /app/server/cpp/src /app/server/cpp/build \
    /app/java_classes

# Copy Python source
COPY environments/code_profiler_env/templates/python/app.py /app/server/python/src/app.py

# Copy Java source
COPY environments/code_profiler_env/templates/java/ECommerceAPI.java /app/server/java/src/com/ecommerce/api/ECommerceAPI.java

# Copy C++ source
COPY environments/code_profiler_env/templates/cpp/main.cpp /app/server/cpp/src/main.cpp

# Compile Java (needs to be run from src/ to match package structure)
RUN cd /app/server/java/src && javac -d /app/java_classes com/ecommerce/api/ECommerceAPI.java && \
    echo "Java compiled successfully" || echo "Java compilation failed"

# Verify Java class file exists
RUN if [ -f /app/java_classes/com/ecommerce/api/ECommerceAPI.class ]; then \
        echo "Java class file verified: /app/java_classes/com/ecommerce/api/ECommerceAPI.class"; \
    else \
        echo "ERROR: Java class file NOT found!"; \
        exit 1; \
    fi

# Compile C++
RUN g++ -O0 -o /app/server/cpp/build/ecommerce_api /app/server/cpp/src/main.cpp && \
    echo "C++ compiled successfully" || echo "C++ compilation failed"

# Verify C++ binary exists
RUN if [ -f /app/server/cpp/build/ecommerce_api ]; then \
        echo "C++ binary verified: /app/server/cpp/build/ecommerce_api"; \
        ls -la /app/server/cpp/build/ecommerce_api; \
    else \
        echo "ERROR: C++ binary NOT found!"; \
        exit 1; \
    fi

# Initialize git repo for code versioning (required for commit_performance_fix)
RUN git config --global user.email "profiler@hfspaces.app" && \
    git config --global user.name "Code Profiler" && \
    git init && \
    git add -A && \
    git commit -m "v1-baseline: initial code ready for profiling"

EXPOSE 7860

CMD ["python", "-c", "import sys; sys.path.insert(0, '/app'); sys.path.insert(0, '/app/server'); from server.app import app, main; main()"]
