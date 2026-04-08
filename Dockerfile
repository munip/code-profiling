# Code Profiler Environment - HuggingFace Spaces Dockerfile
# ==========================================================

FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY pyproject.toml ./
COPY README.md ./
COPY environments/ ./environments/
COPY inference.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create profiles directory
RUN mkdir -p /app/profiles /app/logs

# Expose port (HF Spaces default is 7860)
EXPOSE 7860

# Run the application
CMD ["uvicorn", "environments.code_profiler_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
