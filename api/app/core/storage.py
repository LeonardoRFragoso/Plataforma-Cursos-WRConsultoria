import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from uuid import UUID

from app.core.config import settings


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


def _key_for_lesson(lesson_id: UUID, filename: str) -> str:
    """Gera a chave do objeto no bucket para uma aula."""
    return f"lessons/{str(lesson_id)}/{filename}"


async def generate_upload_url(
    lesson_id: UUID,
    filename: str,
    content_type: str = "video/mp4",
    expiration: int = 3600,
) -> tuple[str, str]:
    """Gera URL pré-assinada para upload direto de vídeo no storage."""
    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()
    key = _key_for_lesson(lesson_id, filename)

    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.STORAGE_BUCKET,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expiration,
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate upload URL: {exc}",
        )

    return url, key


async def generate_watch_url(
    lesson_id: UUID,
    filename: str,
    expiration: int = None,
) -> str:
    """Gera URL pré-assinada temporária para assistir o vídeo."""
    if not settings.STORAGE_ENDPOINT or not settings.STORAGE_ACCESS_KEY or not settings.STORAGE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )

    s3 = _get_s3_client()
    key = _key_for_lesson(lesson_id, filename)
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
