import httpx

from app.core.config import settings


class MercadoPagoError(Exception):
    pass


class MercadoPagoService:
    BASE_URL = "https://api.mercadopago.com/v1"

    @staticmethod
    async def create_preference(
        enrollment_id: str,
        amount: float,
        student_email: str,
        course_name: str,
        access_token: str | None = None,
    ):
        """Cria uma preferência de pagamento no Mercado Pago.

        Em modo mock (MERCADO_PAGO_MOCK_MODE=true), retorna uma
        preferência fake determinística sem chamar a API do MP.
        Usado apenas para testes/integração — nunca em produção.
        """
        if settings.MERCADO_PAGO_MOCK_MODE:
            return {
                "id": f"mock-pref-{enrollment_id}",
                "init_point": f"http://mock-mp.test/checkout?enrollment={enrollment_id}",
            }

        token = access_token or settings.MERCADO_PAGO_ACCESS_TOKEN
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(enrollment_id),
        }

        preference_data = {
            "items": [
                {
                    "title": course_name,
                    "quantity": 1,
                    "unit_price": amount,
                }
            ],
            "payer": {
                "email": student_email,
            },
            "external_reference": str(enrollment_id),
            "back_urls": {
                "success": f"{settings.FRONTEND_URL}/payment/success",
                "failure": f"{settings.FRONTEND_URL}/payment/failure",
                "pending": f"{settings.FRONTEND_URL}/payment/pending",
            },
            "auto_return": "approved",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MercadoPagoService.BASE_URL}/preferences",
                json=preference_data,
                headers=headers,
            )
        
        if response.status_code == 201:
            return response.json()
        raise MercadoPagoError(f"Erro ao criar preferência: {response.text}")
    
    @staticmethod
    async def get_payment_info(payment_id: str, access_token: str | None = None):
        """Obtém informações de um pagamento.

        Em modo mock (MERCADO_PAGO_MOCK_MODE=true), retorna um
        pagamento fake aprovado sem chamar a API do MP. O payment_id
        deve ter o formato "mock-mp-payment-{enrollment_id}".
        """
        if settings.MERCADO_PAGO_MOCK_MODE:
            # Extrai enrollment_id do payment_id mockado
            prefix = "mock-mp-payment-"
            if payment_id.startswith(prefix):
                enrollment_id = payment_id[len(prefix):]
            else:
                enrollment_id = payment_id
            return {
                "external_reference": enrollment_id,
                "preference_id": f"mock-pref-{enrollment_id}",
                "status": "approved",
            }

        token = access_token or settings.MERCADO_PAGO_ACCESS_TOKEN
        headers = {
            "Authorization": f"Bearer {token}",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MercadoPagoService.BASE_URL}/payments/{payment_id}",
                headers=headers,
            )
        
        if response.status_code == 200:
            return response.json()
        raise MercadoPagoError(f"Erro ao obter pagamento: {response.text}")
    
    @staticmethod
    async def refund_payment(payment_id: str, access_token: str | None = None):
        """Reembolsa um pagamento"""
        token = access_token or settings.MERCADO_PAGO_ACCESS_TOKEN
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MercadoPagoService.BASE_URL}/payments/{payment_id}/refunds",
                headers=headers,
            )
        
        if response.status_code == 201:
            return response.json()
        raise MercadoPagoError(f"Erro ao reembolsar pagamento: {response.text}")
