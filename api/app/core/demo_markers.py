"""Shared demo markers — single source of truth for demo data detection.

This module centralizes all markers used to distinguish demo/homologation
records from real business records. Every runtime component that needs to
classify a record as demo MUST import from here, never define its own
constants.

MARKER CATEGORIES:

1. Certificate prefixes — certificate_number starts with a known demo prefix.
2. Email domains — user email domain matches a known demo domain.
   Matching is exact or subdomain (``*.<domain>``), case-insensitive.
3. Class locations — class.location matches a known demo location exactly.

HISTORICAL MARKERS:

The following markers originate from the homologation migration
``a0b1c2d3e4f5_enroll_demo_student_in_uploaded_courses`` and the
``seed_white_label_demo`` script. They are immutable historical artifacts
and must remain recognized forever:

- Email domain ``wr.demo`` (from migration DEMO_EMAIL = "aluno2@wr.demo"
  and seed script aluno1@wr.demo / aluno2@wr.demo)
- Email domain ``alfa.demo`` (from seed script aluno1@alfa.demo /
  aluno2@alfa.demo)
- Class location ``DEMO-EAD-ASSESSMENT`` (from migration CLASS_LOCATION)
- Class location ``DEMO-EAD`` (from seed_white_label_demo._DEMO_CLASS_LOCATION)

CURRENT MARKERS:

- Email domain ``demo.local`` (from create_demo_certificate.py)
- Class location ``DEMO-CERT-EAD`` (from create_demo_certificate.py)
- Class location ``DEMO-EAD-NR1`` (from course_content.py route)
- Certificate prefix ``DEMO-`` (universal demo certificate marker)

SAFETY:

- Class location matching is EXACT only. Never use ``startswith("DEMO")``
  to avoid false positives from future business locations that happen to
  start with "DEMO".
- Email domain matching is exact or subdomain (``*.<domain>``), normalized
  to lowercase. ``notdemo.local`` does NOT match ``demo.local``.
- Absence of demo evidence → UNKNOWN (fail-closed). Never assume
  CONFIRMED_NON_DEMO from absence of markers.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Certificate number prefixes
# ---------------------------------------------------------------------------

DEMO_CERTIFICATE_PREFIXES: frozenset[str] = frozenset({
    "DEMO-",
})

# ---------------------------------------------------------------------------
# Email domains (exact match or subdomain *.<domain>)
# ---------------------------------------------------------------------------

DEMO_EMAIL_DOMAINS: frozenset[str] = frozenset({
    # Current marker (create_demo_certificate.py)
    "demo.local",
    # Historical homologation markers (migration a0b1c2d3e4f5, seed_white_label_demo)
    "wr.demo",
    "alfa.demo",
})

# ---------------------------------------------------------------------------
# Class locations (exact match only)
# ---------------------------------------------------------------------------

DEMO_CLASS_LOCATIONS: frozenset[str] = frozenset({
    # Current markers
    "DEMO-CERT-EAD",  # create_demo_certificate.py
    "DEMO-EAD-NR1",  # course_content.py route
    # Historical homologation markers
    "DEMO-EAD",  # seed_white_label_demo._DEMO_CLASS_LOCATION
    "DEMO-EAD-ASSESSMENT",  # migration a0b1c2d3e4f5 CLASS_LOCATION
})


# ---------------------------------------------------------------------------
# Evidence code labels
# ---------------------------------------------------------------------------

EVIDENCE_DEMO_CERTIFICATE_PREFIX = "DEMO_CERTIFICATE_PREFIX"
EVIDENCE_DEMO_EMAIL_DOMAIN = "DEMO_USER_EMAIL_DOMAIN"
EVIDENCE_DEMO_CLASS_LOCATION = "DEMO_CLASS_LOCATION"
EVIDENCE_HISTORICAL_DEMO_EMAIL_DOMAIN = "HISTORICAL_DEMO_EMAIL_DOMAIN"
EVIDENCE_HISTORICAL_DEMO_CLASS_LOCATION = "HISTORICAL_DEMO_CLASS_LOCATION"


# Historical marker sets (for evidence code differentiation)
_HISTORICAL_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "wr.demo",
    "alfa.demo",
})

_HISTORICAL_CLASS_LOCATIONS: frozenset[str] = frozenset({
    "DEMO-EAD",
    "DEMO-EAD-ASSESSMENT",
})


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------


def is_demo_certificate_number(cert_num: str | None) -> bool:
    """Return True if the certificate number starts with a known demo prefix."""
    if not cert_num:
        return False
    return any(cert_num.startswith(prefix) for prefix in DEMO_CERTIFICATE_PREFIXES)


def is_demo_email_domain(email: str | None) -> tuple[bool, str | None]:
    """Check if the email domain is a known demo domain.

    Returns (is_demo, evidence_code) where evidence_code is
    ``EVIDENCE_DEMO_EMAIL_DOMAIN`` or
    ``EVIDENCE_HISTORICAL_DEMO_EMAIL_DOMAIN`` for historical markers,
    or ``None`` if not a demo domain.

    Matching is exact or subdomain (*.domain), case-insensitive.
    ``notdemo.local`` does NOT match ``demo.local``.
    """
    if not email:
        return False, None
    domain = email.split("@")[-1].lower()
    for demo_domain in DEMO_EMAIL_DOMAINS:
        if domain == demo_domain or domain.endswith(f".{demo_domain}"):
            if demo_domain in _HISTORICAL_EMAIL_DOMAINS:
                return True, EVIDENCE_HISTORICAL_DEMO_EMAIL_DOMAIN
            return True, EVIDENCE_DEMO_EMAIL_DOMAIN
    return False, None


def is_demo_class_location(location: str | None) -> tuple[bool, str | None]:
    """Check if the class location is a known demo location.

    Returns (is_demo, evidence_code) where evidence_code is
    ``EVIDENCE_DEMO_CLASS_LOCATION`` or
    ``EVIDENCE_HISTORICAL_DEMO_CLASS_LOCATION`` for historical markers,
    or ``None`` if not a demo location.

    Matching is EXACT only. Never uses startswith to avoid false positives.
    """
    if not location:
        return False, None
    if location in DEMO_CLASS_LOCATIONS:
        if location in _HISTORICAL_CLASS_LOCATIONS:
            return True, EVIDENCE_HISTORICAL_DEMO_CLASS_LOCATION
        return True, EVIDENCE_DEMO_CLASS_LOCATION
    return False, None


def classify_demo(
    cert_nums: list[str],
    user_email: str | None,
    class_location: str | None,
) -> tuple[str, list[str]]:
    """Classify a record as demo, non-demo, or unknown.

    Uses known demo markers (certificate prefix, email domain, class location)
    as positive evidence. Returns (classification, evidence_codes).

    Classification:
    - CONFIRMED_DEMO: at least one positive demo evidence marker found.
    - UNKNOWN: no positive demo evidence. Fail-closed.

    CONFIRMED_NON_DEMO is only returned when there is positive evidence of
    operational/production origin. Since no reliable criteria for that exist
    in the current data model, UNKNOWN is used instead.

    No PII is returned — only classification and evidence codes.
    """
    evidence_codes: list[str] = []

    # Evidence: certificate number prefixed with a demo prefix
    if any(is_demo_certificate_number(c) for c in cert_nums):
        evidence_codes.append(EVIDENCE_DEMO_CERTIFICATE_PREFIX)

    # Evidence: user email domain is a known demo domain
    is_demo_email, email_evidence = is_demo_email_domain(user_email)
    if is_demo_email and email_evidence:
        evidence_codes.append(email_evidence)

    # Evidence: class location matches a known demo location
    is_demo_loc, loc_evidence = is_demo_class_location(class_location)
    if is_demo_loc and loc_evidence:
        evidence_codes.append(loc_evidence)

    if evidence_codes:
        return "CONFIRMED_DEMO", evidence_codes
    # Fail-closed: absence of demo evidence does NOT confirm NON_DEMO.
    return "UNKNOWN", []
