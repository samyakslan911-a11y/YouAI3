FROM python:3.11-slim

# ffmpeg for video processing + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY . .

RUN mkdir -p output tmp credentials

EXPOSE 8000

# PORT is injected by Railway; falls back to 8000 for local docker run
CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}
