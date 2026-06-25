# ── Stage 1: system deps + Python wheels ──────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-prod.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim

# Runtime system deps only (no build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy Python wheels from builder
COPY --from=builder /install /usr/local

# Download OpenCV DNN face detector model at build time (~10MB)
# Pinned to opencv/4.x branch for stability
RUN mkdir -p /tmp/cv_face && \
    curl -fsSL "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/dnn/face_detector/deploy.prototxt" \
         -o /tmp/cv_face/deploy.prototxt && \
    curl -fsSL "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel" \
         -o /tmp/cv_face/res10_300x300_ssd_iter_140000.caffemodel

WORKDIR /app
COPY . .

RUN mkdir -p output tmp credentials

EXPOSE 8000

# PORT is injected by Railway; falls back to 8000 for local docker run
CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}
