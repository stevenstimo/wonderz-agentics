"""
Client file processor: PDF (pdfplumber) and CSV (pandas); chunk, embed, store in client_knowledge.
"""
import io
import json
import logging

import pdfplumber

from app.services.training import chunk_text_by_chars, generate_embedding

logger = logging.getLogger(__name__)

CHUNK_SIZE = 3200
CHUNK_OVERLAP = 400


class ClientFileProcessor:
    CSV_MAX_ROWS = 6_000
    CSV_MAX_CHARS_PER_ROW = 10_000

    def __init__(self, client_id: str, datasource_id: int, db_pool):  # noqa: ANN001
        self.client_id = client_id
        self.datasource_id = datasource_id
        self.pool = db_pool

    async def process_pdf(self, file_bytes: bytes, filename: str) -> dict:
        """Extract text via pdfplumber, chunk, embed, store. Returns {chunks_created}."""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                parts: list[str] = []
                for page in pdf.pages:
                    t = page.extract_text()
                    if t and t.strip():
                        parts.append(t.strip())
                full_text = "\n\n".join(parts)
        except Exception as e:
            logger.exception("client_file_processor: PDF error %s: %s", filename, e)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET status = 'failed', error_detail = $1, updated_at = now()
                    WHERE id = $2
                    """,
                    str(e),
                    self.datasource_id,
                )
            return {"chunks_created": 0, "error": str(e)}

        if not full_text.strip():
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET status = 'done', chunks_created = 0, finished_at = now(), updated_at = now()
                    WHERE id = $1
                    """,
                    self.datasource_id,
                )
            return {"chunks_created": 0}

        chunks = chunk_text_by_chars(full_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM client_knowledge WHERE datasource_id = $1",
                self.datasource_id,
            )
            stored = 0
            for idx, chunk in enumerate(chunks):
                piece = (chunk or "")[:8000]
                if not piece.strip():
                    continue
                embedding = await generate_embedding(piece)
                await conn.execute(
                    """
                    INSERT INTO client_knowledge
                    (client_id, datasource_id, source_url, page_title, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7, true)
                    """,
                    self.client_id,
                    self.datasource_id,
                    filename,
                    filename,
                    chunk,
                    json.dumps(embedding),
                    idx,
                )
                stored += 1
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'done', chunks_created = $1, finished_at = now(), updated_at = now(), error_detail = NULL
                WHERE id = $2
                """,
                stored,
                self.datasource_id,
            )
        return {"chunks_created": stored}

    async def process_csv(self, file_bytes: bytes, filename: str) -> dict:
        """Read CSV with pandas; one chunk per row (col: value | ...). Enforce row/char limits. Returns counts + optional warning."""
        import pandas as pd

        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as e:
            logger.exception("client_file_processor: CSV read error %s: %s", filename, e)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE client_datasources
                    SET status = 'failed', error_detail = $1, updated_at = now()
                    WHERE id = $2
                    """,
                    str(e),
                    self.datasource_id,
                )
            return {"chunks_created": 0, "rows_processed": 0, "rows_skipped": 0, "error": str(e)}

        total_rows = len(df)
        rows_skipped = 0
        if total_rows > self.CSV_MAX_ROWS:
            df = df.head(self.CSV_MAX_ROWS)
            rows_skipped = total_rows - self.CSV_MAX_ROWS
        warning = None
        if rows_skipped > 0:
            warning = f"Bestand bevat {total_rows} rijen — alleen de eerste {self.CSV_MAX_ROWS} zijn verwerkt."

        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM client_knowledge WHERE datasource_id = $1",
                self.datasource_id,
            )
            stored = 0
            for idx, row in df.iterrows():
                parts = []
                for col, val in row.items():
                    s = str(val) if pd.notna(val) else ""
                    if len(s) > self.CSV_MAX_CHARS_PER_ROW:
                        s = s[: self.CSV_MAX_CHARS_PER_ROW]
                    if s:
                        parts.append(f"{col}: {s}")
                chunk_text = " | ".join(parts)
                if not chunk_text.strip():
                    continue
                piece = (chunk_text or "")[:8000]
                embedding = await generate_embedding(piece)
                await conn.execute(
                    """
                    INSERT INTO client_knowledge
                    (client_id, datasource_id, source_url, page_title, chunk_text, embedding, chunk_index, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6::vector, $7, true)
                    """,
                    self.client_id,
                    self.datasource_id,
                    filename,
                    filename,
                    chunk_text,
                    json.dumps(embedding),
                    idx,
                )
                stored += 1
            error_detail = warning  # store warning in error_detail for UI
            await conn.execute(
                """
                UPDATE client_datasources
                SET status = 'done', chunks_created = $1, finished_at = now(), updated_at = now(), error_detail = $2
                WHERE id = $3
                """,
                stored,
                error_detail,
                self.datasource_id,
            )
        result: dict = {
            "chunks_created": stored,
            "rows_processed": len(df),
            "rows_skipped": rows_skipped,
        }
        if warning:
            result["warning"] = warning
        return result
