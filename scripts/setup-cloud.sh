#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Barcode
python -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
npm ci --prefix frontend --cache /tmp/barcode-npm-cache
npm run build --prefix frontend
.venv/bin/python -m pytest -q
