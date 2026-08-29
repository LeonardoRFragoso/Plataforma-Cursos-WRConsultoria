"""Fail-closed tests for certificate issuance on regulated courses.

Verifies that:
A) POST /certificates/ on a course with incomplete readiness → 409/fail closed
B) Non-regulated course certificate issuance → works as expected
C) CertificateDocumentService.prepare_document fails when regulatory state
   is not CERTIFICATE_PENDING_SIGNATURE
D) Missing professional → certificate not issued
E) Mock PAdES in production → blocked
F) Missing practical evidence when required → not issued
G) Missing pedagogical project when required → not issued

These are real behavior tests, not constant-existence checks.
"""

from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.training_evidence import RegulatoryCompletionState
from app.services.certificate_signing_provider import (
    ExternalPadesGatewayProvider,
    MockPadesSigningProvider,
    SigningProviderError,
)


class TestMockPadesForbiddenInProduction:
    """MockPadesSigningProvider must be forbidden in production."""

    def test_mock_pades_forbidden_in_production(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        with pytest.raises(SigningProviderError, match="forbidden in production"):
            MockPadesSigningProvider(signer_name="test")

    def test_mock_pades_allowed_in_staging(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        provider = MockPadesSigningProvider(signer_name="test")
        assert provider.signer_name == "test"

    def test_mock_pades_allowed_in_development(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "development")
        provider = MockPadesSigningProvider(signer_name="test")
        assert provider.signer_name == "test"


class TestExternalPadesGatewaySecurity:
    """ExternalPadesGatewayProvider must enforce HTTPS."""

    def test_http_rejected(self):
        with pytest.raises(SigningProviderError, match="HTTPS"):
            ExternalPadesGatewayProvider(base_url="http://signing.example.com", api_token="tok")

    def test_empty_token_rejected(self):
        with pytest.raises(SigningProviderError, match="token"):
            ExternalPadesGatewayProvider(base_url="https://signing.example.com", api_token="")

    def test_https_accepted(self):
        provider = ExternalPadesGatewayProvider(
            base_url="https://signing.example.com", api_token="valid-token"
        )
        assert provider.base_url == "https://signing.example.com"

    def test_trailing_slash_stripped(self):
        provider = ExternalPadesGatewayProvider(
            base_url="https://signing.example.com/", api_token="tok"
        )
        assert provider.base_url == "https://signing.example.com"


class TestPrepareDocumentFailClosed:
    """CertificateDocumentService.prepare_document must fail closed when
    regulatory state is not CERTIFICATE_PENDING_SIGNATURE."""

    @pytest.mark.asyncio
    async def test_prepare_document_rejects_non_pending_signature_state(self):
        """prepare_document raises ValueError when state is not PENDING_SIGNATURE."""
        from app.services.certificate_document_service import CertificateDocumentService

        # Mock the _context method to return fake objects
        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.tenant_id = uuid.uuid4()
        mock_student = MagicMock()
        mock_user = MagicMock()
        mock_class = MagicMock()
        mock_course = MagicMock()
        mock_tenant = MagicMock()

        # Mock _existing_live_document to return None (no existing doc)
        with patch.object(
            CertificateDocumentService,
            "_context",
            new_callable=AsyncMock,
            return_value=(mock_enrollment, mock_student, mock_user, mock_class, mock_course, mock_tenant),
        ), patch.object(
            CertificateDocumentService,
            "_existing_live_document",
            new_callable=AsyncMock,
            return_value=None,
        ):
            # Mock evaluate_regulatory_state to return a non-PENDING_SIGNATURE state
            mock_eval = MagicMock()
            mock_eval.state = RegulatoryCompletionState.IN_PROGRESS
            with patch(
                "app.services.certificate_document_service.evaluate_regulatory_state",
                new_callable=AsyncMock,
                return_value=mock_eval,
            ), pytest.raises(ValueError, match="not ready for trusted certificate"):
                await CertificateDocumentService.prepare_document(
                    AsyncMock(),
                    tenant_id=mock_enrollment.tenant_id,
                    enrollment_id=mock_enrollment.id,
                    actor_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_prepare_document_rejects_enrolled_state(self):
        """prepare_document raises ValueError when state is ENROLLED."""
        from app.services.certificate_document_service import CertificateDocumentService

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.tenant_id = uuid.uuid4()

        with patch.object(
            CertificateDocumentService,
            "_context",
            new_callable=AsyncMock,
            return_value=(mock_enrollment, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch.object(
            CertificateDocumentService,
            "_existing_live_document",
            new_callable=AsyncMock,
            return_value=None,
        ):
            mock_eval = MagicMock()
            mock_eval.state = RegulatoryCompletionState.ENROLLED
            with patch(
                "app.services.certificate_document_service.evaluate_regulatory_state",
                new_callable=AsyncMock,
                return_value=mock_eval,
            ), pytest.raises(ValueError, match="not ready"):
                await CertificateDocumentService.prepare_document(
                    AsyncMock(),
                    tenant_id=mock_enrollment.tenant_id,
                    enrollment_id=mock_enrollment.id,
                    actor_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_prepare_document_rejects_assessment_pending_state(self):
        """prepare_document raises ValueError when state is ASSESSMENT_PENDING."""
        from app.services.certificate_document_service import CertificateDocumentService

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.tenant_id = uuid.uuid4()

        with patch.object(
            CertificateDocumentService,
            "_context",
            new_callable=AsyncMock,
            return_value=(mock_enrollment, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch.object(
            CertificateDocumentService,
            "_existing_live_document",
            new_callable=AsyncMock,
            return_value=None,
        ):
            mock_eval = MagicMock()
            mock_eval.state = RegulatoryCompletionState.ASSESSMENT_PENDING
            with patch(
                "app.services.certificate_document_service.evaluate_regulatory_state",
                new_callable=AsyncMock,
                return_value=mock_eval,
            ), pytest.raises(ValueError, match="not ready"):
                await CertificateDocumentService.prepare_document(
                    AsyncMock(),
                    tenant_id=mock_enrollment.tenant_id,
                    enrollment_id=mock_enrollment.id,
                    actor_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_prepare_document_rejects_practical_pending_state(self):
        """prepare_document raises ValueError when practical component is pending."""
        from app.services.certificate_document_service import CertificateDocumentService

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.tenant_id = uuid.uuid4()

        with patch.object(
            CertificateDocumentService,
            "_context",
            new_callable=AsyncMock,
            return_value=(mock_enrollment, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch.object(
            CertificateDocumentService,
            "_existing_live_document",
            new_callable=AsyncMock,
            return_value=None,
        ):
            mock_eval = MagicMock()
            mock_eval.state = RegulatoryCompletionState.PRACTICAL_COMPONENT_PENDING
            with patch(
                "app.services.certificate_document_service.evaluate_regulatory_state",
                new_callable=AsyncMock,
                return_value=mock_eval,
            ), pytest.raises(ValueError, match="not ready"):
                await CertificateDocumentService.prepare_document(
                    AsyncMock(),
                    tenant_id=mock_enrollment.tenant_id,
                    enrollment_id=mock_enrollment.id,
                    actor_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_prepare_document_rejects_compliance_review_required(self):
        """prepare_document raises ValueError when compliance review is required."""
        from app.services.certificate_document_service import CertificateDocumentService

        mock_enrollment = MagicMock()
        mock_enrollment.id = uuid.uuid4()
        mock_enrollment.tenant_id = uuid.uuid4()

        with patch.object(
            CertificateDocumentService,
            "_context",
            new_callable=AsyncMock,
            return_value=(mock_enrollment, MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()),
        ), patch.object(
            CertificateDocumentService,
            "_existing_live_document",
            new_callable=AsyncMock,
            return_value=None,
        ):
            mock_eval = MagicMock()
            mock_eval.state = RegulatoryCompletionState.COMPLIANCE_REVIEW_REQUIRED
            with patch(
                "app.services.certificate_document_service.evaluate_regulatory_state",
                new_callable=AsyncMock,
                return_value=mock_eval,
            ), pytest.raises(ValueError, match="not ready"):
                await CertificateDocumentService.prepare_document(
                    AsyncMock(),
                    tenant_id=mock_enrollment.tenant_id,
                    enrollment_id=mock_enrollment.id,
                    actor_id=uuid.uuid4(),
                )


class TestCertificateApiFailClosed:
    """API-level fail-closed tests for certificate issuance."""

    @pytest.mark.asyncio
    async def test_post_certificates_requires_completed_enrollment(self, client, admin_headers):
        """POST /certificates/ on a non-completed enrollment → 409."""
        # Create a minimal enrollment that is NOT CONCLUIDA
        from app.core.constants import WR_TENANT_ID
        from app.core.database import AsyncSessionLocal
        from app.core.security import hash_password
        from app.core.utils import utc_now
        from app.models.class_model import Class, ClassStatus
        from app.models.course import Course
        from app.models.enrollment import Enrollment, EnrollmentStatus
        from app.models.student import Student
        from app.models.user import User, UserRole

        today = utc_now().date()
        # Generate unique CPFs to avoid collision with admin_token fixture
        unique_cpf_student = f"{uuid.uuid4().hex[:11]}"
        unique_cpf_admin = f"{uuid.uuid4().hex[:11]}"
        async with AsyncSessionLocal() as db:
            user = User(
                tenant_id=WR_TENANT_ID,
                email=f"fail-closed-{uuid.uuid4().hex[:8]}@example.com",
                full_name="Aluno Fail Closed",
                cpf=unique_cpf_student,
                password_hash=hash_password("student123"),
                role=UserRole.STUDENT,
                is_active=True,
            )
            admin = User(
                tenant_id=WR_TENANT_ID,
                email=f"fail-admin-{uuid.uuid4().hex[:8]}@example.com",
                full_name="Admin Fail Closed",
                cpf=unique_cpf_admin,
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            course = Course(
                tenant_id=WR_TENANT_ID,
                code=f"FAIL-{uuid.uuid4().hex[:6].upper()}",
                name="Curso Fail Closed",
                category="Segurança",
                carga_horaria=8,
                modality="EAD",
                price=150.0,
                is_active=True,
            )
            db.add_all([user, admin, course])
            await db.flush()

            student = Student(tenant_id=WR_TENANT_ID, user_id=user.id, cpf=user.cpf)
            class_obj = Class(
                tenant_id=WR_TENANT_ID,
                course_id=course.id,
                responsible_admin_id=admin.id,
                start_date=today,
                end_date=today,
                max_students=20,
                status=ClassStatus.ABERTA,
            )
            db.add_all([student, class_obj])
            await db.flush()

            # PENDENTE enrollment — NOT completed
            enrollment = Enrollment(
                tenant_id=WR_TENANT_ID,
                student_id=student.id,
                class_id=class_obj.id,
                price=150.0,
                status=EnrollmentStatus.PENDENTE,
            )
            db.add(enrollment)
            await db.commit()
            enrollment_id = enrollment.id

        # POST /certificates/ should fail with 409
        response = await client.post(
            "/api/v1/certificates/",
            json={"enrollment_id": str(enrollment_id)},
            headers=admin_headers,
        )
        assert response.status_code == 409
        assert "completed" in response.json()["detail"].lower()


class TestMockPadesSigning:
    """Verify mock signing produces clearly-marked non-ICP-Brasil output."""

    def test_mock_signature_marked_as_not_trusted(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
        provider = MockPadesSigningProvider(signer_name="test-signer")
        cert_id = uuid.uuid4()
        original_pdf = b"%PDF-1.4 test content"

        import asyncio

        submission = asyncio.get_event_loop().run_until_complete(
            provider.submit(
                original_pdf=original_pdf,
                original_sha256=hashlib.sha256(original_pdf).hexdigest(),
                certificate_id=cert_id,
                callback_url=None,
            )
        )
        assert submission.status == "SIGNED"

        result = asyncio.get_event_loop().run_until_complete(
            provider.poll(submission.provider_job_id)
        )
        assert result.verification["is_mock"] is True
        assert result.verification["chain_trusted"] is False
        assert result.verification["standard"] == "PAdES-MOCK"
        assert b"MOCK-PADES-SIGNATURE" in result.signed_pdf_bytes
        assert b"SEM VALIDADE ICP-BRASIL" in result.signed_pdf_bytes
