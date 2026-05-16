FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-dev python3-pip python3-venv \
    libsndfile1 curl git ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
RUN ln -s /usr/bin/python3.10 /usr/bin/python

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN uv venv $VIRTUAL_ENV --python /usr/bin/python3.10

COPY requirements.txt .

# Önce ML paketleri (Cache dostu)
RUN uv pip install --no-cache \
    torch==2.5.1 \
    torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

# Geri kalanı
RUN uv pip install --no-cache -r requirements.txt

COPY . .

# Klasör yapılandırması ve yetkiler
RUN mkdir -p /app/model-cache && \
    addgroup --system --gid 1001 appgroup && \
    adduser --system --no-create-home --uid 1001 --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app && \
    chmod -R 777 /app/model-cache

USER appuser
ENV HF_HOME="/app/model-cache"

EXPOSE 16320 16321

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 16320 --no-access-log"]