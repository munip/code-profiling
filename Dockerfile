# Minimal test Dockerfile
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn

RUN cat > app.py << 'EOF'
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from minimal app", "status": "ok", "endpoint": "/"}

@app.get("/health")
def health():
    return {"status": "healthy", "endpoint": "/health"}

@app.get("/test")
def test():
    return {"message": "test endpoint works!", "endpoint": "/test"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
EOF

EXPOSE 7860

CMD python app.py
