#!/usr/bin/env bash
set -euo pipefail

echo "==> Instalando dependencias Python..."
py -m pip install -r requirements.txt

echo "==> Instalando Playwright Chromium (para TikTok)..."
py -m playwright install chromium

echo "==> Build completado"
