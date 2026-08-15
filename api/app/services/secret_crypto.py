"""Criptografia simétrica para secrets de tenant (ex.: access tokens de
gateway de pagamento, chaves de API de terceiros).

Usa Fernet (AES-128-CBC + HMAC SHA-256) da biblioteca cryptography. A
chave é derivada da configuração TENANT_SECRET_ENCRYPTION_KEY (base64
de 32 bytes) ou, em desenvolvimento, da SECRET_KEY via SHA-256.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _resolve_key() -> bytes:
    """Retorna a chave Fernet (base64 de 32 bytes)."""
    raw = settings.TENANT_SECRET_ENCRYPTION_KEY
    if raw:
        return raw.encode("utf-8")
    # Fallback de desenvolvimento: deriva da SECRET_KEY.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plaintext: str) -> str:
    """Criptografa um texto plano e retorna o token Fernet em string."""
    if plaintext is None:
        return None
    f = Fernet(_resolve_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Descriptografa um token Fernet. Levanta ValueError se inválido."""
    if token is None:
        return None
    f = Fernet(_resolve_key())
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted secret") from exc
