#!/usr/bin/env bash
set -euo pipefail

ENTORNO="${1:-development}"

if [[ ! "$ENTORNO" =~ ^(development|staging|production)$ ]]; then
  echo "ERROR: Entorno inválido '$ENTORNO'. Usa: development | staging | production"
  exit 1
fi

echo "==> Deploy a '$ENTORNO' iniciado"

# Verificar config del entorno
CONFIG_DIR="config/$ENTORNO"
if [ ! -d "$CONFIG_DIR" ]; then
  echo "ERROR: No existe la carpeta de config '$CONFIG_DIR'"
  exit 1
fi

# Cargar variables de entorno
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Correr tests antes de deployar
echo "==> Verificando tests..."
./scripts/test.sh

# --- Agrega aquí tu lógica de deploy por entorno ---
case "$ENTORNO" in
  development)
    # Ejemplo: docker compose up -d
    echo "  Deploy local (development)"
    ;;
  staging)
    # Ejemplo: deploy a staging server
    echo "  Deploy staging"
    ;;
  production)
    echo "  Deploy production — confirma que tienes autorización"
    # Ejemplo: kubectl apply -f k8s/production/
    ;;
esac

echo "==> Deploy a '$ENTORNO' completado"
