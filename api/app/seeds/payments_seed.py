"""
Seed data para pagamentos.
Cria pagamentos de exemplo em diferentes status.
"""

from sqlalchemy import select

from app.models.enrollment import Enrollment
from app.models.payment import Payment, PaymentMethod, PaymentStatus


async def seed_payments(db):
    """Popula o banco com pagamentos de teste."""
    print("\n💳 Populando pagamentos...")

    stmt = select(Enrollment)
    result = await db.execute(stmt)
    enrollments = result.scalars().all()

    if not enrollments:
        print("✗ Matrículas não encontradas, pulando pagamentos")
        return

    payment_data = [
        {"status": PaymentStatus.APROVADO, "method": PaymentMethod.PIX, "installments": None},
        {"status": PaymentStatus.PENDENTE, "method": PaymentMethod.BOLETO, "installments": None},
        {"status": PaymentStatus.RECUSADO, "method": PaymentMethod.CARTAO, "installments": "3x"},
    ]

    for i, enrollment in enumerate(enrollments):
        data = payment_data[i % len(payment_data)]

        stmt = select(Payment).where(Payment.enrollment_id == enrollment.id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            print(f"✓ Pagamento da matrícula {enrollment.id} já existe")
            continue

        payment = Payment(
            enrollment_id=enrollment.id,
            amount=enrollment.price,
            status=data["status"],
            method=data["method"],
            installments=data["installments"],
        )
        db.add(payment)
        print(f"✓ Pagamento da matrícula {enrollment.id} criado ({data['method'].value} - {data['status'].value})")

    await db.commit()
    print("\n✓ Seed de pagamentos concluído!")
