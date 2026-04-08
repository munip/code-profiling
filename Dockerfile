# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================

FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml ./


# Copy application code
COPY envir
onments/ ./environments/
COPY inference.py ./
COPY README.md ./


# Copy server application
COPY environments/code_profiler_env/server/app.py ./environments/code_profiler_env/server/app.py
COPY environments/code_profiler_env/models.py ./environments/code_profiler_env/models.py


# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create profiles directory
RUN mkdir -p /app/profiles /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
