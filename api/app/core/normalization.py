"""Centralized normalization and validation helpers for identity fields.

Single source of truth for email, CPF and CNPJ normalization/validation used by
authentication, registration, password recovery, activation and corporate
flows. Reusing these helpers guarantees consistent identity handling and
prevents malformed Brazilian document identifiers from being silently stored.

Strict document format contracts
--------------------------------
CPF accepts only:

1. Exactly 11 digits: ``52998224725``
2. Canonical formatted CPF: ``529.982.247-25``

CNPJ accepts only:

1. Exactly 14 digits: ``04252011000110``
2. Canonical formatted CNPJ: ``04.252.011/0001-10``

Optional surrounding whitespace is stripped. Any other input is rejected.
"""

import re

# CPF: exactly 11 digits (raw form).
_CPF_RAW_RE = re.compile(r"^\d{11}$")
# CPF: canonical formatted form DDD.DDD.DDD-DD
_CPF_FORMATTED_RE = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
# CNPJ: exactly 14 digits (raw form).
_CNPJ_RAW_RE = re.compile(r"^\d{14}$")
# CNPJ: canonical formatted form DD.DDD.DDD/DDDD-DD
_CNPJ_FORMATTED_RE = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
# Simple email format check (Pydantic EmailStr handles strict validation).
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# CPF check-digit weight tables.
_CPF_FIRST_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2)
_CPF_SECOND_WEIGHTS = (11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
# CNPJ check-digit weight tables.
_CNPJ_FIRST_WEIGHTS = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_SECOND_WEIGHTS = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)

# All-equal-digit documents are invalid even when check digits happen to match.
_INVALID_REPEATED_CPFS = {str(d) * 11 for d in range(10)}
_INVALID_REPEATED_CNPJS = {str(d) * 14 for d in range(10)}


def normalize_email(email: str) -> str:
    """Normalize an email address: strip whitespace and lowercase.

    Returns the normalized email. Raises ValueError if the input is empty.
    """
    if not email or not isinstance(email, str):
        raise ValueError("email cannot be empty")
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("email cannot be empty")
    return normalized


def normalize_cpf(cpf: str) -> str:
    """Normalize a CPF to its canonical 11-digit form.

    Accepts only raw 11 digits or canonical ``DDD.DDD.DDD-DD`` formatting.
    Does not validate check digits; use :func:`validate_cpf` for that.
    """
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
    """Normalize a CNPJ to its canonical 14-digit storage form.

    Accepts only raw 14 digits or canonical ``DD.DDD.DDD/DDDD-DD`` formatting.
    Does not validate check digits; use :func:`validate_cnpj` for that.
    """
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
    """True when the identifier is a valid CPF *format* (not mathematics)."""
    if not identifier or not isinstance(identifier, str):
        return False
    stripped = identifier.strip()
    if not stripped:
        return False
    if _CPF_RAW_RE.match(stripped):
        return True
    return bool(_CPF_FORMATTED_RE.match(stripped))


def is_cnpj_format(identifier: str) -> bool:
    """True when the identifier is a valid CNPJ *format* (not mathematics)."""
    if not identifier or not isinstance(identifier, str):
        return False
    stripped = identifier.strip()
    if not stripped:
        return False
    if _CNPJ_RAW_RE.match(stripped):
        return True
    return bool(_CNPJ_FORMATTED_RE.match(stripped))


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
    """Mathematically validate a Brazilian CPF and return the normalized form."""
    try:
        digits = normalize_cpf(cpf)
    except ValueError:
        raise ValueError("CPF inválido") from None

    if len(digits) != 11:
        raise ValueError("CPF deve conter exatamente 11 dígitos")

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
    """Mathematically validate a Brazilian CNPJ and return 14 raw digits.

    Validation is intentionally strict: only raw 14 digits or canonical
    formatted CNPJ input is accepted, repeated digits are rejected, and both
    verifier digits must match the official modulus-11 calculation.
    """
    try:
        digits = normalize_cnpj(cnpj)
    except ValueError:
        raise ValueError("CNPJ inválido") from None

    if len(digits) != 14 or digits in _INVALID_REPEATED_CNPJS:
        raise ValueError("CNPJ inválido")

    first_check = _compute_check_digit(digits[:12], _CNPJ_FIRST_WEIGHTS)
    if int(digits[12]) != first_check:
        raise ValueError("CNPJ inválido")

    second_check = _compute_check_digit(digits[:13], _CNPJ_SECOND_WEIGHTS)
    if int(digits[13]) != second_check:
        raise ValueError("CNPJ inválido")

    return digits


def is_valid_cpf(cpf: str) -> bool:
    """Boolean wrapper around :func:`validate_cpf` for convenience."""
    try:
        validate_cpf(cpf)
    except ValueError:
        return False
    return True


def is_valid_cnpj(cnpj: str) -> bool:
    """Boolean wrapper around :func:`validate_cnpj` for convenience."""
    try:
        validate_cnpj(cnpj)
    except ValueError:
        return False
    return True
