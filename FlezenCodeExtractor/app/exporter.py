import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.config import EXPORTS_DIR

class ExcelExporter:
    """Exports extraction results into a professionally formatted Excel workbook."""

    # Colors
    HEADER_FILL = PatternFill(start_color="1E2238", end_color="1E2238", fill_type="solid")
    HEADER_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    
    ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    WHITE_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    
    # Status Fills
    STATUS_SUCCESS = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")     # Soft Green
    STATUS_FAILED = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")      # Soft Red
    STATUS_REVIEW = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")      # Soft Amber
    STATUS_DUPLICATE = PatternFill(start_color="FCE7F3", end_color="FCE7F3", fill_type="solid")   # Soft Pink

    THIN_BORDER = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    COLUMNS = [
        ("Serial #", 10),
        ("Flezen URL", 48),
        ("Extracted Code", 22),
        ("Screenshot Filename", 22),
        ("OCR Confidence (%)", 18),
        ("Processing Status", 18),
        ("Verification Status", 20),
        ("Notes / Error Message", 35)
    ]

    @classmethod
    def export(cls, rows: List[Dict[str, Any]], session_name: str,
               destination_path: Optional[str] = None) -> str:
        """
        Generates multi-tab workbook:
        - All Results
        - Successful
        - Failed
        - Needs Review
        - Duplicate Codes
        """
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        # Categorize rows
        all_rows = rows
        successful_rows = [r for r in rows if r.get("processing_status") == "SUCCESS"]
        failed_rows = [r for r in rows if r.get("processing_status") == "FAILED"]
        review_rows = [r for r in rows if r.get("processing_status") == "NEEDS_REVIEW"]

        # Identify duplicate codes
        code_counts: Dict[str, int] = {}
        for r in rows:
            c = (r.get("code") or "").strip()
            if c:
                code_counts[c] = code_counts.get(c, 0) + 1
        duplicate_rows = [r for r in rows if (r.get("code") or "").strip() in code_counts and code_counts[(r.get("code") or "").strip()] > 1]

        sheets_data = [
            ("All Results", all_rows),
            ("Successful", successful_rows),
            ("Failed", failed_rows),
            ("Needs Review", review_rows),
            ("Duplicate Codes", duplicate_rows),
        ]

        for title, data in sheets_data:
            ws = wb.create_sheet(title=title)
            cls._populate_sheet(ws, data)

        if not destination_path:
            clean_session = "".join(c if c.isalnum() or c in " _-" else "_" for c in session_name)
            filename = f"Flezen_Codes_{clean_session}.xlsx"
            destination_path = str(EXPORTS_DIR / filename)

        wb.save(destination_path)
        return destination_path

    @classmethod
    def _populate_sheet(cls, ws, rows: List[Dict[str, Any]]):
        ws.views.sheetView[0].showGridLines = True

        # Header Row
        for col_idx, (header_text, width) in enumerate(cls.COLUMNS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header_text)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = Alignment(horizontal="center" if col_idx in [1, 5, 6, 7] else "left", vertical="center")
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.row_dimensions[1].height = 28

        # Data Rows
        for row_idx, r in enumerate(rows, 2):
            status = r.get("processing_status", "PENDING")
            conf_val = f"{float(r.get('confidence', 0)):.1f}%" if r.get("confidence") else "0.0%"

            values = [
                r.get("serial_no", ""),
                r.get("url", ""),
                r.get("code", "") or "—",
                r.get("screenshot_filename", "") or "—",
                conf_val,
                status,
                r.get("verification_status", "UNVERIFIED"),
                r.get("error_message", "") or ""
            ]

            is_even = (row_idx % 2 == 0)
            row_fill = cls.ZEBRA_FILL if is_even else cls.WHITE_FILL

            for col_idx, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = Font(name="Segoe UI", size=10)
                cell.border = cls.THIN_BORDER
                cell.fill = row_fill
                
                # Alignments
                if col_idx in [1, 5]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx in [6, 7]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif col_idx == 3:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.font = Font(name="Consolas", size=10.5, bold=True)
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

                # Highlight Status column
                if col_idx == 6:
                    if status == "SUCCESS":
                        cell.fill = cls.STATUS_SUCCESS
                        cell.font = Font(name="Segoe UI", size=10, bold=True, color="065F46")
                    elif status == "FAILED":
                        cell.fill = cls.STATUS_FAILED
                        cell.font = Font(name="Segoe UI", size=10, bold=True, color="991B1B")
                    elif status == "NEEDS_REVIEW":
                        cell.fill = cls.STATUS_REVIEW
                        cell.font = Font(name="Segoe UI", size=10, bold=True, color="92400E")

            ws.row_dimensions[row_idx].height = 22

