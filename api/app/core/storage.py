import os
import re
from pathlib import Path
from uuid import UUID

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.core.config import settings

ALLOWED_MIME_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/mpeg"}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB

ALLOWED_MATERIAL_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}
MAX_MATERIAL_SIZE = 100 * 1024 * 1024  # 100 MB

# Filenames that must never be used (path traversal, special files)
_UNSAFE_PATTERNS = re.compile(r'(\.\.|//|\\|\x00|/\.|/\.\.)')


# ─── Backend selection ───

def _is_local_backend() -> bool:
    """True when STORAGE_BACKEND=local (development mode)."""
    return settings.STORAGE_BACKEND.lower() == "local"


def _local_storage_root() -> Path:
    """Return the root directory for local file storage."""
    base = Path(settings.STORAGE_LOCAL_DIR)
    if not base.is_absolute():
        # Resolve relative to the api/ directory (where the app runs from)
        base = Path(__file__).resolve().parent.parent.parent / base
    base.mkdir(parents=True, exist_ok=True)
    return base


def _local_file_path(storage_key: str) -> Path:
    """Resolve a storage_key to a local filesystem path, with traversal protection."""
    root = _local_storage_root()
    target = (root / storage_key).resolve()
    # Ensure the resolved path is within the storage root
    if not str(target).startswith(str(root)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid storage key",
        )
    return target


def _get_s3_client():
    """Retorna um cliente boto3 configurado para um storage S3-compatível."""
    config = Config(
        signature_version="s3v4",
    )
    return boto3.client(
        "s3",
        endpoint_url=settings.STORAGE_ENDPOINT or None,
        aws_access_key_id=settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.STORAGE_SECRET_KEY,
        region_name=settings.STORAGE_REGION,
        config=config,
    )


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe use in a storage key.

    Rejects path traversal, absolute paths, and unsafe components.
    Returns the basename with only safe characters.
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )
    # Reject path traversal attempts
    if _UNSAFE_PATTERNS.search(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsafe filename component detected",
        )
    # Strip any path components — keep only the basename
    filename = os.path.basename(filename)
    if not filename or filename in (".", ".."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:200] + ext
    return filename


def _key_for_lesson(lesson_id: UUID, filename: str) -> str:
    """Legacy key format for backward compatibility."""
    return f"lessons/{lesson_id!s}/{filename}"


def _tenant_key_for_video(
    tenant_id: UUID, course_id: UUID, lesson_id: UUID, filename: str
) -> str:
    """Tenant-aware storage key for lesson videos."""
    safe = _sanitize_filename(filename)
    return f"tenants/{tenant_id}/courses/{course_id}/lessons/{lesson_id}/video/{safe}"


def _tenant_key_for_material(
    tenant_id: UUID, course_id: UUID, lesson_id: UUID, filename: str
) -> str:
    """Tenant-aware storage key for lesson materials."""
    safe = _sanitize_filename(filename)
    return f"tenants/{tenant_id}/courses/{course_id}/lessons/{lesson_id}/materials/{safe}"


def _tenant_key_for_course_material(
    tenant_id: UUID, course_id: UUID, filename: str, sha256: str | None = None
) -> str:
    """Tenant-aware storage key for course-level materials (no lesson_id).

    Includes SHA-256 prefix for idempotency — re-uploading the same file
    produces the same key, preventing duplicate objects.
    """
    safe = _sanitize_filename(filename)
    if sha256:
        # Use first 16 chars of SHA to keep key manageable while ensuring uniqueness
        return f"tenants/{tenant_id}/courses/{course_id}/materials/{sha256[:16]}/{safe}"
    return f"tenants/{tenant_id}/courses/{course_id}/materials/{safe}"


def _is_legacy_key(key: str) -> bool:
    """Check if a storage key uses the legacy format."""
    return key.startswith("lessons/") and "/video/" not in key


# ─── Local storage helpers ───

def save_local_file(storage_key: str, file_data: bytes, content_type: str | None = None) -> None:
    """Save file bytes to the local storage directory."""
    path = _local_file_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_data)


def get_local_file_path(storage_key: str) -> Path:
    """Return the filesystem path for a storage key (for serving)."""
    return _local_file_path(storage_key)


def _local_upload_url(storage_key: str) -> str:
    """Build a backend URL for local-mode file upload (PUT)."""
    return f"{settings.API_BASE_URL}/api/v1/storage/upload"


def _local_serve_url(storage_key: str) -> str:
    """Build a backend URL for local-mode file serving (GET)."""
    return f"{settings.API_BASE_URL}/api/v1/storage/files/{storage_key}"


# ─── Video upload URL generation ───

async def generate_upload_url(
    lesson_id: UUID,
    filename: str,
    content_type: str = "video/mp4",
    content_length: int | None = None,
    expiration: int = 3600,
    tenant_id: UUID | None = None,
    course_id: UUID | None = None,
) -> tuple[str, str]:
    """Gera URL pré-assinada para upload direto de vídeo no storage.

    When tenant_id and course_id are provided, generates a tenant-aware key.
    Otherwise falls back to legacy key format.

    In local mode, returns a backend upload endpoint URL instead of an S3
    presigned URL. The client PUTs the file to this endpoint.
    """
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Content type not allowed: {content_type}",
        )

    if content_length is not None and content_length > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {MAX_UPLOAD_SIZE} bytes",
        )

    if tenant_id is not None and course_id is not None:
        key = _tenant_key_for_video(tenant_id, course_id, lesson_id, filename)
    else:
        key = _key_for_lesson(lesson_id, filename)

    if _is_local_backend():
        # Local mode: return backend upload endpoint URL
        return _local_upload_url(key), key

    # S3 mode
    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()

    try:
        params = {
            "Bucket": settings.STORAGE_BUCKET,
            "Key": key,
            "ContentType": content_type,
        }
        if content_length is not None:
            params["ContentLength"] = content_length
        url = s3.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate upload URL: {exc}",
        )

    return url, key


async def generate_watch_url(
    storage_key: str | None = None,
    lesson_id: UUID | None = None,
    filename: str | None = None,
    expiration: int | None = None,
) -> str:
    """Gera URL pré-assinada temporária para assistir o vídeo.

    Prefers using the stored storage_key directly. Falls back to
    reconstructing the legacy key from lesson_id + filename for
    backward compatibility with old records.
    """
    if storage_key:
        key = storage_key
    elif lesson_id and filename:
        key = _key_for_lesson(lesson_id, filename)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not uploaded yet",
        )

    if _is_local_backend():
        return _local_serve_url(key)

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()
    expires = expiration or settings.STORAGE_WATCH_URL_EXPIRATION

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.STORAGE_BUCKET,
                "Key": key,
            },
            ExpiresIn=expires,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate watch URL: {exc}",
        )

    return url


async def verify_object_exists(storage_key: str) -> bool:
    """Verify that an object exists in storage using head_object."""
    if _is_local_backend():
        path = _local_file_path(storage_key)
        return path.exists() and path.is_file()

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()
    try:
        s3.head_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
        return True
    except ClientError:
        return False


async def delete_object(storage_key: str) -> None:
    """Delete an object from storage."""
    if _is_local_backend():
        path = _local_file_path(storage_key)
        if path.exists() and path.is_file():
            path.unlink()
        return

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        return  # No storage configured, nothing to delete

    s3 = _get_s3_client()
    try:
        s3.delete_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
    except ClientError:
        pass  # Best-effort cleanup


async def generate_material_upload_url(
    tenant_id: UUID,
    course_id: UUID,
    lesson_id: UUID,
    filename: str,
    mime_type: str,
    size_bytes: int,
    expiration: int = 3600,
) -> tuple[str, str]:
    """Generate presigned URL for material upload with tenant-aware key."""
    if mime_type not in ALLOWED_MATERIAL_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Material content type not allowed: {mime_type}",
        )

    if size_bytes > MAX_MATERIAL_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Material size exceeds maximum of {MAX_MATERIAL_SIZE} bytes",
        )

    key = _tenant_key_for_material(tenant_id, course_id, lesson_id, filename)

    if _is_local_backend():
        return _local_upload_url(key), key

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()

    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.STORAGE_BUCKET,
                "Key": key,
                "ContentType": mime_type,
            },
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate material upload URL: {exc}",
        )

    return url, key


async def generate_material_download_url(
    storage_key: str,
    expiration: int | None = None,
) -> str:
    """Generate presigned URL for downloading a material."""
    if _is_local_backend():
        return _local_serve_url(storage_key)

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()
    expires = expiration or settings.STORAGE_WATCH_URL_EXPIRATION

    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.STORAGE_BUCKET,
                "Key": storage_key,
            },
            ExpiresIn=expires,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate download URL: {exc}",
        )

    return url


# ─── Course-level material storage (no lesson_id) ───

async def generate_course_material_upload_url(
    tenant_id: UUID,
    course_id: UUID,
    filename: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
    expiration: int = 3600,
) -> tuple[str, str]:
    """Generate presigned PUT URL for course-level material upload.

    Returns (upload_url, storage_key).
    The storage_key includes the SHA-256 prefix for idempotency.
    """
    if mime_type not in ALLOWED_MATERIAL_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Material content type not allowed: {mime_type}",
        )

    if size_bytes > MAX_MATERIAL_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Material size exceeds maximum of {MAX_MATERIAL_SIZE} bytes",
        )

    key = _tenant_key_for_course_material(tenant_id, course_id, filename, sha256)

    if _is_local_backend():
        return _local_upload_url(key), key

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()

    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.STORAGE_BUCKET,
                "Key": key,
                "ContentType": mime_type,
            },
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate course material upload URL: {exc}",
        )

    return url, key


async def head_object_metadata(storage_key: str) -> dict | None:
    """Get object metadata via head_object.

    Returns dict with 'content_length' and 'content_type' if the object
    exists, or None if it does not exist.
    """
    if _is_local_backend():
        path = _local_file_path(storage_key)
        if not (path.exists() and path.is_file()):
            return None
        import mimetypes
        stat = path.stat()
        return {
            "content_length": stat.st_size,
            "content_type": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
        }

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()
    try:
        response = s3.head_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
        return {
            "content_length": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
        }
    except ClientError:
        return None


def validate_storage_key_tenant_course(
    storage_key: str,
    tenant_id: UUID,
    course_id: UUID,
) -> bool:
    """Validate that a storage_key belongs to the given tenant and course.

    Prevents cross-tenant or cross-course key injection.
    """
    expected_prefix = f"tenants/{tenant_id}/courses/{course_id}/materials/"
    return storage_key.startswith(expected_prefix)
