# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies directly
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx

# Copy application code
COPY environments/ ./environments/
COPY inference.py ./

RUN mkdir -p /app/profiles /app/logs

EXPOSE 7860

# Run the app
CMD ["python", "-m", "uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "${PORT}"]
