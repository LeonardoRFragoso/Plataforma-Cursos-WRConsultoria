import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.financial_admin import (
    claim_review,
    create_corporate_payment,
    financial_summary,
    list_corporate_payments,
    list_financial_reviews,
    open_manual_review,
    resolve_review,
    review_events,
)
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.models.payment import PaymentMethod, PaymentProvider, PaymentStatus
from app.schemas.financial import (
    CorporatePaymentCreate,
    FinancialReviewClaim,
    FinancialReviewResolution,
    ManualReviewCreate,
)
from tests.test_prelaunch_operations import _create_company


async def _admin_user(client, admin_headers):
    response = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert response.status_code == 200
    return {
        "user_id": response.json()["id"],
        "role": "admin",
        "tenant_id": str(WR_TENANT_ID),
    }


@pytest.mark.asyncio
async def test_financial_admin_routes_direct(client, admin_headers):
    company = await _create_company(client, admin_headers)
    admin_user = await _admin_user(client, admin_headers)
    company_id = uuid.UUID(company["id"])

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID

            payment = await create_corporate_payment(
                CorporatePaymentCreate(
                    company_id=company_id,
                    amount=1500.0,
                    method=PaymentMethod.PIX,
                    provider=PaymentProvider.ASAAS,
                    reference="UNIT-FIN-001",
                ),
                db,
                admin_user,
            )
            assert payment.company_id == company_id
            assert payment.status == PaymentStatus.PENDENTE
            assert payment.review_reason == "corporate_reference:UNIT-FIN-001"

            company_payments = await list_corporate_payments(
                company_id,
                db,
                admin_user,
            )
            assert any(item.id == payment.id for item in company_payments)

            review = await open_manual_review(
                payment.id,
                ManualReviewCreate(reason="Conferência financeira", priority="HIGH"),
                db,
                admin_user,
            )
            assert review.status == "OPEN"
            assert review.priority == "HIGH"
            assert review.review_required is True

            reviews = await list_financial_reviews(
                "OPEN",
                "HIGH",
                db,
                admin_user,
            )
            assert any(item.id == review.id for item in reviews)

            with pytest.raises(HTTPException) as invalid_filter:
                await list_financial_reviews(
                    "INVALID",
                    None,
                    db,
                    admin_user,
                )
            assert invalid_filter.value.status_code == 400

            claimed = await claim_review(
                review.id,
                FinancialReviewClaim(priority="URGENT"),
                db,
                admin_user,
            )
            assert claimed.status == "IN_REVIEW"
            assert claimed.priority == "URGENT"

            events = await review_events(review.id, db, admin_user)
            assert any(event.event_type == "CLAIMED" for event in events)

            with pytest.raises(HTTPException) as invalid_action:
                await resolve_review(
                    review.id,
                    FinancialReviewResolution(
                        action="INVALID",
                        notes="Ação inválida",
                    ),
                    db,
                    admin_user,
                )
            assert invalid_action.value.status_code == 400

            resolved = await resolve_review(
                review.id,
                FinancialReviewResolution(
                    action="MARK_APPROVED",
                    notes="Pagamento confirmado",
                ),
                db,
                admin_user,
            )
            assert resolved.status == "RESOLVED"
            assert resolved.payment_status == PaymentStatus.APROVADO
            assert resolved.review_required is False

            with pytest.raises(HTTPException) as closed_claim:
                await claim_review(
                    review.id,
                    FinancialReviewClaim(),
                    db,
                    admin_user,
                )
            assert closed_claim.value.status_code == 409

            with pytest.raises(HTTPException) as closed_resolve:
                await resolve_review(
                    review.id,
                    FinancialReviewResolution(
                        action="DISMISS",
                        notes="Já encerrada",
                    ),
                    db,
                    admin_user,
                )
            assert closed_resolve.value.status_code == 409

            summary = await financial_summary(db, admin_user)
            assert summary.approved_total >= 1500.0
            assert summary.approved_payments >= 1
            assert summary.corporate_payments >= 1

            second_payment = await create_corporate_payment(
                CorporatePaymentCreate(
                    company_id=company_id,
                    amount=300.0,
                    method=PaymentMethod.PIX,
                    provider=PaymentProvider.ASAAS,
                ),
                db,
                admin_user,
            )
            second_review = await open_manual_review(
                second_payment.id,
                ManualReviewCreate(reason="Revisão descartável"),
                db,
                admin_user,
            )
            dismissed = await resolve_review(
                second_review.id,
                FinancialReviewResolution(
                    action="DISMISS",
                    notes="Sem divergência real",
                ),
                db,
                admin_user,
            )
            assert dismissed.status == "DISMISSED"

            fake = uuid.uuid4()
            with pytest.raises(HTTPException) as missing_review:
                await review_events(fake, db, admin_user)
            assert missing_review.value.status_code == 404

            with pytest.raises(HTTPException) as missing_payment:
                await open_manual_review(
                    fake,
                    ManualReviewCreate(reason="Pagamento ausente"),
                    db,
                    admin_user,
                )
            assert missing_payment.value.status_code == 404

            with pytest.raises(HTTPException) as missing_company:
                await create_corporate_payment(
                    CorporatePaymentCreate(
                        company_id=fake,
                        amount=10.0,
                        method=PaymentMethod.PIX,
                        provider=PaymentProvider.ASAAS,
                    ),
                    db,
                    admin_user,
                )
            assert missing_company.value.status_code == 404
    finally:
        current_tenant_id.reset(token)
