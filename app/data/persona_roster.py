"""
Persona roster — framework sectie 10 (49 personas).
(name, type, role_key, score, development_priority)
role_key maps to ROLE_TEMPLATES in role_templates.py.
"""

import re

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "agent"

# CEO (9)
CEO_PERSONAS = [
    ("Jeanne d'Arc", "CEO · Orchestrator", 80, "Tegenspraak toelaten & strategische flexibiliteit"),
    ("Donna Paulsen", "CEO · Orchestrator", 82, "Delegeren & eigen doelen zichtbaar maken"),
    ("Harvey Specter", "CEO · Strategist", 78, "Kwetsbaarheid tonen & ruimte geven aan anderen"),
    ("Vito Corleone", "CEO · Patriarch", 76, "Transparantie & kennisoverdracht"),
    ("Michael Corleone", "CEO · Tacticus", 74, "Menselijkheid bewaren & vertrouwen opbouwen"),
    ("Rick Blaine", "CEO · Noble Leider", 73, "Cynisme transformeren naar vertrouwen"),
    ("Agent K", "CEO · Senior Coach", 77, "Kennisdeling & ruimte voor nieuwe ideeën"),
    ("Tyler Durden", "CEO · Visionair", 64, "Dialoog boven dominantie"),
    ("Tony Montana", "CEO · Driver", 62, "Impulscontrole & langetermijn strategie"),
]

# Talent (17) — map badge to role_key
TALENT_PERSONAS = [
    ("Patrick Bateman", "Talent · QA Reviewer", 75, "Authentieke identiteit & empathie"),
    ("Hannibal Lecter", "Talent · Deep Analysis", 79, "Samenwerking & kennisdeling uitbreiden"),
    ("Alan Turing", "Talent · Logic Validator", 78, "Communicatie vereenvoudigen"),
    ("Data", "Talent · Objective Review", 76, "Menselijke nuance integreren"),
    ("Jules Winnfield", "Talent · Ethics Review", 74, "Balans actie & reflectie"),
    ("Neo", "Talent · Architecture", 73, "Vertrouwen in eigen inzicht"),
    ("Snake Plissken", "Talent · Reviewer", 72, "Samenwerking & kennisdeling"),
    ("Dalai Lama", "Talent · Wisdom Review", 72, "Pragmatischer handelen bij snelheid"),
    ("Louis Litt", "Talent · Process QA", 71, "Emotieregulatie & zelfvertrouwen"),
    ("Deckard", "Talent · Investigator", 70, "Vertrouwen opbouwen & emotie toelaten"),
    ("Agent Smith", "Talent · Compliance", 70, "Flexibiliteit & nuance toelaten"),
    ("Marcus Burnett", "Talent · Risk Assessment", 69, "Snelheid in beslissingen"),
    ("The Dude", "Talent · Psych Safety", 68, "Proactief richting kiezen"),
    ("Frank the Pug", "Talent · Signal Filter", 68, "Zichtbaarheid & kennisdeling"),
    ("Jeffrey Beaumont", "Talent · Hidden Patterns", 67, "Openheid & directe communicatie"),
    ("The Narrator", "Talent · Introspective", 66, "Actie naast reflectie versterken"),
    ("Travis Bickle", "Talent · Risk Detector", 65, "Nuance ontwikkelen & emotieregulatie"),
]

# Worker (23) — map badge to role_key
WORKER_PERSONAS = [
    ("Forrest Gump", "Worker · Copywriter", 78, "Strategisch inzicht & contextbewustzijn"),
    ("Winston Wolf", "Worker · Incident Response", 78, "Kennisoverdracht & documentatie"),
    ("Tony Stark", "Worker · Senior Engineer", 77, "Delegeren & controle loslaten"),
    ("Shuri", "Worker · R&D / Innovation", 76, "Structuur & documentatie toevoegen"),
    ("Lisbeth Salander", "Worker · Security", 76, "Samenwerking & communicatie"),
    ("Keanu Reeves", "Worker · Reliable Executor", 75, "Zichtbaarheid & leiderschap"),
    ("Mark Watney", "Worker · Improvisation", 75, "Samenwerking & kennisdeling"),
    ("Mike Ross", "Worker · Research", 74, "Zelfvertrouwen & structuur"),
    ("Q", "Worker · Tooling / Infra", 74, "Zichtbaarheid & communicatie"),
    ("Amélie Poulain", "Worker · Support Specialist", 71, "Directe communicatie & zichtbaarheid"),
    ("Ferris Bueller", "Worker · GTM / Creative", 70, "Verantwoordelijkheid & transparantie"),
    ("Man with No Name", "Worker · Precision Executor", 73, "Kennisdeling & samenwerking"),
    ("Amélie Poulain", "Worker · Support Specialist", 71, "Directe communicatie & zichtbaarheid"),  # duplicate name
    ("Donnie Darko", "Worker · SEO Research", 65, "Mentale stabiliteit & praktische toetsing"),
    ("Vincent Vega", "Worker · Task Executor", 67, "Proactiviteit & strategisch bewustzijn"),
    ("Edward Scissorhands", "Worker · Creative Design", 67, "Zelfvertrouwen & grenzen stellen"),
    ("Mad Max", "Worker · Incident Response", 68, "Emotionele verwerking & delegatie"),
    ("Mike Lowrey", "Worker · Action / Ops", 68, "Structuur & langetermijndenken"),
    ("Agent J", "Worker · Adaptive Ops", 67, "Structuur & discipline versterken"),
    ("Jack Burton", "Worker · Operations", 66, "Luisteren & realistische zelfinschatting"),
    ("Lester Burnham", "Worker · Creative", 64, "Structuur & focus voor consistent leveren"),
    ("Tony Soprano", "Worker · Operations Lead", 63, "Emotieregulatie & stabiliteit"),
    ("Napoleon Dynamite", "Worker · Niche Skills", 60, "Samenwerking & zelfvertrouwen"),
    ("Alex DeLarge", "Worker · Disruptive", 45, "Zwaar development traject vereist"),
]

BADGE_TO_ROLE = {
    "CEO · Orchestrator": "orchestrator",
    "CEO · Strategist": "orchestrator",
    "CEO · Patriarch": "orchestrator",
    "CEO · Tacticus": "orchestrator",
    "CEO · Noble Leider": "orchestrator",
    "CEO · Senior Coach": "orchestrator",
    "CEO · Visionair": "orchestrator",
    "CEO · Driver": "orchestrator",
    "Talent · QA Reviewer": "qa-reviewer",
    "Talent · Deep Analysis": "logic-validator",
    "Talent · Logic Validator": "logic-validator",
    "Talent · Objective Review": "qa-reviewer",
    "Talent · Ethics Review": "qa-reviewer",
    "Talent · Architecture": "logic-validator",
    "Talent · Reviewer": "qa-reviewer",
    "Talent · Wisdom Review": "qa-reviewer",
    "Talent · Process QA": "qa-reviewer",
    "Talent · Investigator": "logic-validator",
    "Talent · Compliance": "qa-reviewer",
    "Talent · Risk Assessment": "logic-validator",
    "Talent · Psych Safety": "qa-reviewer",
    "Talent · Signal Filter": "qa-reviewer",
    "Talent · Hidden Patterns": "logic-validator",
    "Talent · Introspective": "qa-reviewer",
    "Talent · Risk Detector": "logic-validator",
    "Worker · Copywriter": "copywriter",
    "Worker · Incident Response": "incident-response",
    "Worker · Senior Engineer": "senior-engineer",
    "Worker · R&D / Innovation": "senior-engineer",
    "Worker · Security": "senior-engineer",
    "Worker · Reliable Executor": "support-specialist",
    "Worker · Improvisation": "support-specialist",
    "Worker · Research": "seo-specialist",
    "Worker · Tooling / Infra": "senior-engineer",
    "Worker · Support Specialist": "support-specialist",
    "Worker · GTM / Creative": "copywriter",
    "Worker · Precision Executor": "incident-response",
    "Worker · SEO Research": "seo-specialist",
    "Worker · Task Executor": "support-specialist",
    "Worker · Creative Design": "copywriter",
    "Worker · Action / Ops": "incident-response",
    "Worker · Adaptive Ops": "incident-response",
    "Worker · Operations": "incident-response",
    "Worker · Creative": "copywriter",
    "Worker · Operations Lead": "incident-response",
    "Worker · Niche Skills": "support-specialist",
    "Worker · Disruptive": "copywriter",
}

def get_persona_roster():
    """Returns list of (name, badge, score, development_priority, type, role_key)."""
    out = []
    for name, badge, score, dev in CEO_PERSONAS:
        role_key = BADGE_TO_ROLE.get(badge, "orchestrator")
        out.append((name, badge, score, dev, "orchestrator", role_key))
    for name, badge, score, dev in TALENT_PERSONAS:
        role_key = BADGE_TO_ROLE.get(badge, "qa-reviewer")
        out.append((name, badge, score, dev, "talent", role_key))
    for name, badge, score, dev in WORKER_PERSONAS:
        role_key = BADGE_TO_ROLE.get(badge, "copywriter")
        out.append((name, badge, score, dev, "worker", role_key))
    return out
