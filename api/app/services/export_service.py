import csv
import io
from datetime import datetime
from uuid import UUID

from openpyxl import Workbook


class ExportService:
    """Converte listas de dicionários em CSV ou XLSX."""

    @staticmethod
    def _normalize(value):
        if value is None:
            return ""
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def to_csv(rows: list[dict], columns: list[str] | None = None) -> bytes:
        if not rows and not columns:
            return b""
        columns = columns or list(rows[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ExportService._normalize(row.get(k, "")) for k in columns})
        return output.getvalue().encode("utf-8-sig")

    @staticmethod
    def to_xlsx(rows: list[dict], columns: list[str] | None = None) -> bytes:
        if not rows and not columns:
            return b""
        columns = columns or list(rows[0].keys())
        workbook = Workbook()
        sheet = workbook.active
        if sheet is None:
            sheet = workbook.create_sheet()
        sheet.title = "Dados"
        sheet.append(columns)
        for row in rows:
            sheet.append([ExportService._normalize(row.get(k, "")) for k in columns])
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return output.getvalue()
