#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
npm ci --prefix vendor/fish-speech/awesome_webui --no-audit --no-fund
npm run build --prefix vendor/fish-speech/awesome_webui
