FROM python:3.13-slim

RUN apt-get update && apt-get install -y ca-certificates curl git unzip libopus0 ffmpeg nodejs npm \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && deno --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY bot.py link_security.py music_worker.mjs package.json ./
ENV PYTHONPATH=/app \
    NODE_MUSIC_WORKER_URL=http://127.0.0.1:8787
CMD ["sh", "-c", "node music_worker.mjs & exec python -u bot.py"]
