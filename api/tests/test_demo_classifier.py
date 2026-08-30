"""Tests for the shared demo marker classifier.

Covers all mandatory cases A-L from the corrective gate specification,
plus edge cases for email domain subdomain matching and class location
exact-match safety.
"""

from __future__ import annotations

from app.core.demo_markers import (
    DEMO_CERTIFICATE_PREFIXES,
    DEMO_CLASS_LOCATIONS,
    DEMO_EMAIL_DOMAINS,
    classify_demo,
    is_demo_certificate_number,
    is_demo_class_location,
    is_demo_email_domain,
)

# ===========================================================================
# Test A: aluno2@wr.demo → CONFIRMED_DEMO
# ===========================================================================


def test_A_wr_demo_email_confirmed_demo():
    cls, evidence = classify_demo([], "aluno2@wr.demo", None)
    assert cls == "CONFIRMED_DEMO"
    assert "HISTORICAL_DEMO_EMAIL_DOMAIN" in evidence


# ===========================================================================
# Test B: user@foo.wr.demo → CONFIRMED_DEMO (subdomain)
# ===========================================================================


def test_B_wr_demo_subdomain_confirmed_demo():
    cls, evidence = classify_demo([], "user@foo.wr.demo", None)
    assert cls == "CONFIRMED_DEMO"
    assert "HISTORICAL_DEMO_EMAIL_DOMAIN" in evidence


# ===========================================================================
# Test C: demo@demo.local → CONFIRMED_DEMO
# ===========================================================================


def test_C_demo_local_confirmed_demo():
    cls, evidence = classify_demo([], "demo@demo.local", None)
    assert cls == "CONFIRMED_DEMO"
    assert "DEMO_USER_EMAIL_DOMAIN" in evidence


# ===========================================================================
# Test D: demo@tenant.demo.local → CONFIRMED_DEMO (subdomain)
# ===========================================================================


def test_D_demo_local_subdomain_confirmed_demo():
    cls, evidence = classify_demo([], "demo@tenant.demo.local", None)
    assert cls == "CONFIRMED_DEMO"
    assert "DEMO_USER_EMAIL_DOMAIN" in evidence


# ===========================================================================
# Test E: user@notwr.demo → UNKNOWN
# ===========================================================================


def test_E_notwr_demo_unknown():
    cls, evidence = classify_demo([], "user@notwr.demo", None)
    assert cls == "UNKNOWN"
    assert evidence == []


# ===========================================================================
# Test F: user@notdemo.local → UNKNOWN
# ===========================================================================


def test_F_notdemo_local_unknown():
    cls, evidence = classify_demo([], "user@notdemo.local", None)
    assert cls == "UNKNOWN"
    assert evidence == []


# ===========================================================================
# Test G: class_location=DEMO-EAD-ASSESSMENT → CONFIRMED_DEMO
# ===========================================================================


def test_G_demo_ead_assessment_confirmed_demo():
    cls, evidence = classify_demo([], None, "DEMO-EAD-ASSESSMENT")
    assert cls == "CONFIRMED_DEMO"
    assert "HISTORICAL_DEMO_CLASS_LOCATION" in evidence


# ===========================================================================
# Test H: class_location=DEMO-CERT-EAD → CONFIRMED_DEMO
# ===========================================================================


def test_H_demo_cert_ead_confirmed_demo():
    cls, evidence = classify_demo([], None, "DEMO-CERT-EAD")
    assert cls == "CONFIRMED_DEMO"
    assert "DEMO_CLASS_LOCATION" in evidence


# ===========================================================================
# Test I: class_location=DEMO-EAD → CONFIRMED_DEMO
# ===========================================================================


def test_I_demo_ead_confirmed_demo():
    cls, evidence = classify_demo([], None, "DEMO-EAD")
    assert cls == "CONFIRMED_DEMO"
    assert "HISTORICAL_DEMO_CLASS_LOCATION" in evidence


# ===========================================================================
# Test J: class_location="DEMO-RANDOM" → UNKNOWN (no startswith match)
# ===========================================================================


def test_J_demo_random_unknown():
    cls, evidence = classify_demo([], None, "DEMO-RANDOM")
    assert cls == "UNKNOWN"
    assert evidence == []


# ===========================================================================
# Test K: DEMO-* certificate → CONFIRMED_DEMO
# ===========================================================================


def test_K_demo_certificate_confirmed_demo():
    cls, evidence = classify_demo(["DEMO-ABC123"], None, None)
    assert cls == "CONFIRMED_DEMO"
    assert "DEMO_CERTIFICATE_PREFIX" in evidence


# ===========================================================================
# Test L: no evidence → UNKNOWN
# ===========================================================================


def test_L_no_evidence_unknown():
    cls, evidence = classify_demo([], None, None)
    assert cls == "UNKNOWN"
    assert evidence == []


# ===========================================================================
# Additional edge cases
# ===========================================================================


def test_case_insensitive_email_domain():
    """Email domain matching should be case-insensitive."""
    cls, _ = classify_demo([], "Aluno2@WR.DEMO", None)
    assert cls == "CONFIRMED_DEMO"


def test_fakewr_demo_example_com_not_demo():
    """fakewr.demo.example.com should NOT match wr.demo."""
    cls, evidence = classify_demo([], "user@fakewr.demo.example.com", None)
    assert cls == "UNKNOWN"
    assert evidence == []


def test_alfa_demo_confirmed_demo():
    """alfa.demo should be recognized as a historical demo domain."""
    cls, evidence = classify_demo([], "aluno1@alfa.demo", None)
    assert cls == "CONFIRMED_DEMO"
    assert "HISTORICAL_DEMO_EMAIL_DOMAIN" in evidence


def test_multiple_evidence_codes():
    """Multiple demo markers should produce multiple evidence codes."""
    cls, evidence = classify_demo(["DEMO-123"], "aluno2@wr.demo", "DEMO-EAD-ASSESSMENT")
    assert cls == "CONFIRMED_DEMO"
    assert "DEMO_CERTIFICATE_PREFIX" in evidence
    assert "HISTORICAL_DEMO_EMAIL_DOMAIN" in evidence
    assert "HISTORICAL_DEMO_CLASS_LOCATION" in evidence
    assert len(evidence) == 3


def test_cert_num_none_not_demo():
    """None certificate number should not be classified as demo."""
    assert is_demo_certificate_number(None) is False
    assert is_demo_certificate_number("") is False


def test_class_location_exact_not_startswith():
    """DEMO-EAD-ASSESSMENT-EXTRA should NOT match (exact only)."""
    is_demo, _ = is_demo_class_location("DEMO-EAD-ASSESSMENT-EXTRA")
    assert is_demo is False


def test_email_none_not_demo():
    """None email should not be classified as demo."""
    is_demo, evidence = is_demo_email_domain(None)
    assert is_demo is False
    assert evidence is None


def test_class_location_none_not_demo():
    """None class location should not be classified as demo."""
    is_demo, evidence = is_demo_class_location(None)
    assert is_demo is False
    assert evidence is None


def test_demo_ead_nr1_confirmed_demo():
    """DEMO-EAD-NR1 should be recognized as a current demo location."""
    cls, evidence = classify_demo([], None, "DEMO-EAD-NR1")
    assert cls == "CONFIRMED_DEMO"
    assert "DEMO_CLASS_LOCATION" in evidence


def test_cert_prefix_cert_not_demo():
    """CERT- prefix should NOT be classified as demo."""
    cls, evidence = classify_demo(["CERT-ABC123"], None, None)
    assert cls == "UNKNOWN"
    assert evidence == []


def test_marker_sets_immutable():
    """Marker sets should be frozensets (immutable)."""
    assert isinstance(DEMO_EMAIL_DOMAINS, frozenset)
    assert isinstance(DEMO_CLASS_LOCATIONS, frozenset)
    assert isinstance(DEMO_CERTIFICATE_PREFIXES, frozenset)


def test_historical_markers_present():
    """Historical markers from migration a0b1c2d3e4f5 must be present."""
    assert "wr.demo" in DEMO_EMAIL_DOMAINS
    assert "alfa.demo" in DEMO_EMAIL_DOMAINS
    assert "DEMO-EAD-ASSESSMENT" in DEMO_CLASS_LOCATIONS
    assert "DEMO-EAD" in DEMO_CLASS_LOCATIONS


def test_current_markers_present():
    """Current markers must be present."""
    assert "demo.local" in DEMO_EMAIL_DOMAINS
    assert "DEMO-CERT-EAD" in DEMO_CLASS_LOCATIONS
    assert "DEMO-EAD-NR1" in DEMO_CLASS_LOCATIONS
    assert "DEMO-" in DEMO_CERTIFICATE_PREFIXES
