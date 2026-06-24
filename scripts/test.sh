#!/usr/bin/env bash
set -euo pipefail

echo "==> Ejecutando tests..."
py -m pytest tests/ -v --tb=short

echo "==> Tests completados"
