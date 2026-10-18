#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image_repo=ghcr.io/themonisbig/personaplex-voice
image_sha="${IMAGE_SHA:-$(git rev-parse HEAD)}"
build_mode=--load
if [ "${PUBLISH_IMAGE:-false}" = true ]; then build_mode=--push; fi
# Build logs contain no HF/RunPod secrets: none are supplied during image builds.
if docker buildx build --progress plain "$build_mode" \
  --label org.opencontainers.image.source=https://github.com/Themonisbig/translator- \
  -t "$image_repo:main" -t "$image_repo:$image_sha" . > /tmp/fish-image-build.log 2>&1; then
  tail -20 /tmp/fish-image-build.log
else
  build_status=$?
  tail -80 /tmp/fish-image-build.log
  if [ "${GITHUB_ACTIONS:-false}" = true ]; then
    python3 - <<'PYANNOTATION'
from pathlib import Path
lines = Path('/tmp/fish-image-build.log').read_text(errors='replace').splitlines()
message = '\n'.join(lines[-65:])[-12000:]
message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
print('::error title=Container build diagnostic::' + message)
PYANNOTATION
  fi
  exit "$build_status"
fi
