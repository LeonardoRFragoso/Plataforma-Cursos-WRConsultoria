import mercado_pago
from app.core.config import settings

sdk = mercado_pago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)

class MercadoPagoService:
    @staticmethod
    async def create_preference(enrollment_id: str, amount: float, student_email: str, course_name: str):
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
        
        request_options = mercado_pago.config.RequestOptions()
        request_options.custom_headers = {
            "X-Idempotency-Key": str(enrollment_id),
        }
        
        preference_response = sdk.preference().create(preference_data, request_options)
        return preference_response
    
    @staticmethod
    async def get_payment_info(payment_id: str):
        payment_response = sdk.payment().get(payment_id)
        return payment_response
    
    @staticmethod
    async def refund_payment(payment_id: str):
        refund_data = {
            "id": payment_id,
        }
        refund_response = sdk.refund().create(refund_data)
        return refund_response
