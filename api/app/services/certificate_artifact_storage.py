from __future__ import annotations

from uuid import UUID

from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.storage import _get_s3_client, _is_local_backend, _local_file_path, delete_object


PDF_CONTENT_TYPE = "application/pdf"


def certificate_artifact_key(
    *,
    tenant_id: UUID,
    certificate_id: UUID,
    sha256: str,
    signed: bool,
) -> str:
    kind = "signed" if signed else "original"
    return (
        f"tenants/{tenant_id}/certificates/{certificate_id}/"
        f"{kind}/{sha256}.pdf"
    )


async def store_certificate_pdf(
    *,
    tenant_id: UUID,
    certificate_id: UUID,
    pdf_bytes: bytes,
    sha256: str,
    signed: bool,
) -> str:
    """Persist exact PDF bytes and return their immutable storage key."""
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Certificate artifact must be a non-empty PDF")

    key = certificate_artifact_key(
        tenant_id=tenant_id,
        certificate_id=certificate_id,
        sha256=sha256,
        signed=signed,
    )
    if _is_local_backend():
        path = _local_file_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf_bytes)
        return key

    if (
        not settings.STORAGE_ENDPOINT
        or not settings.STORAGE_ACCESS_KEY
        or not settings.STORAGE_SECRET_KEY
    ):
        raise RuntimeError("Storage not configured")

    try:
        _get_s3_client().put_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=key,
            Body=pdf_bytes,
            ContentType=PDF_CONTENT_TYPE,
            Metadata={"sha256": sha256},
        )
    except ClientError as exc:
        raise RuntimeError("Could not persist certificate artifact") from exc
    return key


async def load_certificate_pdf(storage_key: str) -> bytes:
    """Load the exact stored artifact bytes for hashing/download."""
    if _is_local_backend():
        path = _local_file_path(storage_key)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(storage_key)
        return path.read_bytes()

    if (
        not settings.STORAGE_ENDPOINT
        or not settings.STORAGE_ACCESS_KEY
        or not settings.STORAGE_SECRET_KEY
    ):
        raise RuntimeError("Storage not configured")

    try:
        response = _get_s3_client().get_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=storage_key,
        )
        return response["Body"].read()
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise FileNotFoundError(storage_key) from exc
        raise RuntimeError("Could not load certificate artifact") from exc


async def remove_certificate_pdf(storage_key: str | None) -> None:
    if storage_key:
        await delete_object(storage_key)
