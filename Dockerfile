# syntax=docker/dockerfile:1
# The official Drama 3 source and uv.lock are vendored unchanged.
FROM node:22-bookworm-slim AS browser
WORKDIR /webui
COPY vendor/fish-speech/awesome_webui/package*.json ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci --include=dev --no-audit --no-fund
COPY vendor/fish-speech/awesome_webui/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.8.15 AS uv
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 \
    UV_PYTHON=python3.12 UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-dev python3.12-venv build-essential cmake git curl ca-certificates \
    ffmpeg libsndfile1 libsox-dev libasound2-dev portaudio19-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /bin/uv
WORKDIR /app/fish-speech
COPY vendor/fish-speech/ ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/build_ca > /tmp/build-ca.pem; \
      export SSL_CERT_FILE=/tmp/build-ca.pem; \
    fi; \
    uv sync --frozen --extra cu128 --no-dev --no-cache && \
    uv pip install --python .venv/bin/python --no-cache aiohttp==3.10.11 && \
    rm -f /tmp/build-ca.pem
ENV PATH="/app/fish-speech/.venv/bin:$PATH" \
    HF_HOME=/workspace/huggingface WEB_USERNAME=persona \
    MODEL_DIR=/workspace/checkpoints/drama-3 FISH_DRAMA3_FP8_EXPERTS=1
COPY --from=browser /webui/dist /app/fish-speech/awesome_webui/dist
COPY deploy/ /app/deploy/
# Imports and CLI parsing must work without a GPU or model download during build.
RUN python /app/deploy/check_runtime.py && python tools/api_server.py --help > /dev/null && \
    python -c "import aiohttp; from fish_speech.models.text2semantic.fish_omni.model import FishOmniModel"
EXPOSE 8080
HEALTHCHECK --interval=30s --start-period=30m --timeout=5s CMD curl -fsS http://127.0.0.1:8080/healthz || exit 1
CMD ["python", "/app/deploy/launch.py"]
