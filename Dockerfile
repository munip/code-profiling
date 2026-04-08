# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx austin-python py-spy openai

COPY environments/ ./environments/
COPY inference.py ./

RUN mkdir -p /app/profiles /app/logs

EXPOSE 7860

CMD python -m uvicorn environments.code_profiler_env.server.app:app --host 0.0.0.0 --port $PORT
