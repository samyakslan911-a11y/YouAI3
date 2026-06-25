"""
Cloudflare R2 storage service (S3-compatible).
Uploads clips, slides and thumbnails; returns public CDN URLs.
Falls back silently if R2 is not configured — local file serving still works.
"""
import logging, os
from pathlib import Path

log = logging.getLogger(__name__)

_client = None


def _creds() -> tuple[str, str, str, str, str]:
    """Read R2 credentials lazily so Railway env vars set after import are picked up."""
    return (
        os.getenv("R2_ACCOUNT_ID", ""),
        os.getenv("R2_ACCESS_KEY_ID", ""),
        os.getenv("R2_SECRET_ACCESS_KEY", ""),
        os.getenv("R2_BUCKET", "youai3-media"),
        os.getenv("R2_PUBLIC_URL", "").rstrip("/"),
    )


def _get_client():
    global _client
    if _client:
        return _client
    account_id, access_key, secret_key, _, _ = _creds()
    if not (account_id and access_key and secret_key):
        return None
    import boto3
    from botocore.config import Config
    _client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
    )
    return _client


def is_configured() -> bool:
    account_id, access_key, secret_key, _, _ = _creds()
    return bool(account_id and access_key and secret_key)


def upload(local_path: Path, key: str, content_type: str = "video/mp4") -> str | None:
    """
    Upload a file to R2. Returns the public URL or None if R2 not configured.
    key format: "clips/filename.mp4" or "slides/slug/images/00.png"
    """
    client = _get_client()
    if not client:
        return None
    _, _, _, bucket, public_url = _creds()
    try:
        client.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        url = f"{public_url}/{key}" if public_url else _presigned(client, key, bucket)
        log.info(f"R2 upload OK: {key} → {url}")
        return url
    except Exception as e:
        log.error(f"R2 upload failed ({key}): {e}")
        return None


def _presigned(client, key: str, bucket: str, expires: int = 3600 * 24 * 7) -> str:
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def public_url(key: str) -> str | None:
    _, _, _, _, pub = _creds()
    if pub:
        return f"{pub}/{key}"
    client = _get_client()
    if not client:
        return None
    _, _, _, bucket, _ = _creds()
    return _presigned(client, key, bucket)


def delete(key: str) -> bool:
    client = _get_client()
    if not client:
        return False
    _, _, _, bucket, _ = _creds()
    try:
        client.delete_object(Bucket=bucket, Key=key)
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
