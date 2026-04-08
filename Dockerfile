# Code Profiler Environment - Unified Container
# ============================================
# Single container with all profiling environments:
# - Python (Flask API + austin)
# - Java (ECommerceAPI + async-profiler)
# - C++ (ecommerce_api + austin)
# - OpenEnv FastAPI server

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV ASYNC_PROFILER_HOME=/opt/async-profiler
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH=$PATH:/opt/async-profiler

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    cmake \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Java JDK 17
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
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

# Install async-profiler for Java
RUN mkdir -p /opt/async-profiler && \
    curl -L https://github.com/async-profiler/async-profiler/releases/download/v4.3/async-profiler-4.3-linux-x64.tar.gz | \
    tar -xz -C /opt/async-profiler --strip-components=1

# Create directories
RUN mkdir -p /app/profiles /app/logs /app/java_src /app/cpp_src /app/java_classes

# Copy Python API
COPY environments/code_profiler_env/server/python/src/app.py /app/python_api.py

# Copy Java source
COPY environments/code_profiler_env/server/java/src /app/java_src
RUN cd /app/java_src && find . -name "*.java" -exec javac -d /app/java_classes {} + 2>/dev/null || true

# Copy C++ source
COPY environments/code_profiler_env/server/cpp/src /app/cpp_src
COPY environments/code_profiler_env/server/cpp/CMakeLists.txt /app/cpp_src/
RUN cd /app/cpp_src && mkdir -p build && cd build && cmake .. && make

# Copy OpenEnv environment
COPY environments/code_profiler_env /app/environments/code_profiler_env

# Copy inference script
COPY inference.py /app/

# Copy README
COPY README.md /app/

# Copy pyproject.toml
COPY pyproject.toml /app/

# Copy start_apis and profile_runner
COPY environments/code_profiler_env/server/start_apis.py /app/
COPY environments/code_profiler_env/server/profile_runner.py /app/

# Install austin for C++ profiling (need to build from source or use available version)
# Note: austin requires Frame Pointer bit - using py-spy as fallback

EXPOSE 7860

# Start the OpenEnv server - APIs will be started by start_apis.py
CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
