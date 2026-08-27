import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.course import Course, CourseModality, CourseType
from app.models.tenant import Tenant
from app.services.tenant_secret_service import (
    MERCADO_PAGO_ACCESS_TOKEN_KEY,
    set_tenant_secret,
)


@pytest.mark.asyncio
async def test_readiness_reports_missing_real_configuration(client, admin_headers):
    response = await client.get('/api/v1/tenants/readiness', headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['ready_for_launch'] is False
    assert payload['percentage'] < 100
    keys = {item['key'] for item in payload['items']}
    assert keys == {'identity', 'branding', 'domain', 'gateway', 'catalog', 'certificates'}


@pytest.mark.asyncio
async def test_readiness_reaches_100_only_with_persisted_requirements(client, admin_headers):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        tenant = await db.get(Tenant, WR_TENANT_ID)
        tenant.legal_name = 'WR Consultoria e Soluções em QSMS Ltda'
        tenant.cnpj = '11222333000181'
        tenant.logo_url = 'https://example.com/logo.svg'
        tenant.primary_color = '#1B7A3A'
        tenant.secondary_color = '#17324D'
        tenant.settings = {'payment_provider': 'MERCADO_PAGO'}
        course = Course(
            id=uuid.uuid4(),
            tenant_id=WR_TENANT_ID,
            code=f'READY-{uuid.uuid4().hex[:6]}',
            name='Curso pronto para catálogo',
            category='SST',
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=100.0,
            is_active=True,
        )
        db.add(course)
        await set_tenant_secret(
            db,
            WR_TENANT_ID,
            MERCADO_PAGO_ACCESS_TOKEN_KEY,
            'APP_USR-test-readiness-token',
        )
        await db.commit()

    response = await client.get('/api/v1/tenants/readiness', headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['ready_for_launch'] is True
    assert payload['percentage'] == 100
    assert payload['completed'] == payload['total_required'] == 6
    assert payload['payment_provider'] == 'MERCADO_PAGO'
    assert payload['active_courses'] == 1
    assert all(item['ready'] for item in payload['items'])
