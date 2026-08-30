from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class RegulatorySourceVersion:
    code: str
    title: str
    authority: str
    source_url: str
    effective_from: date | None = None
    effective_until: date | None = None
    notes: str | None = None

    def applies_on(self, reference_date: date) -> bool:
        if self.effective_from and reference_date < self.effective_from:
            return False
        if self.effective_until and reference_date > self.effective_until:
            return False
        return True

    def public_dict(self) -> dict:
        payload = asdict(self)
        payload["effective_from"] = self.effective_from.isoformat() if self.effective_from else None
        payload["effective_until"] = self.effective_until.isoformat() if self.effective_until else None
        return payload


# Official Ministry of Labour sources. URLs are deliberately stored with the
# rule metadata so a future regulatory review can trace exactly which public
# source supported each machine-enforced baseline.
NR1_CURRENT = RegulatorySourceVersion(
    code="NR-01",
    title="NR-01 — Disposições Gerais e Gerenciamento de Riscos Ocupacionais",
    authority="Ministério do Trabalho e Emprego",
    source_url=(
        "https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/"
        "participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-"
        "partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-"
        "vigentes/nr-01-atualizada-2024-ii.pdf"
    ),
    notes=(
        "Baseline used for certificate minimum fields, EAD traceability, "
        "individual authentication and access-log retention."
    ),
)

NR10_CURRENT = RegulatorySourceVersion(
    code="NR-10",
    title="NR-10 — Segurança em Instalações e Serviços em Eletricidade",
    authority="Ministério do Trabalho e Emprego",
    source_url=(
        "https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/"
        "participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-"
        "partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-"
        "vigentes/norma-regulamentadora-no-10-nr-10"
    ),
    effective_until=date(2027, 5, 31),
    notes="Current NR-10 remains applicable through 31/05/2027.",
)

NR10_2027 = RegulatorySourceVersion(
    code="NR-10",
    title="NR-10 — revisão da Portaria MTE nº 737/2026",
    authority="Ministério do Trabalho e Emprego",
    source_url=(
        "https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/"
        "participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-"
        "partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-"
        "vigentes/norma-regulamentadora-no-10-nr-10"
    ),
    effective_from=date(2027, 6, 1),
    notes="Future NR-10 version becomes applicable on 01/06/2027.",
)

ITI_PADES = RegulatorySourceVersion(
    code="ICP-BRASIL-PADES",
    title="Políticas de Assinatura ICP-Brasil — PAdES",
    authority="Instituto Nacional de Tecnologia da Informação",
    source_url="https://www.gov.br/iti/pt-br/assuntos/legislacao/documentos-principais",
    notes=(
        "Technical reference for the trusted PDF-signature provider. The "
        "platform never stores a private key or PFX in application tables."
    ),
)


# NR-01 item 1.7.1.1 minimum information expressed using the keys already
# supported by CertificateDocumentService._required_snapshot_value().
NR1_CERTIFICATE_REQUIRED_FIELDS: tuple[str, ...] = (
    "student_name",
    "course_name",
    "workload",
    "training_start",
    "training_end",
    "training_location",
    "instructors",
    "technical_responsible",
)

# Human-readable controls used by the admin/readiness APIs. These are not a
# substitute for legal review; they are the source-backed floor the software
# can enforce without inventing WR-specific facts.
NR1_EAD_CONTROLS: tuple[str, ...] = (
    "individual_authentication",
    "assessment_traceability",
    "assessment_results_retained",
    "access_logs_retained_until_validity_end_plus_2_years",
    "appropriate_virtual_learning_environment",
)

# The governance table stores retention as an integer number of days while the
# source rule is calendar based (validity end + two calendar years). 731 days
# is a deliberately conservative operational projection that covers a leap day.
# Date-specific legal boundaries must continue to use add_calendar_years().
CONSERVATIVE_TWO_YEAR_BUFFER_DAYS = 731


def nr10_source_for(reference_date: date) -> RegulatorySourceVersion:
    """Return the NR-10 source version applicable on a calendar date."""
    return NR10_2027 if reference_date >= date(2027, 6, 1) else NR10_CURRENT


def add_calendar_years(value: date, years: int) -> date:
    """Calendar-year arithmetic suitable for legal retention boundaries."""
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # 29 February -> 28 February in a non-leap target year.
        return value.replace(month=2, day=28, year=value.year + years)


def minimum_ead_access_log_retention_until(course_validity_end: date) -> date:
    """NR-01 EAD floor: keep access logs for 2 years after course validity."""
    return add_calendar_years(course_validity_end, 2)


def operational_ead_access_log_retention_days(validity_days: int) -> int:
    """Conservative day-based floor for the versioned operational policy."""
    if validity_days <= 0:
        raise ValueError("validity_days must be positive")
    return validity_days + CONSERVATIVE_TWO_YEAR_BUFFER_DAYS


def official_regulatory_sources() -> list[dict]:
    return [
        NR1_CURRENT.public_dict(),
        NR10_CURRENT.public_dict(),
        NR10_2027.public_dict(),
        ITI_PADES.public_dict(),
    ]
