# Code Profiler Environment - Unified Container
# ============================================
# Single container with all profiling environments:
# - Python (Flask API)
# - Java (ECommerceAPI + async-profiler)
# - C++ (ecommerce_api)
# - OpenEnv FastAPI server

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app

# Install all system dependencies in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    cmake \
    make \
    g++ \
    openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        fastapi \
        uvicorn \
        pydantic \
        httpx \
        austin \
        austin-python \
        py-spy \
        openai \
        flask \
        gunicorn \
    && rm -rf /root/.cache/pip

# Install async-profiler
RUN mkdir -p /opt/async-profiler && \
    curl -sL https://github.com/async-profiler/async-profiler/releases/download/v4.3/async-profiler-4.3-linux-x64.tar.gz | \
    tar -xz -C /opt/async-profiler --strip-components=1

# Create directories
RUN mkdir -p /app/profiles /app/logs /app/java_src /app/cpp_src /app/java_classes

# Copy source files
COPY environments/code_profiler_env/server/python/src/app.py /app/python_api.py
COPY environments/code_profiler_env/server/java/src /app/java_src
COPY environments/code_profiler_env/server/cpp/src /app/cpp_src
COPY environments/code_profiler_env/server/cpp/CMakeLists.txt /app/cpp_src/

# Build Java and C++ in one layer
RUN cd /app/java_src && find . -name "*.java" -exec javac -d /app/java_classes {} + 2>/dev/null || true && \
    cd /app/cpp_src && mkdir -p build && cd build && cmake .. && make

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
