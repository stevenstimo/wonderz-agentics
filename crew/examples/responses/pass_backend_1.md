Gevonden:
- `web_ui/backend/api_main.py:1524` -> `return DaveDevResponse(answer=_clean_answer_for_ui(answer), confidence=0.85, llm_used="OpenAI")`
- `web_ui/backend/api_main.py:1553` -> `return DaveDevResponse(answer=_clean_answer_for_ui(answer), confidence=0.8, llm_used="Gemini")`

Oorzaak:
- OpenAI/Gemini paden geven output zonder contract-lint; inconsistent formaat ontstaat door ontbrekende post-processing.

Fix voorstel:
- Routeer beide returns via een centrale style-functie voordat antwoord wordt teruggegeven.
- Command: `rg -n 'return DaveDevResponse' web_ui/backend/api_main.py`

Vraag:
- Wil je dat ik deze wijziging direct doorvoer?
