# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================
# Supports: Python, Java, C++ profiling tasks (simulated)
# Note: Real profiling falls back to simulated when tools unavailable

FROM python:3.10-slim

ARG BUILD_VERSION=6

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV BUILD_VERSION=${BUILD_VERSION}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx py-spy openai pyyaml psutil flask

COPY environments/ ./environments/
COPY inference.py ./
COPY README.md ./
COPY pyproject.toml ./

RUN mkdir -p /app/profiles /app/logs

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
