FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    austin \
    austin-python \
    flask \
    gunicorn

COPY ./src /app/src

ENV PYTHONUNBUFFERED=1
ENV AUSTIN_ENABLED=true

EXPOSE 8080

CMD ["sh", "-c", "cd /app/src && python app.py"]
