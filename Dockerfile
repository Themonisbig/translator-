# syntax=docker/dockerfile:1
FROM node:20.19.0-bookworm-slim AS browser
WORKDIR /client
COPY vendor/personaplex/client/package*.json ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci --include=dev --no-audit --no-fund && test -x node_modules/.bin/tsc
COPY vendor/personaplex/client/ ./
RUN npm run build

# Ampere/Ada/Hopper path matching upstream torch >=2.2,<2.5; not Blackwell.
FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus-dev libportaudio2 build-essential ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY vendor/personaplex/moshi/ /app/moshi/
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/build_ca > /tmp/build-ca.pem; \
      export PIP_CERT=/tmp/build-ca.pem; \
    fi; \
    pip install --no-cache-dir /app/moshi && pip check && python -m moshi.server --help > /dev/null && rm -f /tmp/build-ca.pem
COPY --from=browser /client/dist /app/client/dist
COPY deploy/ /app/deploy/
ENV HF_HOME=/workspace/huggingface PYTHONUNBUFFERED=1 WEB_USERNAME=persona
EXPOSE 8080
HEALTHCHECK --interval=30s --start-period=20m --timeout=5s CMD curl -fsS http://127.0.0.1:8080/healthz || exit 1
CMD ["python", "/app/deploy/launch.py"]
