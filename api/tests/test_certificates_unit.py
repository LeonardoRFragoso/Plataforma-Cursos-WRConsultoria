import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request

from app.api.routes.certificates import (
    _authorize,
    _effective_status,
    _resolve_trusted_frontend_url,
    certificate_history,
    create_certificate,
    delete_certificate,
    download_certificate,
    get_certificate,
    list_certificates,
    list_my_certificates,
    reissue_certificate,
    revoke_certificate,
    validate_certificate,
)
from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.student import Student
from app.schemas.certificate import (
    CertificateCreate,
    CertificateReissueRequest,
    CertificateRevokeRequest,
    CertificateValidationRequest,
)
from tests.test_prelaunch_operations import _create_course_and_class


async def _admin_id(client, admin_headers):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    return uuid.UUID(response.json()["id"])


async def _completed_enrollment(client, admin_headers, student_user):
    _course, class_obj = await _create_course_and_class(
        client,
        admin_headers,
        validity_days=30,
    )
    enrollment = await client.post(
        "/api/v1/enrollments/",
        json={
            "student_id": student_user["student_id"],
            "class_id": class_obj["id"],
            "price": 320.0,
            "status": "CONFIRMADA",
        },
        headers=admin_headers,
    )
    assert enrollment.status_code == 201, enrollment.text
    enrollment_id = enrollment.json()["id"]
    completed = await client.put(
        f"/api/v1/enrollments/{enrollment_id}",
        json={"status": "CONCLUIDA"},
        headers=admin_headers,
    )
    assert completed.status_code == 200, completed.text
    return uuid.UUID(enrollment_id)


@pytest.mark.asyncio
async def test_certificate_routes_direct_lifecycle(
    client,
    admin_headers,
    student_user,
    monkeypatch,
):
    enrollment_id = await _completed_enrollment(client, admin_headers, student_user)
    admin_id = await _admin_id(client, admin_headers)

    async with AsyncSessionLocal() as lookup:
        student = await lookup.get(Student, uuid.UUID(student_user["student_id"]))
        assert student is not None
        student_user_id = student.user_id

    admin_user = {
        "user_id": str(admin_id),
        "role": "admin",
        "tenant_id": str(WR_TENANT_ID),
    }
    student_user_dict = {
        "user_id": str(student_user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID

            first = await create_certificate(
                CertificateCreate(enrollment_id=enrollment_id),
                db,
                admin_user,
            )
            assert first.status == "ACTIVE"
            assert first.version == 1
            assert first.content_hash

            listed = await list_certificates(db, admin_user, 0, 100)
            assert any(item.id == first.id for item in listed)

            mine = await list_my_certificates(db, student_user_dict)
            assert any(item.id == first.id for item in mine)
            assert await list_my_certificates(db, admin_user) == []

            valid = await validate_certificate(
                CertificateValidationRequest(validation_code=first.validation_code),
                db,
            )
            assert valid.valid is True
            assert valid.status == "ACTIVE"

            invalid = await validate_certificate(
                CertificateValidationRequest(validation_code="UNIT-NOT-FOUND"),
                db,
            )
            assert invalid.valid is False
            assert invalid.status == "NOT_FOUND"

            got = await get_certificate(first.id, db, student_user_dict)
            assert got.id == first.id

            history = await certificate_history(first.id, db, admin_user)
            assert any(event.event_type == "ISSUED" for event in history)

            with pytest.raises(HTTPException) as duplicate:
                await create_certificate(
                    CertificateCreate(enrollment_id=enrollment_id),
                    db,
                    admin_user,
                )
            assert duplicate.value.status_code == 409

            revoked = await revoke_certificate(
                first.id,
                CertificateRevokeRequest(reason="Correção unitária"),
                db,
                admin_user,
            )
            assert revoked.status == "REVOKED"

            revoked_again = await revoke_certificate(
                first.id,
                CertificateRevokeRequest(reason="Idempotência"),
                db,
                admin_user,
            )
            assert revoked_again.status == "REVOKED"

            second = await reissue_certificate(
                first.id,
                CertificateReissueRequest(reason="Reemissão unitária"),
                db,
                admin_user,
            )
            assert second.status == "ACTIVE"
            assert second.version == 2
            assert second.supersedes_id == first.id

            with pytest.raises(HTTPException) as duplicate_reissue:
                await reissue_certificate(
                    first.id,
                    CertificateReissueRequest(reason="Duplicada"),
                    db,
                    admin_user,
                )
            assert duplicate_reissue.value.status_code == 409

            third = await reissue_certificate(
                second.id,
                CertificateReissueRequest(reason="Nova versão"),
                db,
                admin_user,
            )
            assert third.status == "ACTIVE"
            assert third.version == 3

            with pytest.raises(HTTPException) as superseded_revoke:
                await revoke_certificate(
                    second.id,
                    CertificateRevokeRequest(reason="Inválida"),
                    db,
                    admin_user,
                )
            assert superseded_revoke.value.status_code == 409

            monkeypatch.setattr(
                "app.api.routes.certificates.CertificateService.generate_certificate_pdf",
                lambda **kwargs: b"%PDF-UNIT",
            )
            request = Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/certificate",
                    "headers": [],
                }
            )
            response = await download_certificate(
                third.id,
                request,
                db,
                student_user_dict,
            )
            assert response.media_type == "application/pdf"
            assert response.body == b"%PDF-UNIT"

            with pytest.raises(HTTPException) as immutable:
                await delete_certificate(third.id, db, admin_user)
            assert immutable.value.status_code == 409

            fake = uuid.uuid4()
            with pytest.raises(HTTPException) as get_missing:
                await get_certificate(fake, db, admin_user)
            assert get_missing.value.status_code == 404

            with pytest.raises(HTTPException) as history_missing:
                await certificate_history(fake, db, admin_user)
            assert history_missing.value.status_code == 404

            with pytest.raises(HTTPException) as revoke_missing:
                await revoke_certificate(
                    fake,
                    CertificateRevokeRequest(reason="Ausente"),
                    db,
                    admin_user,
                )
            assert revoke_missing.value.status_code == 404

            with pytest.raises(HTTPException) as reissue_missing:
                await reissue_certificate(
                    fake,
                    CertificateReissueRequest(reason="Ausente"),
                    db,
                    admin_user,
                )
            assert reissue_missing.value.status_code == 404

            with pytest.raises(HTTPException) as download_missing:
                await download_certificate(fake, request, db, admin_user)
            assert download_missing.value.status_code == 404

            with pytest.raises(HTTPException) as delete_missing:
                await delete_certificate(fake, db, admin_user)
            assert delete_missing.value.status_code == 404
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_certificate_helpers_and_authorization_branches(monkeypatch):
    now = utc_now()
    assert _effective_status(SimpleNamespace(status="REVOKED", expires_at=None)) == "REVOKED"
    assert _effective_status(SimpleNamespace(status="SUPERSEDED", expires_at=None)) == "SUPERSEDED"
    assert _effective_status(SimpleNamespace(status="ACTIVE", expires_at=now - timedelta(days=1))) == "EXPIRED"
    assert _effective_status(SimpleNamespace(status="ACTIVE", expires_at=None)) == "ACTIVE"

    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id)
    certificate = SimpleNamespace(tenant_id=WR_TENANT_ID)
    admin_user = {"user_id": str(uuid.uuid4()), "role": "admin"}
    own_user = {"user_id": str(user_id), "role": "student"}
    other_user = {"user_id": str(uuid.uuid4()), "role": "student"}

    _authorize(certificate, user, admin_user, WR_TENANT_ID)
    _authorize(certificate, user, own_user, WR_TENANT_ID)

    with pytest.raises(HTTPException) as forbidden:
        _authorize(certificate, user, other_user, WR_TENANT_ID)
    assert forbidden.value.status_code == 403

    with pytest.raises(HTTPException) as cross_tenant:
        _authorize(certificate, user, admin_user, uuid.uuid4())
    assert cross_tenant.value.status_code == 404

    no_origin = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    assert _resolve_trusted_frontend_url(no_origin, None) == settings.FRONTEND_URL

    monkeypatch.setattr(settings, "TRUSTED_FRONTEND_ORIGINS", ["https://trusted.example"])
    trusted = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"origin", b"https://trusted.example/")],
        }
    )
    assert _resolve_trusted_frontend_url(trusted, None) == "https://trusted.example"

    untrusted = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"origin", b"https://evil.example")],
        }
    )
    assert _resolve_trusted_frontend_url(untrusted, None) == settings.FRONTEND_URL
