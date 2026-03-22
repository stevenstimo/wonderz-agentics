"""
Idempotente seed van eval_suites en eval_cases (regression + capability).
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg

REGRESSION_CASES: list[dict[str, Any]] = [
    {
        "suite": "regression",
        "name": "Basis copywriter job voltooit zonder errors",
        "job_type": "copywriting",
        "input_payload": {
            "job_type": "copywriting",
            "description": "Schrijf 200 woorden over duurzame mode voor een Nederlandse webshop. Toon: professioneel, doelgroep: vrouwen 25-45.",
            "client_id": None,
        },
        "expected_checks": {
            "response_contract": True,
            "lesson_created": True,
        },
    },
    {
        "suite": "regression",
        "name": "CEO intake verwerkt een job post zonder te crashen",
        "job_type": "copywriting",
        "input_payload": {
            "job_type": "copywriting",
            "description": "Blog artikel van 300 woorden over SEO tips voor kleine ondernemers.",
            "client_id": None,
        },
        "expected_checks": {
            "response_contract": False,
            "lesson_created": False,
            "success_statuses": [
                "JOB_READY",
                "COMPLETED",
                "PLAN_PROPOSED",
                "INTAKE_CLARIFICATION",
            ],
        },
    },
    {
        "suite": "regression",
        "name": "Job met lege description crasht niet maar faalt netjes",
        "job_type": "copywriting",
        "input_payload": {
            "job_type": "copywriting",
            "description": "",
            "client_id": None,
        },
        "expected_checks": {
            "response_contract": False,
            "lesson_created": False,
            "terminal_status_in": [
                "FAILED",
                "ERROR",
                "INTAKE_CLARIFICATION",
                "PLAN_PROPOSED",
            ],
            "skip_checks": ["no_unhandled_errors"],
        },
    },
]

CAPABILITY_CASES: list[dict[str, Any]] = [
    {
        "suite": "capability",
        "name": "Copywriter produceert output met alle Response Contract secties",
        "job_type": "copywriting",
        "input_payload": {
            "job_type": "copywriting",
            "description": "Schrijf een LinkedIn artikel van 400 woorden over het belang van contentstrategie voor B2B bedrijven. Inclusief concrete voorbeelden.",
            "client_id": None,
        },
        "expected_checks": {
            "response_contract": True,
            "lesson_created": True,
            "llm_quality_criteria": (
                "De tekst is professioneel, heeft een duidelijke structuur met intro/midden/conclusie, "
                "bevat minimaal één concreet voorbeeld, en is geschikt voor LinkedIn publicatie."
            ),
        },
    },
    {
        "suite": "capability",
        "name": "Lesson wordt aangemaakt na completed job met correcte metadata",
        "job_type": "copywriting",
        "input_payload": {
            "job_type": "copywriting",
            "description": "Productbeschrijving van 150 woorden voor een handgemaakte leren tas. Nadruk op ambacht en duurzaamheid.",
            "client_id": None,
        },
        "expected_checks": {
            "response_contract": True,
            "lesson_created": True,
            "llm_quality_criteria": (
                "De productbeschrijving is verkoopgericht, benadrukt ambacht en duurzaamheid, "
                "en heeft een duidelijke call-to-action."
            ),
        },
    },
    {
        "suite": "capability",
        "name": "STM wordt gevuld na meerdere stappen in een job",
        "job_type": "copywriting",
        "input_payload": {
            "job_type": "copywriting",
            "description": "Schrijf een e-mail nieuwsbrief van 300 woorden voor een restaurant. Aankondiging nieuw seizoensmenu. Toon: warm en uitnodigend.",
            "client_id": None,
        },
        "expected_checks": {
            "response_contract": True,
            "lesson_created": True,
            "stm_populated": True,
        },
    },
]


async def seed_eval_cases(conn: asyncpg.Connection) -> dict[str, int]:
    """Seed de initiële eval suites en cases. Idempotent — veilig om meerdere keren te draaien."""
    inserted_suites = 0
    inserted_cases = 0

    for suite_type, cases in (
        ("regression", REGRESSION_CASES),
        ("capability", CAPABILITY_CASES),
    ):
        desc = (
            "Regression suite — moet altijd ~100% halen"
            if suite_type == "regression"
            else "Capability suite — meet wat het systeem kan verbeteren"
        )
        suite = await conn.fetchrow(
            "SELECT id FROM eval_suites WHERE name = $1",
            suite_type,
        )
        if not suite:
            await conn.execute(
                """
                INSERT INTO eval_suites (name, suite_type, description)
                VALUES ($1, $2, $3)
                """,
                suite_type,
                suite_type,
                desc,
            )
            inserted_suites += 1
            suite = await conn.fetchrow(
                "SELECT id FROM eval_suites WHERE name = $1",
                suite_type,
            )
        suite_id = suite["id"]

        for case in cases:
            existing = await conn.fetchval(
                "SELECT id FROM eval_cases WHERE suite_id = $1 AND name = $2",
                suite_id,
                case["name"],
            )
            if not existing:
                await conn.execute(
                    """
                    INSERT INTO eval_cases (suite_id, name, job_type, input_payload, expected_checks)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
                    """,
                    suite_id,
                    case["name"],
                    case["job_type"],
                    json.dumps(case["input_payload"]),
                    json.dumps(case["expected_checks"]),
                )
                inserted_cases += 1

    return {"suites_inserted": inserted_suites, "cases_inserted": inserted_cases}
