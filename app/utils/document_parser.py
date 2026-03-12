"""Extract text from uploaded documents. Used by jobs and skills."""

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
                    return "\n".join((p.extract_text() or "") for p in pdf.pages)
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
            from docx import Document as DocxDocument
            from docx.oxml.table import CT_Tbl
            from docx.oxml.text.paragraph import CT_P
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            doc = DocxDocument(io.BytesIO(raw))
            body = doc.element.body
            parts = []
            for child in body.iterchildren():
                if isinstance(child, CT_P):
                    para = Paragraph(child, doc)
                    if para.text.strip():
                        parts.append(para.text)
                elif isinstance(child, CT_Tbl):
                    tbl = Table(child, doc)
                    for row in tbl.rows:
                        row_text = "\t".join(cell.text.strip() for cell in row.cells)
                        if row_text.strip():
                            parts.append(row_text)
            return "\n".join(parts)
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
