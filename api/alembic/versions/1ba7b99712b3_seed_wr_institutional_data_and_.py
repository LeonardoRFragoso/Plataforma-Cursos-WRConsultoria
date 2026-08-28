"""seed_wr_institutional_data

Revision ID: 1ba7b99712b3
Revises: e784adb04d36
Create Date: 2026-08-28 17:58:36.817644

Seeds WR institutional data (razão social, CNPJ, address) on the WR
tenant's settings JSON block.

IMPORTANT — what this migration does NOT do:
- It does NOT create a TrainingProfessional for Willy Ramos.
  Persisting personal data (CPF) for a real person using an invented
  placeholder is prohibited. The instructor/CEO is recorded only as an
  external intent in the settings block (name, declared qualification,
  corporate role, verification status) until a real CPF/identity is
  provided by the owner.
- CEO is NOT a technical qualification. "Técnico em Segurança do
  Trabalho" is a declared qualification, not a verified one.
- professional_verification = PENDING means no official certificate
  readiness can be granted based on this entry alone.

Downgrade policy:
- This migration only writes the `institutional` block into the
  tenant's `settings` JSON and sets `legal_name`/`cnpj` if they were
  NULL. It never overwrites preexisting real institutional data.
- Downgrade removes ONLY the `institutional` block from `settings` and
  restores `legal_name`/`cnpj` to NULL ONLY if they match the values
  this migration set (i.e. were provably created by this migration).
  Preexisting real data is never destroyed.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ba7b99712b3"
down_revision: str | None = "e784adb04d36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WR_TENANT_SLUG = "wr"

WR_INSTITUTIONAL = {
    "legal_name": "WR Consultoria e Soluções em QSMS Ltda",
    "cnpj": "51.492.324/0001-25",
    "address": {
        "street": "Avenida Paranapuã, 1680, sala 205",
        "neighborhood": "Praia da Bandeira",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "zip_code": "21910-174",
    },
    # External intent only — NOT a TrainingProfessional record.
    # No CPF/identity is persisted. Verification is PENDING until the
    # owner provides real identification.
    "informed_instructor": {
        "name": "Willy Ramos",
        "declared_qualification": "Técnico em Segurança do Trabalho",
        "corporate_role": "CEO",
        "professional_verification": "PENDING",
        "note": (
            "CEO is NOT a technical qualification. "
            "No TrainingProfessional record is created until real "
            "CPF/identity is provided. NR-10 electrical qualification "
            "and NR-12 PLH remain PENDING_VERIFICATION."
        ),
    },
}

_LEGAL_NAME = WR_INSTITUTIONAL["legal_name"]
_CNPJ = WR_INSTITUTIONAL["cnpj"]


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT id, settings, legal_name, cnpj FROM tenants WHERE slug = :slug"),
        {"slug": WR_TENANT_SLUG},
    )
    row = result.fetchone()
    if not row:
        return
    tenant_id, settings, existing_legal_name, existing_cnpj = row
    if isinstance(settings, str):
        settings = json.loads(settings) if settings else {}
    if settings is None:
        settings = {}
    settings["institutional"] = WR_INSTITUTIONAL
    # Only set legal_name/cnpj if they were NULL — never overwrite real data.
    new_legal_name = existing_legal_name if existing_legal_name else _LEGAL_NAME
    new_cnpj = existing_cnpj if existing_cnpj else _CNPJ
    bind.execute(
        sa.text(
            "UPDATE tenants SET legal_name = :legal_name, cnpj = :cnpj, settings = :settings WHERE id = :tid"
        ),
        {
            "legal_name": new_legal_name,
            "cnpj": new_cnpj,
            "settings": json.dumps(settings),
            "tid": str(tenant_id),
        },
    )


def downgrade() -> None:
    """Remove ONLY data provably created by this migration.

    Never destroy preexisting real institutional data. We only:
    - Remove the `institutional` block from settings.
    - Set legal_name/cnpj to NULL ONLY if they exactly match the values
      this migration would have set (i.e. they were not preexisting).
    """
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT id, settings, legal_name, cnpj FROM tenants WHERE slug = :slug"),
        {"slug": WR_TENANT_SLUG},
    )
    row = result.fetchone()
    if not row:
        return
    tenant_id, settings, current_legal_name, current_cnpj = row
    if isinstance(settings, str):
        settings = json.loads(settings) if settings else {}
    if settings is None:
        settings = {}
    settings.pop("institutional", None)
    # Only null out legal_name/cnpj if they match what this migration set.
    # If they differ, they were preexisting real data — preserve them.
    restore_legal_name = None if current_legal_name == _LEGAL_NAME else current_legal_name
    restore_cnpj = None if current_cnpj == _CNPJ else current_cnpj
    bind.execute(
        sa.text(
            "UPDATE tenants SET legal_name = :legal_name, cnpj = :cnpj, settings = :settings WHERE id = :tid"
        ),
        {
            "legal_name": restore_legal_name,
            "cnpj": restore_cnpj,
            "settings": json.dumps(settings),
            "tid": str(tenant_id),
        },
    )
