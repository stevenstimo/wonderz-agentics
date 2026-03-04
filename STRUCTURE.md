# Project Structuur

```
multi-agent-dev-system/
│
├── 📋 Documentatie
│   ├── README.md              # Hoofddocumentatie
│   ├── QUICKSTART.md          # Snelle start gids
│   └── FEATURES.md            # Complete features lijst
│
├── 🔧 Configuratie
│   ├── .env.example           # API key template
│   ├── .gitignore            # Git ignore (beschermt .env!)
│   ├── requirements.txt       # Python dependencies
│   ├── config.py             # Agent configuratie
│   └── setup.sh              # Installatie script
│
├── 🤖 Agents
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── product_owner.py  # Requirements agent
│   │   ├── developer.py      # Code generation agent
│   │   ├── reviewer.py       # Code review agent
│   │   └── devops.py         # Deployment agent
│   │
│   ├── orchestrator.py       # Workflow orchestration
│   └── utils.py              # Helper functies
│
├── 🚀 Entry Points
│   ├── main.py               # Hoofdapplicatie
│   └── examples.py           # Voorbeeld workflows
│
└── 📁 Output (wordt aangemaakt bij eerste run)
    ├── requirements/         # Product Owner outputs
    ├── code/                # Developer code files
    ├── reviews/             # Code review rapporten
    └── devops/              # Deployment configs
```

## Bestands Uitleg

### 📋 Documentatie

**README.md**
- Algemene introductie
- Architectuur uitleg
- Installatie instructies
- Product informatie

**QUICKSTART.md**
- 5-minuten setup guide
- Gebruik voorbeelden
- Troubleshooting
- Tips & tricks

**FEATURES.md**
- Complete feature lijst per agent
- API documentatie
- Use cases
- Roadmap

### 🔧 Configuratie

**.env.example**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-jouw-key-hier
MODEL_NAME=claude-sonnet-4-20250514  # optioneel
```

**config.py**
```python
# API configuratie
# Agent settings (model, temperature, tokens)
# Output directories
```

**requirements.txt**
```
anthropic>=0.18.0
python-dotenv>=1.0.0
pydantic>=2.0.0
rich>=13.0.0
```

### 🤖 Agents

**agents/product_owner.py** (~100 regels)
- Requirements analyse
- Technische specificaties
- Acceptatiecriteria

**agents/developer.py** (~150 regels)
- Code implementatie
- Feature toevoegen
- Code parsing

**agents/reviewer.py** (~150 regels)
- Code review
- Security audit
- Verbetervoorstellen

**agents/devops.py** (~200 regels)
- Dockerfile generatie
- CI/CD pipelines
- Deployment configs
- Monitoring setup

**orchestrator.py** (~250 regels)
- Workflow management
- Agent coördinatie
- File handling
- Progress tracking

**utils.py** (~150 regels)
- JSON helpers
- Token/cost calculatie
- Code extraction
- Session logging

### 🚀 Entry Points

**main.py**
```bash
python main.py
# → Interactive CLI voor complete workflow
```

**examples.py**
```bash
python examples.py
# → 7 advanced voorbeelden:
#   1. Custom workflow
#   2. Security audit
#   3. Feature addition
#   4. Iterative refinement
#   5. Quick MVP
#   6. Dockerfile optimization
#   7. Monitoring setup
```

## File Sizes

| File | Lines | Purpose |
|------|-------|---------|
| README.md | ~100 | Documentatie |
| QUICKSTART.md | ~200 | Setup gids |
| FEATURES.md | ~350 | Feature documentatie |
| config.py | ~60 | Configuratie |
| product_owner.py | ~100 | Requirements agent |
| developer.py | ~150 | Code agent |
| reviewer.py | ~150 | Review agent |
| devops.py | ~200 | DevOps agent |
| orchestrator.py | ~250 | Workflow engine |
| main.py | ~150 | CLI interface |
| examples.py | ~200 | Voorbeelden |
| utils.py | ~150 | Utilities |
| **TOTAAL** | **~2100** | Complete systeem |

## Output Structuur

Na het runnen van `main.py` wordt deze structuur aangemaakt:

```
output/
├── requirements/
│   └── 20240210_153000_requirements.md
│
├── code/
│   ├── 20240210_153000_main.py
│   ├── 20240210_153000_api.py
│   ├── 20240210_153000_models.py
│   └── 20240210_153000_development_full.md
│
├── reviews/
│   ├── 20240210_153000_review_iteration_1.md
│   └── 20240210_153000_review_iteration_2.md
│
└── devops/
    ├── 20240210_153000_Dockerfile
    ├── 20240210_153000_docker-compose.yml
    ├── 20240210_153000_.github_workflows_ci.yml
    └── 20240210_153000_deployment_full.md
```

## Dependencies

### Python Packages
- **anthropic** - Claude API client
- **python-dotenv** - Environment variables
- **pydantic** - Data validation
- **rich** - Terminal formatting

### System Requirements
- Python 3.9+
- pip
- (optioneel) virtual environment

## Veiligheid

### Bestanden die NOOIT gecommit mogen worden:
```gitignore
.env                  # ⚠️ BEVAT API KEY
output/              # (optioneel)
__pycache__/
*.pyc
```

### Bestanden die WEL gecommit moeten worden:
```
✓ .env.example
✓ .gitignore
✓ Alle .py files
✓ Alle .md files
✓ requirements.txt
✓ setup.sh
```

## Next Steps

1. ✅ Download het complete systeem
2. ✅ Run `./setup.sh` (of handmatig setup)
3. ✅ Configureer `.env` met je API key
4. ✅ Test met `python main.py`
5. ✅ Experimenteer met `python examples.py`
6. ✅ Pas aan naar je behoeften

## Aanpassingen Maken

### Nieuwe Agent Toevoegen
1. Maak `agents/jouw_agent.py`
2. Implementeer dezelfde API pattern
3. Voeg toe aan `orchestrator.py`
4. Update `agents/__init__.py`

### Agent Prompts Aanpassen
- Edit `SYSTEM_PROMPT` in elke agent file
- Pas temperature/tokens aan in `config.py`

### Custom Workflow
- Gebruik individual agents programmatisch
- Zie `examples.py` voor inspiratie

## Support

- Issues? Check QUICKSTART.md → Troubleshooting
- Vragen? Zie FEATURES.md → Resources
- Bugs? Check de agent outputs in `output/`

Veel plezier! 🚀
