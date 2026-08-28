"""Pydantic schemas for the Central WR SSO receiver (LMS side)."""

from pydantic import BaseModel


class SsoCallbackRequest(BaseModel):
    """Frontend → LMS callback payload.

    The frontend receives ``code`` and ``state`` from the Central WR redirect
    and posts them here. The LMS backend then exchanges the code server-to-
    server with the Central WR backend.
    """

    code: str
    state: str
    target_application: str = "lms-wr-cursos"


class SsoCallbackResponse(BaseModel):
    """LMS → frontend response, same shape as the normal login endpoint."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
