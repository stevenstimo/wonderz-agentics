# Quick Start Guide

## Setup (5 minuten)

### 1. Installeer dependencies
```bash
pip install -r requirements.txt
```

### 2. Configureer API key
```bash
# Kopieer example
cp .env.example .env

# Edit .env en voeg je API key toe
# ANTHROPIC_API_KEY=sk-ant-api03-jouw-nieuwe-key-hier
```

⚠️ **BELANGRIJK**: 
- Revoke eerst je oude API key via https://console.anthropic.com/settings/keys
- Maak een nieuwe aan
- Kopieer deze naar je .env file

### 3. Test de setup
```bash
python main.py
```

## Gebruik Voorbeelden

### Basis: Volledig project bouwen
```bash
python main.py
```

Je wordt gevraagd om:
- Project beschrijving
- Programmeertaal (optioneel)
- Deployment platform
- Max review iteraties

### Advanced: Custom workflows
```bash
python examples.py
```

Kies uit voorbeelden zoals:
- Security audit
- Feature toevoegen aan bestaande code
- Dockerfile optimalisatie
- Monitoring setup

### Programmatisch gebruik

```python
from orchestrator import DevelopmentOrchestrator

orchestrator = DevelopmentOrchestrator()

result = orchestrator.run_full_workflow(
    project_idea="Een blog API met FastAPI",
    language="Python",
    platform="docker"
)

print(f"Session ID: {result['session_id']}")
```

## Output Structuur

Alle outputs worden opgeslagen in `output/` directory:

```
output/
├── requirements/
│   └── 20240210_120000_requirements.md
├── code/
│   ├── 20240210_120000_main.py
│   ├── 20240210_120000_config.py
│   └── 20240210_120000_development_full.md
├── reviews/
│   └── 20240210_120000_review_iteration_1.md
└── devops/
    ├── 20240210_120000_Dockerfile
    ├── 20240210_120000_docker-compose.yml
    └── 20240210_120000_deployment_full.md
```

## Workflow Stappen

Het systeem doorloopt automatisch:

1. **Product Owner** 
   - Analyseert je idee
   - Maakt technische requirements
   - Output: requirements.md

2. **Developer**
   - Implementeert de requirements
   - Schrijft alle benodigde code files
   - Output: .py, .js, .ts, etc. files

3. **Reviewer**
   - Review op bugs, security, style
   - Geeft status: APPROVED/NEEDS_CHANGES/REJECTED
   - Kan itereren met fixes
   - Output: review reports

4. **DevOps**
   - Maakt Dockerfile
   - Docker Compose voor local dev
   - CI/CD pipeline
   - Output: deployment configs

## Tips

### Voor beste resultaten
- Wees specifiek in je project beschrijving
- Noem technologieën die je wilt gebruiken
- Geef context over het doel van het project

### Voorbeeld goede project beschrijving
```
Een RESTful API voor een todo-lijst applicatie met:
- User authenticatie (JWT)
- CRUD operations voor todos
- PostgreSQL database
- Rate limiting
- API documentation met Swagger
```

### Voorbeeld minder goede beschrijving
```
Een todo app
```

### Kosten besparen
- Gebruik Haiku model voor simpele taken (pas aan in config.py)
- Verminder max_review_iterations
- Test eerst met kleine projecten

### Aanpassen agents
Je kunt de agent prompts aanpassen in:
- `agents/product_owner.py` - SYSTEM_PROMPT
- `agents/developer.py` - SYSTEM_PROMPT
- `agents/reviewer.py` - SYSTEM_PROMPT
- `agents/devops.py` - SYSTEM_PROMPT

## Troubleshooting

### "Geen API key gevonden"
- Check of .env file bestaat
- Check of ANTHROPIC_API_KEY is ingevuld
- Check geen spaties of aanhalingstekens rond de key

### "Rate limit exceeded"
- Wacht een paar minuten
- Verhoog de wachttijd tussen requests
- Upgrade je Anthropic plan

### Code werkt niet zoals verwacht
- Review de requirements - zijn ze duidelijk genoeg?
- Run de code review opnieuw met focus_areas
- Gebruik de reviewer.suggest_improvements() functie

### Output files niet gevonden
- Check of output/ directories zijn aangemaakt
- Kijk naar de console output voor filepaths
- Elk bestand heeft een session_id prefix

## Volgende Stappen

1. **Test het systeem** met een klein project
2. **Pas agents aan** naar jouw voorkeuren
3. **Voeg custom agents toe** (bijv. Tester, Designer)
4. **Bouw web interface** (zie README voor Fase 3)

## Support

- Documentatie: Zie README.md voor details
- Examples: Run `python examples.py` voor voorbeelden
- Anthropic API docs: https://docs.anthropic.com

Veel plezier met bouwen! 🚀
