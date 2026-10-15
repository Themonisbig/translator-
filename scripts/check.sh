#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
npm ci --prefix vendor/personaplex/client --no-audit --no-fund
npm run build --prefix vendor/personaplex/client
