"""Reconciliação segura de matrículas duplicadas.

Prioridade de resolução:
1. Registros com histórico (pagamentos, certificados, presenças) têm precedência
   sobre simples status.
2. Apenas uma matrícula do grupo (student_id, class_id) pode possuir histórico.
   Se várias tiverem histórico, a reconciliação é abortada sem apagar dados.
3. Sem histórico, a prioridade de status é:
   CONCLUIDA > CONFIRMADA > PENDENTE > CANCELADA.
4. Desempate pelo menor id.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

STATUS_PRIORITY = {
    "CONCLUIDA": 0,
    "CONFIRMADA": 1,
    "PENDENTE": 2,
    "CANCELADA": 3,
}


def _canonical_id(rows: list) -> UUID:
    """Escolhe a matrícula canônica de um grupo duplicado."""
    rows_with_children = [
        r for r in rows if (r.payment_count + r.certificate_count + r.attendance_count) > 0
    ]
    if len(rows_with_children) > 1:
        return None
    if len(rows_with_children) == 1:
        return rows_with_children[0].id

    sorted_rows = sorted(
        rows,
        key=lambda r: (STATUS_PRIORITY.get(r.status, 99), r.id),
    )
    return sorted_rows[0].id


def reconcile_enrollments(conn: Connection) -> None:
    """Remove matrículas duplicadas preservando a canônica e seus filhos."""
    duplicate_groups = conn.execute(
        text(
            """
            SELECT student_id, class_id, array_agg(id ORDER BY id) AS ids
            FROM enrollments
            GROUP BY student_id, class_id
            HAVING count(*) > 1
        """
        )
    ).fetchall()

    for student_id, class_id, ids in duplicate_groups:
        rows = conn.execute(
            text(
                """
                SELECT
                    e.id,
                    e.status,
                    (SELECT count(*) FROM payments WHERE enrollment_id = e.id) AS payment_count,
                    (SELECT count(*) FROM certificates WHERE enrollment_id = e.id) AS certificate_count,
                    (SELECT count(*) FROM attendances WHERE enrollment_id = e.id) AS attendance_count
                FROM enrollments e
                WHERE e.id = ANY(:ids)
                ORDER BY e.id
            """
            ),
            {"ids": ids},
        ).fetchall()

        total_certs = sum(r.certificate_count for r in rows)
        if total_certs > 1:
            raise RuntimeError(
                f"Cannot reconcile duplicate enrollments for student {student_id} and class {class_id}: "
                "multiple certificates found. Manual intervention required."
            )

        canonical = _canonical_id(rows)
        if canonical is None:
            raise RuntimeError(
                f"Cannot reconcile duplicate enrollments for student {student_id} and class {class_id}: "
                "multiple rows have linked history. Manual intervention required."
            )

        non_canonical = [r.id for r in rows if r.id != canonical]
        for enrollment_id in non_canonical:
            conn.execute(
                text("DELETE FROM enrollments WHERE id = :id"),
                {"id": enrollment_id},
            )
