FROM python:3.11-slim

# libcairo2: vector PDF output · fonts-dejavu: number glyphs · libgl/glib: opencv runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 fonts-dejavu-core libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # pykuwahara declares opencv-python (GUI build) as a dep; we already have headless
    && pip install --no-cache-dir --no-deps pykuwahara

COPY pbn_converter.py main.py ./

EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
