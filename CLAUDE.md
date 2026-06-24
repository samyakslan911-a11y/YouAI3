# CLAUDE.md — Instrucciones Maestras del Proyecto

## Sobre este proyecto

> Edita esta sección cuando definas el stack y propósito del proyecto.

**Nombre:** workspace  
**Stack:** Por definir  
**Entorno principal:** desarrollo local

---

## Estructura del proyecto

```
src/core/        → Lógica de negocio pura (sin dependencias de framework)
src/api/         → Controladores, rutas, handlers
src/services/    → Integraciones externas (DB, APIs de terceros, colas)
src/utils/       → Helpers reutilizables sin estado
tests/unit/      → Tests de funciones individuales
tests/integration/ → Tests que cruzan capas (ej. API + DB)
tests/e2e/       → Tests de flujo completo
config/          → Variables de configuración por entorno
scripts/         → Automatización de build, test y deploy
docs/            → Documentación técnica
```

---

## Convenciones de código

- Nombrado en `camelCase` para funciones/variables, `PascalCase` para clases/tipos
- Sin comentarios a menos que el WHY sea no obvio
- Sin abstracciones prematuras — tres líneas similares antes de extraer una función
- Validar solo en los bordes del sistema (input de usuario, APIs externas)
- No agregar manejo de errores para escenarios imposibles

---

## Sub-agentes disponibles

| Agente | Cuándo usarlo |
|--------|--------------|
| `coder` | Implementar features, escribir código nuevo, refactorizar |
| `debugger` | Encontrar bugs, correr tests, validar antes de merge |
| `deployer` | Build, release, deploy a cualquier entorno |

Para lanzar los 3 en paralelo, usa el Agent tool con `run_in_background: true` en los 3 simultáneamente.

---

## Comandos principales

```bash
# Desarrollo
./scripts/build.sh

# Tests
./scripts/test.sh

# Deploy
./scripts/deploy.sh [development|staging|production]
```

---

## Variables de entorno

Copia `.env.example` a `.env` y completa los valores antes de ejecutar.  
**Nunca commites `.env` al repositorio.**

---

## Flujo de trabajo recomendado

1. `coder` → implementa la feature en `src/`
2. `debugger` → valida con tests y revisa edge cases
3. `deployer` → construye y despliega cuando todo está verde
