"""
Cloudflare R2 storage service (S3-compatible).
Uploads clips, slides and thumbnails; returns public CDN URLs.
Falls back silently if R2 is not configured — local file serving still works.
"""
import logging, os
from pathlib import Path

log = logging.getLogger(__name__)

ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
ACCESS_KEY  = os.getenv("R2_ACCESS_KEY_ID", "")
SECRET_KEY  = os.getenv("R2_SECRET_ACCESS_KEY", "")
BUCKET      = os.getenv("R2_BUCKET", "youai3-media")
PUBLIC_URL  = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

_client = None


def _get_client():
    global _client
    if _client:
        return _client
    if not (ACCOUNT_ID and ACCESS_KEY and SECRET_KEY):
        return None
    import boto3
    _client = boto3.client(
        "s3",
        endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="auto",
    )
    return _client


def is_configured() -> bool:
    return bool(ACCOUNT_ID and ACCESS_KEY and SECRET_KEY)


def upload(local_path: Path, key: str, content_type: str = "video/mp4") -> str | None:
    """
    Upload a file to R2. Returns the public URL or None if R2 not configured.
    key format: "clips/filename.mp4" or "slides/slug/images/00.png"
    """
    client = _get_client()
    if not client:
        return None
    try:
        client.upload_file(
            str(local_path),
            BUCKET,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        url = f"{PUBLIC_URL}/{key}" if PUBLIC_URL else _presigned(client, key)
        log.info(f"R2 upload OK: {key} → {url}")
        return url
    except Exception as e:
        log.error(f"R2 upload failed ({key}): {e}")
        return None


def _presigned(client, key: str, expires: int = 3600 * 24 * 7) -> str:
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires,
    )


def public_url(key: str) -> str | None:
    if PUBLIC_URL:
        return f"{PUBLIC_URL}/{key}"
    client = _get_client()
    if not client:
        return None
    return _presigned(client, key)


def delete(key: str) -> bool:
    client = _get_client()
    if not client:
        return False
    try:
        client.delete_object(Bucket=BUCKET, Key=key)
        return True
    except Exception as e:
        log.error(f"R2 delete failed ({key}): {e}")
        return False


def upload_clip(clip_path: Path) -> str | None:
    """Upload a clip MP4 and return its URL."""
    return upload(clip_path, f"clips/{clip_path.name}", "video/mp4")


def upload_thumbnail(thumb_path: Path) -> str | None:
    return upload(thumb_path, f"clips/{thumb_path.name}", "image/jpeg")


def upload_slide_image(slug: str, filename: str, img_path: Path) -> str | None:
    return upload(img_path, f"slides/{slug}/images/{filename}", "image/png")


def upload_slide_video(slug: str, video_path: Path) -> str | None:
    return upload(video_path, f"slides/{slug}/video.mp4", "video/mp4")
