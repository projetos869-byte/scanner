# API Scanner OCR — imagem para rodar em Docker / Render
FROM python:3.11-slim-bookworm

WORKDIR /app

# Tesseract OCR + idioma português; libs para OpenCV (headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1-mesa-glx \
    libsm6 \
    libxext6 \
    libxrender1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python: usar opencv-python-headless no container (menor, sem GUI)
COPY requirements.txt .
RUN sed -i 's/opencv-python/opencv-python-headless/' requirements.txt \
    && pip install --no-cache-dir -r requirements.txt

# Código da API e do scanner
COPY main.py .
COPY scanner/ ./scanner/
COPY web/ ./web/

# Porta (Render injeta PORT em runtime; padrão 8000)
ENV PORT=8000
EXPOSE 8000

# Executar a API
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
