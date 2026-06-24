# workspace

> Describe aquí el propósito del proyecto.

## Inicio rápido

```bash
# 1. Configura variables de entorno
cp .env.example .env

# 2. Build
./scripts/build.sh

# 3. Tests
./scripts/test.sh

# 4. Deploy
./scripts/deploy.sh development
```

## Estructura

```
src/core/       → Lógica de negocio
src/api/        → Capa API
src/services/   → Integraciones externas
src/utils/      → Helpers
tests/          → Unit, Integration, E2E
config/         → Configuración por entorno
scripts/        → Automatización
docs/           → Documentación
```

## Sub-agentes Claude Code

Este proyecto incluye 3 agentes especializados en `.claude/agents/`:

| Agente | Función |
|--------|---------|
| `coder` | Escribe e implementa código |
| `debugger` | Caza errores y valida tests |
| `deployer` | Build y deploy |
