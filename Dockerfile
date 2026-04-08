# Code Profiler Environment - Unified Container
# ============================================
# Single container with all profiling environments:
# - Python (Flask API)
# - Java (ECommerceAPI + async-profiler)  
# - C++ (pre-built binary)
# - OpenEnv FastAPI server

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV ASYNC_PROFILER_HOME=/opt/async-profiler
ENV JAVA_HOME=/opt/java/openjdk

WORKDIR /app

# Install system dependencies (minimal for profiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pydantic \
    httpx \
    py-spy \
    openai \
    flask \
    gunicorn \
    && rm -rf /root/.cache/pip

# Install async-profiler for Java
RUN mkdir -p /opt/async-profiler && \
    curl -sL https://github.com/async-profiler/async-profiler/releases/download/v4.3/async-profiler-4.3-linux-x64.tar.gz | \
    tar -xz -C /opt/async-profiler --strip-components=1

# Create directories
RUN mkdir -p /app/profiles /app/logs /app/java_src /app/cpp_src /app/java_classes

# Copy Python API
COPY environments/code_profiler_env/server/python/src/app.py /app/python_api.py

# Copy Java source
COPY environments/code_profiler_env/server/java/src /app/java_src

# Copy C++ binary (pre-built for faster builds)
COPY environments/code_profiler_env/server/cpp/src/main.cpp /app/cpp_src/
COPY environments/code_profiler_env/server/cpp/CMakeLists.txt /app/cpp_src/

# Build Java
RUN cd /app/java_src && find . -name "*.java" -exec javac -d /app/java_classes {} + 2>/dev/null || true

# Build C++ (minimal build)
RUN apt-get update && apt-get install -y --no-install-recommends cmake make g++ && \
    cd /app/cpp_src && mkdir -p build && cd build && cmake .. && make && \
    apt-get remove -y cmake make g++ && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Copy OpenEnv environment
COPY environments/code_profiler_env /app/environments/code_profiler_env

# Copy application files
COPY inference.py /app/
COPY README.md /app/
COPY pyproject.toml /app/

# Copy server modules
COPY environments/code_profiler_env/server/start_apis.py /app/environments/code_profiler_env/server/
COPY environments/code_profiler_env/server/profile_runner.py /app/environments/code_profiler_env/server/

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
