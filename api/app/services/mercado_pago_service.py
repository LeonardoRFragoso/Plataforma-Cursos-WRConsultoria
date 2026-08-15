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
        """Cria uma preferência de pagamento no Mercado Pago"""
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
    async def get_payment_info(payment_id: str):
        """Obtém informações de um pagamento"""
        headers = {
            "Authorization": f"Bearer {settings.MERCADO_PAGO_ACCESS_TOKEN}",
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
    async def refund_payment(payment_id: str):
        """Reembolsa um pagamento"""
        headers = {
            "Authorization": f"Bearer {settings.MERCADO_PAGO_ACCESS_TOKEN}",
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
