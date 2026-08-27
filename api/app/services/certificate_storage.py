from __future__ import annotations

import hashlib
from uuid import UUID

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.storage import _get_s3_client, _is_local_backend, _local_file_path


def certificate_pdf_key(
    *,
    tenant_id: UUID,
    enrollment_id: UUID,
    certificate_number: str,
    version: int,
) -> str:
    safe_number = "".join(ch for ch in certificate_number if ch.isalnum() or ch in ("-", "_"))
    return (
        f"tenants/{tenant_id}/certificates/{enrollment_id}/"
        f"v{version}/{safe_number}.pdf"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def store_immutable_certificate_pdf(*, storage_key: str, pdf: bytes) -> str:
    """Persist certificate bytes without silently overwriting an existing PDF.

    A retry is idempotent only when the already stored bytes have the same
    SHA-256. A divergent object for the same immutable key is a hard error.
    """
    digest = sha256_bytes(pdf)
    if _is_local_backend():
        path = _local_file_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if sha256_bytes(existing) != digest:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Immutable certificate artifact already exists with different content",
                )
            return digest
        path.write_bytes(pdf)
        return digest

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Storage not configured")

    s3 = _get_s3_client()
    try:
        s3.put_object(
            Bucket=settings.STORAGE_BUCKET,
            Key=storage_key,
            Body=pdf,
            ContentType="application/pdf",
            Metadata={"sha256": digest, "immutable": "true"},
            IfNoneMatch="*",
        )
        return digest
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"PreconditionFailed", "412"} or status_code == 412:
            existing = await load_certificate_pdf(storage_key=storage_key)
            if sha256_bytes(existing) == digest:
                return digest
            raise HTTPException(
                status_code=409,
                detail="Immutable certificate artifact already exists with different content",
            ) from exc
        raise HTTPException(status_code=500, detail="Could not persist certificate artifact") from exc


async def load_certificate_pdf(*, storage_key: str) -> bytes:
    if _is_local_backend():
        path = _local_file_path(storage_key)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Certificate artifact not found")
        return path.read_bytes()

    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Storage not configured")
    s3 = _get_s3_client()
    try:
        response = s3.get_object(Bucket=settings.STORAGE_BUCKET, Key=storage_key)
        return response["Body"].read()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            raise HTTPException(status_code=404, detail="Certificate artifact not found") from exc
        raise HTTPException(status_code=500, detail="Could not read certificate artifact") from exc


async def verify_certificate_pdf(*, storage_key: str, expected_sha256: str) -> bytes:
    pdf = await load_certificate_pdf(storage_key=storage_key)
    actual = sha256_bytes(pdf)
    if actual != expected_sha256:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate integrity verification failed",
        )
    return pdf
