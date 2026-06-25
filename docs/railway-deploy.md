# Railway Deploy Guide

## Variables de entorno obligatorias

| Variable | Descripción |
|---|---|
| `GOOGLE_API_KEY` | Google AI Studio — gemini + análisis |
| `PEXELS_API_KEY` | Imágenes para slides (pexels.com/api) |
| `YOUTUBE_OAUTH_TOKEN_JSON` | JSON completo del token OAuth de YouTube |

## Variables opcionales

| Variable | Descripción | Default |
|---|---|---|
| `GEMINI_MODEL` | Modelo Gemini a usar | `gemini-2.5-flash` |
| `WHISPER_MODEL` | Tamaño del modelo de transcripción | `base` |
| `CHANNEL_HANDLE` | Handle del canal en slides | — |
| `INSTAGRAM_USERNAME` / `INSTAGRAM_PASSWORD` | Publicación a Instagram | — |
| `TIKTOK_COOKIES_FILE` | Ruta al JSON de cookies TikTok | `cookies/tiktok.json` |
| `YOUTUBE_COOKIES` | Contenido del archivo cookies.txt (anti-bot) | — |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` | Cloudflare R2 para URLs públicas | — |

## Configurar TikTok cookies

1. Instala la extensión **EditThisCookie** en Chrome.
2. Abre tiktok.com con sesión iniciada.
3. Click en EditThisCookie → Export → copia el JSON.
4. En Railway: agrega variable `TIKTOK_COOKIES_FILE` apuntando a `cookies/tiktok.json`
   y sube el JSON como archivo al contenedor, o pega el contenido en una variable
   `TIKTOK_COOKIES_JSON` y adapta el loader.

## Configurar YouTube OAuth

1. Corre localmente: `python scripts/setup_youtube.py`
2. Completa el flujo OAuth en el browser.
3. Lee el archivo generado: `credentials/youtube_oauth.json`
4. En Railway: crea la variable `YOUTUBE_OAUTH_TOKEN_JSON` y pega el contenido JSON completo.

El servidor detecta `YOUTUBE_OAUTH_TOKEN_JSON` (Railway) primero;
si no existe, usa `YOUTUBE_CREDENTIALS` (ruta local).

## Nota sobre WHISPER_MODEL

| Modelo | RAM aprox. | Calidad |
|---|---|---|
| `base` | ~1 GB | Suficiente para clips cortos |
| `large-v3` | ~3 GB | Máxima precisión |

Railway Starter Plan tiene 512 MB. Para `large-v3` se necesita el plan Pro (8 GB).
Usar `base` o `small` en Railway si el plan es limitado.

## Playwright en Railway

El Dockerfile ya incluye `playwright install chromium --with-deps`.
No se necesita configuración extra. Las features `publish_instagram_playwright`
y `publish_tiktok` funcionarán automáticamente en el contenedor.
