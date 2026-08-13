import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.core.utils import utc_now


class CertificateService:
    @staticmethod
    def generate_certificate_pdf(
        student_name: str,
        course_name: str,
        course_code: str,
        carga_horaria: int,
        certificate_number: str,
        validation_code: str,
        responsible_admin_name: str,
        issued_date: datetime | None = None,
    ) -> bytes:
        if issued_date is None:
            issued_date = utc_now()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=12,
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        
        footer_style = ParagraphStyle(
            'CustomFooter',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
        )
        
        elements = []
        
        elements.append(Spacer(1, 0.5*inch))
        
        elements.append(Paragraph("CERTIFICADO DE CONCLUSÃO", title_style))
        elements.append(Spacer(1, 0.3*inch))
        
        elements.append(Paragraph(f"Certificamos que <b>{student_name}</b>", body_style))
        elements.append(Spacer(1, 0.2*inch))
        
        elements.append(Paragraph(
            f"completou com sucesso o curso <b>{course_name}</b> ({course_code})",
            body_style
        ))
        elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Paragraph(
            f"com carga horária de <b>{carga_horaria} horas</b>",
            body_style
        ))
        elements.append(Spacer(1, 0.3*inch))
        
        formatted_date = issued_date.strftime("%d de %B de %Y").replace(
            "January", "janeiro"
        ).replace(
            "February", "fevereiro"
        ).replace(
            "March", "março"
        ).replace(
            "April", "abril"
        ).replace(
            "May", "maio"
        ).replace(
            "June", "junho"
        ).replace(
            "July", "julho"
        ).replace(
            "August", "agosto"
        ).replace(
            "September", "setembro"
        ).replace(
            "October", "outubro"
        ).replace(
            "November", "novembro"
        ).replace(
            "December", "dezembro"
        )
        
        elements.append(Paragraph(f"Emitido em {formatted_date}", body_style))
        elements.append(Spacer(1, 0.4*inch))
        
        elements.append(Paragraph(f"<b>Responsável:</b> {responsible_admin_name}", body_style))
        elements.append(Spacer(1, 0.3*inch))
        
        elements.append(Paragraph(f"<b>Número do Certificado:</b> {certificate_number}", footer_style))
        elements.append(Paragraph(f"<b>Código de Validação:</b> {validation_code}", footer_style))
        elements.append(Spacer(1, 0.2*inch))
        
        elements.append(Paragraph(
            "Valide este certificado em: https://wrcursos.com.br/validar",
            footer_style
        ))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
