"""
Canva Connect API — OAuth PKCE + design autofill.
Single-user flow: authorize once → store tokens in env vars → auto-refresh.
"""
import base64
import hashlib
import logging
import os
import secrets
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

CANVA_CLIENT_ID     = os.getenv("CANVA_CLIENT_ID", "")
CANVA_CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET", "")
CANVA_REDIRECT_URI  = os.getenv(
    "CANVA_REDIRECT_URI",
    "https://youai3-production.up.railway.app/api/canva/callback",
)

_API   = "https://api.canva.com/rest/v1"
_AUTH  = "https://www.canva.com/api/oauth/authorize"
_TOKEN = "https://api.canva.com/rest/v1/oauth/token"

SCOPES = (
    "design:content:read design:content:write "
    "asset:read asset:write "
    "brandtemplate:content:read"
)

# Template IDs for the 4 milokira templates (set after Brand Templates are configured in Canva)
TEMPLATE_IDS = {
    "t1_cover":   os.getenv("CANVA_TEMPLATE_T1", ""),
    "t2_guide":   os.getenv("CANVA_TEMPLATE_T2", ""),
    "t3_species": os.getenv("CANVA_TEMPLATE_T3", ""),
    "t4_cta":     os.getenv("CANVA_TEMPLATE_T4", ""),
}

# In-memory PKCE store (single-user app, one flow at a time)
_pkce_store: dict[str, str] = {}


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_auth_url() -> str:
    """Build PKCE authorization URL. Returns the URL to redirect the user to."""
    code_verifier  = _b64url(secrets.token_bytes(32))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())
    state          = secrets.token_urlsafe(16)
    _pkce_store[state] = code_verifier

    params = "&".join([
        f"client_id={CANVA_CLIENT_ID}",
        "response_type=code",
        f"redirect_uri={CANVA_REDIRECT_URI}",
        f"scope={SCOPES.replace(' ', '%20')}",
        f"code_challenge={code_challenge}",
        "code_challenge_method=S256",
        f"state={state}",
    ])
    return f"{_AUTH}?{params}"


def exchange_code(code: str, state: str) -> dict:
    """Exchange auth code for access + refresh tokens."""
    code_verifier = _pkce_store.pop(state, None)
    if not code_verifier:
        raise ValueError(f"Unknown OAuth state: {state}")

    resp = httpx.post(_TOKEN, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "code_verifier": code_verifier,
        "client_id":     CANVA_CLIENT_ID,
        "client_secret": CANVA_CLIENT_SECRET,
        "redirect_uri":  CANVA_REDIRECT_URI,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _refresh(refresh_token: str) -> dict:
    resp = httpx.post(_TOKEN, data={
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     CANVA_CLIENT_ID,
        "client_secret": CANVA_CLIENT_SECRET,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── API client ────────────────────────────────────────────────────────────────

class CanvaClient:
    """Single-user Canva Connect API client with auto token refresh."""

    def __init__(self):
        self._access  = os.getenv("CANVA_ACCESS_TOKEN", "")
        self._refresh = os.getenv("CANVA_REFRESH_TOKEN", "")
        self._expires = float(os.getenv("CANVA_TOKEN_EXPIRES_AT", "0"))

    def store_tokens(self, tokens: dict):
        self._access  = tokens["access_token"]
        self._refresh = tokens.get("refresh_token", self._refresh)
        self._expires = time.time() + tokens.get("expires_in", 3600)

    def _ensure(self):
        if time.time() < self._expires - 60:
            return
        if not self._refresh:
            raise RuntimeError(
                "No Canva token — visit /api/canva/authorize to authenticate"
            )
        log.info("Refreshing Canva access token")
        self.store_tokens(_refresh(self._refresh))

    def _h(self, extra: dict | None = None) -> dict:
        self._ensure()
        h = {"Authorization": f"Bearer {self._access}"}
        if extra:
            h.update(extra)
        return h

    # ── Brand templates ───────────────────────────────────────────────────────

    def get_brand_template(self, template_id: str) -> dict:
        """Get a specific brand template by ID."""
        r = httpx.get(f"{_API}/brandtemplates/{template_id}", headers=self._h(), timeout=15)
        r.raise_for_status()
        return r.json()

    # ── Assets ────────────────────────────────────────────────────────────────

    def upload_asset(self, image_path: Path, name: str) -> str:
        """Upload a PNG/JPG to Canva library. Returns asset_id."""
        data = image_path.read_bytes()
        r = httpx.post(
            f"{_API}/assets",
            headers=self._h({"Asset-Name": name}),
            content=data,
            timeout=30,
        )
        r.raise_for_status()
        job_id = r.json()["job"]["id"]
        return self._wait_asset(job_id)

    def _wait_asset(self, job_id: str) -> str:
        for _ in range(20):
            time.sleep(1.5)
            r = httpx.get(f"{_API}/assets/upload/{job_id}", headers=self._h(), timeout=10)
            r.raise_for_status()
            job = r.json().get("job", {})
            if job.get("status") == "success":
                return job["asset"]["id"]
            if job.get("status") == "failed":
                raise RuntimeError(f"Canva asset upload failed: {job}")
        raise TimeoutError("Canva asset upload timed out")

    # ── Autofill ──────────────────────────────────────────────────────────────

    def autofill_template(self, template_id: str, title: str, data: dict) -> str:
        """
        Autofill a Brand Template. Returns design_id.

        `data` keys must match the field names set up in Canva:
          {"headline": {"type":"text","text":"..."}, "plant_photo": {"type":"image","asset_id":"..."}}
        """
        r = httpx.post(
            f"{_API}/brandtemplates/{template_id}/autofill",
            headers=self._h({"Content-Type": "application/json"}),
            json={"title": title, "data": data},
            timeout=30,
        )
        r.raise_for_status()
        job_id = r.json()["job"]["id"]
        return self._wait_autofill(job_id)

    def _wait_autofill(self, job_id: str) -> str:
        for _ in range(30):
            time.sleep(2)
            r = httpx.get(
                f"{_API}/brandtemplates/autofill/{job_id}",
                headers=self._h(), timeout=10,
            )
            r.raise_for_status()
            job = r.json().get("job", {})
            if job.get("status") == "success":
                return job["design"]["id"]
            if job.get("status") == "failed":
                raise RuntimeError(f"Canva autofill failed: {job}")
        raise TimeoutError("Canva autofill timed out")

    # ── Export ────────────────────────────────────────────────────────────────

    def export_png_urls(self, design_id: str) -> list[str]:
        """Export all pages of a design as PNG. Returns list of download URLs."""
        r = httpx.post(
            f"{_API}/exports",
            headers=self._h({"Content-Type": "application/json"}),
            json={"design_id": design_id, "format": "png", "pages": ["all"]},
            timeout=30,
        )
        r.raise_for_status()
        job_id = r.json()["job"]["id"]
        return self._wait_export(job_id)

    def _wait_export(self, job_id: str) -> list[str]:
        for _ in range(40):
            time.sleep(2)
            r = httpx.get(f"{_API}/exports/{job_id}", headers=self._h(), timeout=10)
            r.raise_for_status()
            job = r.json().get("job", {})
            if job.get("status") == "success":
                return job.get("urls", [])
            if job.get("status") == "failed":
                raise RuntimeError(f"Canva export failed: {job}")
        raise TimeoutError("Canva export timed out")

    # ── High-level: render one slide via Canva ────────────────────────────────

    def render_slide(
        self,
        template_key: str,
        title: str,
        fields: dict,
        photo_path: Path | None,
        out_path: Path,
    ) -> Path:
        """
        Autofill a Brand Template and download the PNG to out_path.
        template_key: "t1_cover" | "t2_guide" | "t3_species" | "t4_cta"
        fields: text fields dict (without plant_photo — handled separately)
        """
        template_id = TEMPLATE_IDS.get(template_key, "")
        if not template_id:
            raise RuntimeError(
                f"CANVA_TEMPLATE_{template_key.upper().split('_')[0]}"
                f"{template_key.upper().split('_')[1]} not set in env"
            )

        data = {k: {"type": "text", "text": v} for k, v in fields.items()}

        if photo_path and photo_path.exists():
            asset_id = self.upload_asset(photo_path, f"plant_{title}")
            data["plant_photo"] = {"type": "image", "asset_id": asset_id}

        design_id = self.autofill_template(template_id, title, data)
        urls       = self.export_png_urls(design_id)

        if not urls:
            raise RuntimeError("Canva returned no export URLs")

        png_data = httpx.get(urls[0], timeout=30).content
        out_path.write_bytes(png_data)
        log.info(f"Canva slide saved: {out_path}")
        return out_path


# Singleton
canva = CanvaClient()
