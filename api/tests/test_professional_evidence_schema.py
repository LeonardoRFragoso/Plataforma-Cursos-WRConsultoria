from datetime import datetime

from app.schemas.professional_evidence import ProfessionalEvidenceCreate


def test_professional_evidence_normalizes_offset_timestamps_to_utc_naive():
    payload = ProfessionalEvidenceCreate.model_validate(
        {
            "evidence_type": "PROFICIENCY",
            "issued_at": "2026-08-30T18:00:00-03:00",
            "expires_at": "2027-08-30T18:00:00-03:00",
        }
    )

    assert payload.issued_at == datetime(2026, 8, 30, 21, 0, 0)
    assert payload.expires_at == datetime(2027, 8, 30, 21, 0, 0)
    assert payload.issued_at.tzinfo is None
    assert payload.expires_at.tzinfo is None
