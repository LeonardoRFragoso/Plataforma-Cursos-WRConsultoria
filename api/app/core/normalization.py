"""Centralized normalization and validation helpers for identity fields.

Single source of truth for email and CPF normalization/validation used by
authentication, registration, password recovery, activation and corporate
employee creation. Reusing these helpers guarantees that the same person can
safely exist in multiple tenants (WR + Alfa) without ambiguity, because every
lookup and duplicate check compares normalized values.

Strict CPF format contract
--------------------------
Only two input shapes are accepted as CPF:

1. Exactly 11 digits: ``52998224725``
2. Canonical formatted CPF: ``529.982.247-25``

Optional surrounding whitespace is stripped. Any other input (letters,
extra symbols, partial formatting, slashes, plus signs, etc.) is rejected.
This prevents arbitrary garbage like ``abc52998224725xyz`` from being
silently reduced to a valid 11-digit CPF.
"""

import re

# CPF: exactly 11 digits (raw form).
_CPF_RAW_RE = re.compile(r"^\d{11}$")
# CPF: canonical formatted form DDD.DDD.DDD-DD
_CPF_FORMATTED_RE = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
# Simple email format check (Pydantic EmailStr handles strict validation).
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# CPF check-digit weight tables.
_CPF_FIRST_WEIGHTS = (10, 9, 8, 7, 6, 5, 4, 3, 2)
_CPF_SECOND_WEIGHTS = (11, 10, 9, 8, 7, 6, 5, 4, 3, 2)

# All-equal-digit CPFs are invalid even when check digits happen to match.
_INVALID_REPEATED_CPFS = {str(d) * 11 for d in range(10)}


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

    Accepts only:
    - Exactly 11 digits (e.g. ``52998224725``)
    - Canonical formatted CPF (e.g. ``529.982.247-25``)

    Surrounding whitespace is stripped. Any other input raises ValueError.

    Does NOT validate check digits — use :func:`validate_cpf` for that.
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


def is_cpf_format(identifier: str) -> bool:
    """True when the identifier is a valid CPF *format* (not mathematics).

    Only accepts:
    - Exactly 11 digits
    - Canonical formatted CPF ``DDD.DDD.DDD-DD``

    Returns False for arbitrary strings that merely contain 11 digits
    embedded in other characters (e.g. ``abc52998224725xyz``).
    """
    if not identifier or not isinstance(identifier, str):
        return False
    stripped = identifier.strip()
    if not stripped:
        return False
    if _CPF_RAW_RE.match(stripped):
        return True
    return bool(_CPF_FORMATTED_RE.match(stripped))


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
    """Mathematically validate a Brazilian CPF and return the normalized form.

    Performs:
    - strict format validation (only raw 11 digits or canonical formatted);
    - exactly 11 digits after normalization;
    - rejection of all-equal-digit sequences (00000000000, 11111111111, ...);
    - validation of both check digits (verifying digits).

    Returns the normalized 11-digit CPF string on success.

    Raises ValueError with a user-friendly message on any validation failure.
    """
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


def is_valid_cpf(cpf: str) -> bool:
    """Boolean wrapper around :func:`validate_cpf` for convenience."""
    try:
        validate_cpf(cpf)
    except ValueError:
        return False
    return True
