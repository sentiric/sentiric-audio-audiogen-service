FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV HF_HUB_DISABLE_PROGRESS_BARS=1
ENV TOKENIZERS_PARALLELISM=false
ENV PYTHONUNBUFFERED=1

# Sistem paketleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip python3-venv curl git ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# UV (Hızlı paket yöneticisi)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Sanal ortam
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN uv venv $VIRTUAL_ENV --python /usr/bin/python3.10

# Bağımlılıklar - STABİL SÜRÜMLER (Torch 2.5.1 + CUDA 12.4)
COPY requirements.txt .

# Önce ağır paketleri kur (Timeout riskini azaltmak için ayrı katman)
RUN uv pip install --no-cache \
    torch==2.5.1 \
    torchvision==0.20.1 \
    torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

# Diğer servis bağımlılıkları
RUN uv pip install --no-cache -r requirements.txt

COPY . .

# Güvenlik ve Klasör Yapısı
RUN mkdir -p /app/model-cache && \
    addgroup --system --gid 1001 appgroup && \
    adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser
ENV HF_HOME="/app/model-cache"

EXPOSE 16320 16321

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 16320 --no-access-log"]