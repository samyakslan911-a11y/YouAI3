"""
Configura las credenciales OAuth2 para publicar en YouTube.

Uso:
    python scripts/setup_youtube.py

Requisitos previos:
    1. Ve a https://console.cloud.google.com
    2. Crea un proyecto (o usa el existente de AI Studio)
    3. Activa la YouTube Data API v3:
       APIs & Services > Enable APIs > busca "YouTube Data API v3" > Enable
    4. Crea credenciales OAuth2:
       APIs & Services > Credentials > Create Credentials > OAuth client ID
       - Application type: Desktop app
       - Descarga el JSON y guárdalo como: credentials/youtube_client_secrets.json
    5. Corre este script: python scripts/setup_youtube.py
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_FILE = BASE_DIR / "credentials" / "youtube_client_secrets.json"
TOKEN_FILE = BASE_DIR / "credentials" / "youtube_oauth.json"


def main():
    if not SECRETS_FILE.exists():
        print(f"ERROR: No se encontró {SECRETS_FILE}")
        print("\nSigue estos pasos:")
        print("1. Ve a https://console.cloud.google.com")
        print("2. Activa YouTube Data API v3")
        print("3. Crea credenciales OAuth2 (Desktop app)")
        print(f"4. Descarga el JSON y guárdalo en: {SECRETS_FILE}")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("Instalando dependencias...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "google-auth-oauthlib", "google-api-python-client"], check=True)
        from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",   # para listar tus videos
        "https://www.googleapis.com/auth/yt-analytics.readonly",  # para Analytics API
    ]

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("Abriendo navegador para autenticación con Google...")
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json())
    print(f"\nCredenciales guardadas en: {TOKEN_FILE}")
    print("Ya puedes publicar en YouTube con el pipeline.")


if __name__ == "__main__":
    main()
