"""CNPJ helpers shared by corporate integration tests."""

import uuid


def _check_digit(digits: str, weights: tuple[int, ...]) -> int:
    remainder = sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 11
    return 0 if remainder < 2 else 11 - remainder


def make_valid_cnpj(seed: int | None = None) -> str:
    """Generate a mathematically valid, non-repeated 14-digit CNPJ."""
    rng = uuid.uuid4().int if seed is None else seed
    base = f"{rng % 10**12:012d}"
    if len(set(base)) == 1:
        base = base[:-1] + ("1" if base[-1] != "1" else "2")

    first = _check_digit(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = _check_digit(base + str(first), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return f"{base}{first}{second}"
