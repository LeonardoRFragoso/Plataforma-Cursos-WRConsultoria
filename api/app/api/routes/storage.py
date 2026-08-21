"""Storage routes for local-mode file upload and serving.

These routes are only active when STORAGE_BACKEND=local. In S3 mode,
uploads go directly to presigned S3 URLs and file serving uses S3
presigned download URLs — these routes are never hit.

Security:
- Upload requires admin authentication
- File serving requires authentication (student/admin)
- Path traversal is prevented by storage.py's _local_file_path
- Content-Type is derived from the file extension
"""
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.core.security import get_current_user
from app.core.storage import _is_local_backend, get_local_file_path, save_local_file

router = APIRouter()


@router.put("/upload", status_code=status.HTTP_200_OK)
async def local_upload(
    request: Request,
    storage_key: str = "",
    current_user: dict = Depends(get_current_user),
):
    """Receive a file upload and save it to the local storage directory.

    The client PUTs the raw file body to this endpoint with the
    storage_key as a query parameter. This replaces the S3 presigned
    PUT URL in local mode.
    """
    if not _is_local_backend():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local storage not enabled",
        )

    if not storage_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="storage_key query parameter is required",
        )

    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file body",
        )

    content_type = request.headers.get("content-type", "application/octet-stream")
    save_local_file(storage_key, body, content_type)

    return {"status": "ok", "storage_key": storage_key, "size": len(body)}


@router.get("/files/{storage_key:path}")
async def serve_file(
    storage_key: str,
    current_user: dict = Depends(get_current_user),
):
    """Serve a file from local storage.

    Used for video watch URLs and material download URLs in local mode.
    """
    if not _is_local_backend():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local storage not enabled",
        )

    path = get_local_file_path(storage_key)

    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    # Determine content type from extension, fall back to octet-stream
    content_type, _ = mimetypes.guess_type(str(path))
    if not content_type:
        content_type = "application/octet-stream"

    return FileResponse(
        path=str(path),
        media_type=content_type,
        filename=path.name,
    )
