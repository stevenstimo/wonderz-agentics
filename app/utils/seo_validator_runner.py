"""
Draait repo-root ``seo_validator.py`` als subprocess op een gegenereerd Excel-bestand.
Gebruikt asyncio.to_thread zodat de ARQ event loop niet blokkeert.
"""
from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    # app/utils/this_file.py -> parents[0]=utils, [1]=app, [2]=repo root
    return Path(__file__).resolve().parents[2]


def _parse_score(stdout: str) -> int:
    match = re.search(r"Score:.*?(\d+)%", stdout)
    return int(match.group(1)) if match else 0


def _run_validator_subprocess(excel_path: str, job_id: str) -> subprocess.CompletedProcess:
    validator_path = _repo_root() / "seo_validator.py"
    path = Path(excel_path)
    cwd = str(path.resolve().parent)
    return subprocess.run(
        [sys.executable, str(validator_path), str(path.resolve()), "--report"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cwd,
    )


async def validate_seo_excel_output(excel_path: str, job_id: str) -> dict[str, Any]:
    """
    Voert seo_validator.py uit. Exit 2 -> ValueError met leesbare samenvatting.
    Exit 1 -> warnings gelogd, job mag slagen. Exit 0 -> alleen info-log.
    """
    result = await asyncio.to_thread(_run_validator_subprocess, excel_path, job_id)
    exit_code = result.returncode
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if stderr:
        logger.warning(
            "[SEO Validator] stderr job %s: %s",
            job_id,
            stderr[:500],
        )

    logger.info(
        "[SEO Validator] job %s — exit %s\n%s",
        job_id,
        exit_code,
        stdout[:1000],
    )

    if exit_code == 2:
        error_lines = [
            line.strip()
            for line in stdout.split("\n")
            if "❌" in line and len(line.strip()) > 5
        ]
        raise ValueError(
            "SEO output validatie gefaald (exit 2). "
            f"Errors: {'; '.join(error_lines[:5]) or 'zie logs'}"
        )

    if exit_code == 1:
        warning_lines = [
            line.strip()
            for line in stdout.split("\n")
            if "⚠️" in line and len(line.strip()) > 5
        ]
        logger.warning(
            "[SEO Validator] job %s — warnings: %s",
            job_id,
            "; ".join(warning_lines[:5]) or "(geen ⚠️ regels geparsed)",
        )

    score = _parse_score(stdout)
    stem = Path(excel_path).stem
    report_name = f"{stem}_validation_report.md"
    report_path = str(Path(excel_path).resolve().parent / report_name)

    return {
        "passed": exit_code < 2,
        "exit_code": exit_code,
        "score": score,
        "report_path": report_path,
    }
