"""Centralized normalization and validation helpers for identity fields.

Single source of truth for email, CPF and CNPJ normalization/validation used
throughout authentication, contracting, corporate onboarding and payments.
"""

import re

# CPF: exactly 11 digits (raw form) or canonical formatted form.
_CPF_RAW_RE = re.compile(r"^\d{11}$")
_CPF_FORMATTED_RE = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
# CNPJ: exactly 14 digits (raw form) or canonical formatted form.
_CNPJ_RAW_RE = re.compile(r"^\d{14}$")
_CNPJ_FORMATTED_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
# Simple email format check (Pydantic EmailStr handles strict validation).
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_CPF_FIRST_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2)
_CPF_SECOND_WEIGHTS = (11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_FIRST_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_SECOND_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

_INVALID_REPEATED_CPFS = {str(d) * 11 for d in range(10)}
_INVALID_REPEATED_CNPJS = {str(d) * 14 for d in range(10)}


def normalize_email(email: str) -> str:
    """Normalize an email address to trimmed lowercase."""
    if not email or not isinstance(email, str):
        raise ValueError("email cannot be empty")
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("email cannot be empty")
    return normalized


def normalize_cpf(cpf: str) -> str:
    """Normalize a CPF to 11 digits, accepting only canonical input shapes."""
    if not cpf or not isinstance(cpf, str):
        raise ValueError("cpf cannot be empty")
    stripped = cpf.strip()
    if not stripped:
        raise ValueError("cpf cannot be empty")
    if _CPF_RAW_RE.match(stripped):
        return stripped
    if _CPF_FORMATTED_RE.match(stripped):
        return stripped.replace(".", "").replace("-", "")
    raise ValueError("cpf must be 11 digits or formatted as DDD.DDD.DDD-DD")


def normalize_cnpj(cnpj: str) -> str:
    """Normalize a CNPJ to 14 digits, accepting only canonical input shapes."""
    if not cnpj or not isinstance(cnpj, str):
        raise ValueError("cnpj cannot be empty")
    stripped = cnpj.strip()
    if not stripped:
        raise ValueError("cnpj cannot be empty")
    if _CNPJ_RAW_RE.match(stripped):
        return stripped
    if _CNPJ_FORMATTED_RE.match(stripped):
        return stripped.replace(".", "").replace("/", "").replace("-", "")
    raise ValueError("cnpj must be 14 digits or formatted as DD.DDD.DDD/DDDD-DD")


def is_cpf_format(identifier: str) -> bool:
    """Return True when identifier has a supported CPF representation."""
    if not identifier or not isinstance(identifier, str):
        return False
    stripped = identifier.strip()
    return bool(_CPF_RAW_RE.match(stripped) or _CPF_FORMATTED_RE.match(stripped))


def is_cnpj_format(identifier: str) -> bool:
    """Return True when identifier has a supported CNPJ representation."""
    if not identifier or not isinstance(identifier, str):
        return False
    stripped = identifier.strip()
    return bool(_CNPJ_RAW_RE.match(stripped) or _CNPJ_FORMATTED_RE.match(stripped))


def is_email_format(identifier: str) -> bool:
    """True when the identifier looks like an email address."""
    if not identifier:
        return False
    return bool(_EMAIL_RE.match(identifier.strip()))


def _compute_check_digit(digits: str, weights: tuple[int, ...]) -> int:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    remainder = total % 11
    if remainder < 2:
        return 0
    return 11 - remainder


def validate_cpf(cpf: str) -> str:
    """Mathematically validate a Brazilian CPF and return 11 normalized digits."""
    try:
        digits = normalize_cpf(cpf)
    except ValueError:
        raise ValueError("CPF inválido") from None

    if digits in _INVALID_REPEATED_CPFS:
        raise ValueError("CPF inválido")

    first_check = _compute_check_digit(digits[:9], _CPF_FIRST_WEIGHTS)
    if int(digits[9]) != first_check:
        raise ValueError("CPF inválido")

    second_check = _compute_check_digit(digits[:10], _CPF_SECOND_WEIGHTS)
    if int(digits[10]) != second_check:
        raise ValueError("CPF inválido")

    return digits


def validate_cnpj(cnpj: str) -> str:
    """Mathematically validate a Brazilian CNPJ and return 14 normalized digits."""
    try:
        digits = normalize_cnpj(cnpj)
    except ValueError:
        raise ValueError("CNPJ inválido") from None

    if digits in _INVALID_REPEATED_CNPJS:
        raise ValueError("CNPJ inválido")

    first_check = _compute_check_digit(digits[:12], _CNPJ_FIRST_WEIGHTS)
    if int(digits[12]) != first_check:
        raise ValueError("CNPJ inválido")

    second_check = _compute_check_digit(digits[:13], _CNPJ_SECOND_WEIGHTS)
    if int(digits[13]) != second_check:
        raise ValueError("CNPJ inválido")

    return digits


def is_valid_cpf(cpf: str) -> bool:
    """Boolean wrapper around :func:`validate_cpf`."""
    try:
        validate_cpf(cpf)
    except ValueError:
        return False
    return True


def is_valid_cnpj(cnpj: str) -> bool:
    """Boolean wrapper around :func:`validate_cnpj`."""
    try:
        validate_cnpj(cnpj)
    except ValueError:
        return False
    return True
