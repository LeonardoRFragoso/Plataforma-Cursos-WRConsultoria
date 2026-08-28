from uuid import uuid4

from app.scripts.audit_repair_enrollment_course_links import _candidate_list, _normalize
from app.models.course import Course, CourseModality, CourseType


def _course(*, code: str, name: str) -> Course:
    return Course(
        id=uuid4(),
        tenant_id=uuid4(),
        code=code,
        name=name,
        category="NR",
        description=None,
        carga_horaria=8,
        modality=CourseModality.EAD,
        tipo_curso=CourseType.FORMACAO,
        price=0,
        is_active=True,
    )


def test_normalize_ignores_accents_punctuation_and_dash_variants():
    assert _normalize("NR-35 — Trabalho em Altura") == _normalize("NR 35 - Trabalho em Altura")


def test_candidate_list_prioritizes_unique_exact_normalized_name():
    source = _course(code="LEGACY-NR35", name="NR-35 — Trabalho em Altura")
    canonical = _course(code="NR-35-F", name="NR 35 - Trabalho em Altura")
    unrelated = _course(code="NR-10-B", name="NR 10 - Segurança em Instalações Elétricas")

    candidates = _candidate_list(source, [(canonical, 4), (unrelated, 6)])

    assert candidates[0].course_id == str(canonical.id)
    assert candidates[0].exact_name is True
    assert candidates[0].lesson_count == 4


def test_candidate_list_keeps_fuzzy_match_for_review_without_marking_exact():
    source = _course(code="LEGACY-NR10", name="NR 10 Segurança Elétrica")
    canonical = _course(code="NR-10-B", name="NR 10 - Segurança em Instalações Elétricas")

    candidates = _candidate_list(source, [(canonical, 6)])

    assert candidates
    assert candidates[0].exact_name is False
