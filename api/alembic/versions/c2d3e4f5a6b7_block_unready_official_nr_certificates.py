"""Fail-closed database gate for official NR certificates.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-27

The trigger protects every issuance path, including legacy code: CERT-* records
for NR courses cannot be inserted until compliance and learner evidence are
complete. DEMO-* records remain available for homologation.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_official_nr_certificate_compliance()
        RETURNS trigger AS $$
        DECLARE
            v_course_id uuid;
            v_course_code text;
            v_course_modality text;
            v_profile course_compliance_profiles%ROWTYPE;
            v_active_seconds bigint;
        BEGIN
            IF NEW.certificate_number NOT LIKE 'CERT-%' THEN
                RETURN NEW;
            END IF;

            SELECT c.id, c.code, c.modality::text
              INTO v_course_id, v_course_code, v_course_modality
              FROM enrollments e
              JOIN classes cl ON cl.id = e.class_id
              JOIN courses c ON c.id = cl.course_id
             WHERE e.id = NEW.enrollment_id
               AND c.tenant_id = NEW.tenant_id;

            IF v_course_code IS NULL OR v_course_code NOT LIKE 'NR-%' THEN
                RETURN NEW;
            END IF;

            SELECT * INTO v_profile
              FROM course_compliance_profiles
             WHERE tenant_id = NEW.tenant_id
               AND course_id = v_course_id
             LIMIT 1;

            IF v_profile.id IS NULL THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: compliance profile missing';
            END IF;
            IF v_profile.status <> 'COMPLIANCE_READY' THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: compliance status is %', v_profile.status;
            END IF;
            IF v_profile.blocker_reason IS NOT NULL AND btrim(v_profile.blocker_reason) <> '' THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: unresolved compliance blocker';
            END IF;
            IF v_profile.regulatory_version IS NULL OR v_profile.normative_source_url IS NULL
               OR v_profile.source_checked_at IS NULL THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: normative evidence incomplete';
            END IF;
            IF v_profile.required_delivery_mode IS NULL
               OR v_profile.required_delivery_mode <> v_course_modality THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: delivery mode is not compliant';
            END IF;
            IF v_profile.technical_responsible_id IS NULL
               OR NOT EXISTS (
                    SELECT 1 FROM training_professionals tp
                     WHERE tp.id = v_profile.technical_responsible_id
                       AND tp.tenant_id = NEW.tenant_id
                       AND tp.professional_role = 'TECHNICAL_RESPONSIBLE'
                       AND tp.is_active = true
               ) THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: technical responsible missing/invalid';
            END IF;
            IF v_profile.pedagogical_project_version_id IS NULL
               OR NOT EXISTS (
                    SELECT 1 FROM pedagogical_project_versions pp
                     WHERE pp.id = v_profile.pedagogical_project_version_id
                       AND pp.tenant_id = NEW.tenant_id
                       AND pp.course_id = v_course_id
                       AND pp.status = 'APPROVED'
                       AND (pp.valid_until IS NULL OR pp.valid_until > CURRENT_TIMESTAMP)
               ) THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: approved pedagogical project missing';
            END IF;
            IF v_profile.support_channel_verified IS NOT TRUE THEN
                RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: support channel not verified';
            END IF;

            IF v_profile.requires_final_assessment THEN
                IF v_profile.assessment_practical_scenarios_validated IS NOT TRUE THEN
                    RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: assessment practical scenarios not validated';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM assessment_attempts aa
                     WHERE aa.tenant_id = NEW.tenant_id
                       AND aa.enrollment_id = NEW.enrollment_id
                       AND aa.course_id = v_course_id
                       AND aa.passed = true
                       AND aa.completed_at IS NOT NULL
                       AND (v_profile.minimum_score IS NULL OR aa.score >= v_profile.minimum_score)
                ) THEN
                    RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: satisfactory assessment missing';
                END IF;
            END IF;

            IF v_profile.requires_practical_component THEN
                IF NOT EXISTS (
                    SELECT 1 FROM practical_training_records pr
                     WHERE pr.tenant_id = NEW.tenant_id
                       AND pr.enrollment_id = NEW.enrollment_id
                       AND pr.course_id = v_course_id
                       AND pr.result = 'SATISFATORIO'
                       AND (
                           v_profile.practical_minimum_percent IS NULL
                           OR pr.practical_percent >= v_profile.practical_minimum_percent
                       )
                ) THEN
                    RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: satisfactory practical component missing';
                END IF;
            END IF;

            IF v_profile.minimum_workload_hours IS NOT NULL THEN
                SELECT COALESCE(SUM(active_seconds), 0)
                  INTO v_active_seconds
                  FROM training_sessions
                 WHERE tenant_id = NEW.tenant_id
                   AND enrollment_id = NEW.enrollment_id
                   AND course_id = v_course_id;
                IF v_active_seconds < (v_profile.minimum_workload_hours * 3600)::bigint THEN
                    RAISE EXCEPTION 'OFFICIAL_NR_CERTIFICATE_BLOCKED: minimum active training duration not met';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_official_nr_certificate_compliance ON certificates;
        CREATE TRIGGER trg_official_nr_certificate_compliance
        BEFORE INSERT ON certificates
        FOR EACH ROW
        EXECUTE FUNCTION enforce_official_nr_certificate_compliance();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_official_nr_certificate_compliance ON certificates")
    op.execute("DROP FUNCTION IF EXISTS enforce_official_nr_certificate_compliance()")
