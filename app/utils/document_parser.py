"""Extract text from uploaded documents. Used by jobs and skills."""

import logging
import re

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "xlsx", "xls", "csv", "docx", "txt", "md", "skill", "png", "jpg", "jpeg"}


def extract_text_from_file(filename: str, raw: bytes) -> str:
    """Extract text from uploaded file. Returns empty string on unsupported/error."""
    ext = (filename or "").lower().split(".")[-1] if "." in (filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type .{ext} not allowed. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    if ext == "pdf":
        try:
            import pdfplumber
            import tempfile
            import os as _os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(raw)
                tmp.flush()
            try:
                with pdfplumber.open(tmp.name) as pdf:
                    parts = []
                    for page in pdf.pages:
                        # layout=True preserves more structure (paragraph/line breaks)
                        page_text = (page.extract_text(layout=True) or "").strip()
                        if page_text:
                            parts.append(page_text)
                    return "\n\n".join(parts)
            finally:
                _os.unlink(tmp.name)
        except ImportError:
            return raw.decode("utf-8", errors="replace")
    if ext in ("txt", "md", "skill"):
        try:
            import chardet
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "utf-8"
            return raw.decode(encoding, errors="replace")
        except ImportError:
            return raw.decode("utf-8", errors="replace")
    if ext == "csv":
        return raw.decode("utf-8", errors="replace")
    if ext == "docx":
        try:
            import io
            from docx import Document
            from docx.oxml.table import CT_Tbl
            from docx.oxml.text.paragraph import CT_P
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            doc = Document(io.BytesIO(raw))
            parts = []

            def process_paragraph(para):
                text = (para.text or "").strip()
                if not text:
                    return
                style_name = (getattr(getattr(para, "style", None), "name", None) or "") or ""
                if style_name.startswith("Heading"):
                    parts.append("\n\n" + text + "\n\n")
                else:
                    parts.append(text)

            def process_table(table):
                seen = set()
                for row in table.rows:
                    for cell in row.cells:
                        cell_text = (cell.text or "").strip()
                        if cell_text and cell_text not in seen:
                            seen.add(cell_text)
                            parts.append(cell_text)

            # Iterate body children in document order so paragraphs and tables are interleaved
            body = doc.element.body
            for child in body.iterchildren():
                if isinstance(child, CT_P):
                    process_paragraph(Paragraph(child, doc))
                elif isinstance(child, CT_Tbl):
                    process_table(Table(child, doc))

            text = "\n\n".join(p.strip() for p in parts if p.strip())
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            return text
        except ImportError:
            return raw.decode("utf-8", errors="replace")
    if ext in ("xlsx", "xls"):
        try:
            import io
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            parts = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    parts.append("\t".join(str(c) if c is not None else "" for c in row))
            return "\n".join(parts)
        except Exception:
            return raw.decode("utf-8", errors="replace")
    if ext in ("png", "jpg", "jpeg"):
        return ""  # Images: no text extraction; caller uses placeholder
    return raw.decode("utf-8", errors="replace")
