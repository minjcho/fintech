FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Prophet
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV UVICORN_WORKERS=4

EXPOSE 8002

# Use exec form with sh -c for proper signal handling (SIGTERM)
# This ensures graceful shutdown when container stops
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers ${UVICORN_WORKERS}"]