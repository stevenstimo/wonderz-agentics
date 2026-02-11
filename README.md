# Multi-Agent Development System

Een multi-agent systeem met Claude AI voor gestructureerde softwareontwikkeling.

## 🏗️ Architectuur

Het systeem bestaat uit 4 gespecialiseerde agents:

1. **Product Owner Agent** - Vertaalt vage ideeën naar technische requirements
2. **Developer Agent** - Schrijft de daadwerkelijke code
3. **Reviewer Agent** - Controleert code op bugs, security en stijl
4. **DevOps Agent** - Beheert deployment, Docker, CI/CD

## 📋 Vereisten

- Python 3.9+
- Claude API key (van Anthropic Console)

## 🚀 Installatie

1. **Clone/download dit project**

2. **Installeer dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configureer API key:**
   
   Maak een `.env` file aan in de root:
```bash
ANTHROPIC_API_KEY=jouw-nieuwe-api-key-hier
```

⚠️ **BELANGRIJK**: 
- Revoke eerst je oude API key via https://console.anthropic.com/settings/keys
- Maak een nieuwe aan
- Deel deze NOOIT in chat of commits

## 💻 Gebruik

### Basis gebruik:
```bash
python main.py
```

Je wordt gevraagd om je project idee in te voeren. Het systeem doorloopt dan:
1. Requirements analyse
2. Code ontwikkeling
3. Code review
4. DevOps setup

### Voorbeeld:
```bash
python main.py

> Beschrijf je project idee: Een todo-lijst API met FastAPI en SQLite

[Product Owner Agent analyseert...]
[Developer Agent schrijft code...]
[Reviewer Agent controleert...]
[DevOps Agent maakt deployment files...]
```

## 📁 Project Structuur

```
multi-agent-dev/
├── main.py              # Hoofdscript
├── agents/              # Agent definities
│   ├── product_owner.py
│   ├── developer.py
│   ├── reviewer.py
│   └── devops.py
├── orchestrator.py      # Workflow beheer
├── utils.py            # Helper functies
├── .env                # API key (NIET committen!)
├── .env.example        # Voorbeeld
├── requirements.txt    # Dependencies
└── output/             # Gegenereerde bestanden
```

## 🔧 Configuratie

Je kunt de agents aanpassen in `config.py`:
- Model selectie (haiku, sonnet, opus)
- Temperature settings
- Max tokens
- Agent prompts

## 📝 Volgende stappen

- [ ] Test met een simpel project
- [ ] Pas agent prompts aan naar jouw voorkeuren
- [ ] Voeg custom agents toe
- [ ] Migreer naar web-applicatie (Fase 3)

## 🤝 Contributing

Dit is jouw persoonlijke development tool - pas aan zoals je wilt!

## ⚖️ License

MIT
