FROM python:3.11-slim

# ffmpeg for video processing + curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Download OpenCV DNN face detector model at build time (~10MB)
RUN mkdir -p /tmp/cv_face && \
    curl -fsSL "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt" \
         -o /tmp/cv_face/deploy.prototxt && \
    curl -fsSL "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel" \
         -o /tmp/cv_face/res10_300x300_ssd_iter_140000.caffemodel

COPY . .

RUN mkdir -p output tmp credentials

EXPOSE 8000

# PORT is injected by Railway; falls back to 8000 for local docker run
CMD uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}
