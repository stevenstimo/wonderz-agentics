# Overnight Prompt B — Training Workflow — Summary

## Wat is gedaan
- **B1** `tests/test_training_chunking.py`: Drie tests toegevoegd (test_chunk_basic, test_chunk_short_text, test_chunk_no_empty). Gebruik van `chunk_text` uit `app.services.training` (retourneert `List[Tuple[str, int]]`).
- **B2** `app/routes/agents.py`: POST `/api/agents/{id}/train` retourneert direct 200 met `{ status: "training_started", url, agent_id }`. URL moet met `https://` beginnen. `knowledge_base_sources` wordt direct bijgewerkt met status `"processing"`; een `BackgroundTasks` taak voert de training uit en zet status op `"active"` of `"failed"`. `app/services/training.py`: bij `update_knowledge_sources` wordt `"status": "active"` in de entry gezet.
- **B3** `app/services/job_pipeline.py`: Per step wordt agent-specifieke kennis opgehaald: `agent_id` uit de step of eerste actieve agent met dezelfde `role`; `TrainingWorkflow.retrieve_context(agent_id, query, top_k=5)`; resultaat in `context["_knowledge_block"]` als "## Relevante kennis" + chunks.
- **B4** `web_ui/frontend/src/AgentDetail.jsx`: Sectie "Knowledge Base" in het profieltab: lijst van `knowledge_base_sources` met status-badge (processing/active/failed), URL-invoer + knop "Train", melding en polling elke 5s tot status niet meer "processing" is. `loadDetail` retourneert nu de opgehaalde JSON voor gebruik in de poll.

## Aannames
- `# assumption-based:` in job_pipeline: eerste actieve agent met matching role als step geen `agent_id` heeft.
- Training background task gebruikt de bestaande event loop (`async def _run_training_background`); pool via `get_db()` in de taak.
