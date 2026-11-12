import csv
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import pymupdf
import openpyxl

class ImportResult:
    def __init__(self, file_path: str, file_type: str):
        self.file_path = file_path
        self.file_type = file_type
        self.links: List[Tuple[int, str]] = []  # (serial_no, url)
        self.duplicates: List[Dict[str, Any]] = [] # list of duplicate occurrences
        self.total_raw_found = 0
        self.total_unique = 0
        self.error: Optional[str] = None

class LinkImporter:
    """Unified file parser supporting PDF, CSV, Excel (.xlsx), and TXT."""
    
    URL_REGEX = re.compile(r'https?://[^\s<>"\',;]+')

    @classmethod
    def import_file(cls, file_path: str) -> ImportResult:
        path = Path(file_path)
        if not path.exists():
            res = ImportResult(file_path, "unknown")
            res.error = f"File not found: {file_path}"
            return res

        ext = path.suffix.lower()
        if ext == ".pdf":
            return cls._import_pdf(path)
        elif ext in [".csv", ".tsv"]:
            return cls._import_csv(path)
        elif ext in [".xlsx", ".xls"]:
            return cls._import_excel(path)
        elif ext in [".txt", ".log"]:
            return cls._import_txt(path)
        else:
            res = ImportResult(file_path, ext)
            res.error = f"Unsupported file extension: {ext}. Expected .pdf, .csv, .xlsx, or .txt"
            return res

    @classmethod
    def _import_pdf(cls, path: Path) -> ImportResult:
        res = ImportResult(str(path), "PDF")
        try:
            doc = pymupdf.open(str(path))
            raw_entries: List[Tuple[Optional[int], str]] = []

            # 1. Parse text line-by-line looking for "<number>\n<url>" patterns
            for page in doc:
                text = page.get_text()
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if line.isdigit() and i + 1 < len(lines):
                        next_line = lines[i + 1]
                        m = cls.URL_REGEX.search(next_line)
                        if m:
                            raw_entries.append((int(line), m.group(0)))
                            i += 2
                            continue
                    else:
                        m = cls.URL_REGEX.search(line)
                        if m:
                            raw_entries.append((None, m.group(0)))
                    i += 1

            # 2. If line parsing yielded fewer than link annotations, extract annotations
            if len(raw_entries) < 10:
                annot_entries = []
                for page in doc:
                    for l in page.get_links():
                        uri = l.get("uri")
                        if uri and cls.URL_REGEX.match(uri):
                            annot_entries.append((None, uri))
                if len(annot_entries) > len(raw_entries):
                    raw_entries = annot_entries

            res.total_raw_found = len(raw_entries)
            cls._deduplicate_and_index(res, raw_entries)
            doc.close()
        except Exception as e:
            res.error = f"Error reading PDF: {e}"
        return res

    @classmethod
    def _import_csv(cls, path: Path) -> ImportResult:
        res = ImportResult(str(path), "CSV")
        try:
            raw_entries: List[Tuple[Optional[int], str]] = []
            with open(path, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                res.error = "CSV file is empty"
                return res

            # Determine URL column index and Serial column index
            url_col_idx = -1
            serial_col_idx = -1

            header = [str(c).strip().lower() for c in rows[0]]
            for idx, col in enumerate(header):
                if any(k in col for k in ["url", "link", "flezen"]):
                    url_col_idx = idx
                elif any(k in col for k in ["no", "serial", "sr", "id", "#"]):
                    serial_col_idx = idx

            start_row = 1 if (url_col_idx != -1 or serial_col_idx != -1) else 0

            # If no header match, auto-detect column containing URLs
            if url_col_idx == -1:
                for row in rows[:10]:
                    for idx, cell in enumerate(row):
                        if cls.URL_REGEX.search(cell):
                            url_col_idx = idx
                            break
                    if url_col_idx != -1:
                        break

            if url_col_idx == -1:
                url_col_idx = 0

            for r_idx in range(start_row, len(rows)):
                row = rows[r_idx]
                if not row or url_col_idx >= len(row):
                    continue
                cell_val = row[url_col_idx].strip()
                m = cls.URL_REGEX.search(cell_val)
                if not m:
                    continue
                url = m.group(0)

                serial = None
                if serial_col_idx != -1 and serial_col_idx < len(row):
                    s_val = row[serial_col_idx].strip()
                    if s_val.isdigit():
                        serial = int(s_val)

                raw_entries.append((serial, url))

            res.total_raw_found = len(raw_entries)
            cls._deduplicate_and_index(res, raw_entries)
        except Exception as e:
            res.error = f"Error reading CSV: {e}"
        return res

    @classmethod
    def _import_excel(cls, path: Path) -> ImportResult:
        res = ImportResult(str(path), "Excel")
        try:
            wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            wb.close()

            if not rows:
                res.error = "Excel sheet is empty"
                return res

            url_col_idx = -1
            serial_col_idx = -1

            header = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
            for idx, col in enumerate(header):
                if any(k in col for k in ["url", "link", "flezen"]):
                    url_col_idx = idx
                elif any(k in col for k in ["no", "serial", "sr", "id", "#"]):
                    serial_col_idx = idx

            start_row = 1 if (url_col_idx != -1 or serial_col_idx != -1) else 0

            if url_col_idx == -1:
                for row in rows[:10]:
                    for idx, cell in enumerate(row):
                        if cell and cls.URL_REGEX.search(str(cell)):
                            url_col_idx = idx
                            break
                    if url_col_idx != -1:
                        break

            if url_col_idx == -1:
                url_col_idx = 0

            raw_entries: List[Tuple[Optional[int], str]] = []
            for r_idx in range(start_row, len(rows)):
                row = rows[r_idx]
                if not row or url_col_idx >= len(row) or row[url_col_idx] is None:
                    continue
                val = str(row[url_col_idx]).strip()
                m = cls.URL_REGEX.search(val)
                if not m:
                    continue
                url = m.group(0)

                serial = None
                if serial_col_idx != -1 and serial_col_idx < len(row) and row[serial_col_idx] is not None:
                    s_str = str(row[serial_col_idx]).strip()
                    if s_str.isdigit():
                        serial = int(s_str)

                raw_entries.append((serial, url))

            res.total_raw_found = len(raw_entries)
            cls._deduplicate_and_index(res, raw_entries)
        except Exception as e:
            res.error = f"Error reading Excel: {e}"
        return res

    @classmethod
    def _import_txt(cls, path: Path) -> ImportResult:
        res = ImportResult(str(path), "TXT")
        try:
            raw_entries: List[Tuple[Optional[int], str]] = []
            with open(path, mode="r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    m = cls.URL_REGEX.search(line)
                    if m:
                        # Check if line starts with a number (e.g. "1. https://..." or "1 https://...")
                        prefix_match = re.match(r'^(\d+)[\.\s:\-)]+', line)
                        serial = int(prefix_match.group(1)) if prefix_match else None
                        raw_entries.append((serial, m.group(0)))

            res.total_raw_found = len(raw_entries)
            cls._deduplicate_and_index(res, raw_entries)
        except Exception as e:
            res.error = f"Error reading TXT: {e}"
        return res

    @classmethod
    def _deduplicate_and_index(cls, res: ImportResult, raw_entries: List[Tuple[Optional[int], str]]):
        """Preserve sequential serial numbering while deduplicating identical URLs."""
        seen: Dict[str, int] = {}
        unique_links: List[Tuple[int, str]] = []
        duplicates: List[Dict[str, Any]] = []

        assigned_index = 1
        for explicit_serial, url in raw_entries:
            serial = explicit_serial if explicit_serial is not None else assigned_index
            if url in seen:
                orig_serial = seen[url]
                duplicates.append({
                    "original_serial": orig_serial,
                    "duplicate_serial": serial,
                    "url": url
                })
            else:
                seen[url] = serial
                unique_links.append((serial, url))
            assigned_index += 1

        res.links = unique_links
        res.duplicates = duplicates
        res.total_unique = len(unique_links)

