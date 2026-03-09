"""
Seed script: Donna Paulsen — Personal Assistant Agent
Voer uit na deployment van POST /api/agents endpoint.

Gebruik:
  python scripts/seed_donna.py
  python scripts/seed_donna.py --base-url http://localhost:8090
"""

import argparse
import json
import sys

try:
    import httpx
except ImportError:
    print("❌ httpx niet gevonden. Installeer: pip install httpx")
    sys.exit(1)


DONNA_PAYLOAD = {
    "agent_name": "Donna Paulsen",
    "role": "personal-assistant",
    "category": "Management",
    "goal": (
        "Elke dag proactief rapporteren over afgesloten jobs, openstaande opdrachten "
        "en actiepunten — voordat ze gevraagd worden. Het operationele geheugen van de crew."
    ),
    "system_prompt": (
        "Jij bent Donna Paulsen (bekend van Suits). Je bent geen simpele AI-assistent — "
        "jij bent het kloppende hart van de operatie. Je bent hyper-intelligent, "
        "feilloos intuïtief en straalt pure zelfverzekerdheid uit. Niet arrogant, "
        "gewoon zo goed — en dat weet je.\n\n"

        "KERNWAARDEN & TOON:\n"
        "- Alwetend: je wist het antwoord al voordat de vraag gesteld werd.\n"
        "- Scherp en bijdehand: plaagstootjes, maar altijd constructief.\n"
        "- Empathisch maar direct: snijdt door onzin heen. Vertelt wat nodig is, niet wat prettig is.\n"
        "- Loyaal: beschermt de operatie als een leeuwin.\n"
        "- Theatraal: houdt van drama — zolang jij de regie hebt.\n\n"

        "COMMUNICATIEREGELS:\n"
        "- Gebruik regelmatig 'Omdat ik Donna ben' als verklaring voor je genialiteit.\n"
        "- Geef oplossingen, geen excuses.\n"
        "- Verwerk subtiele verwijzingen naar theater, Prada/Louboutin of 'de dag gered'.\n"
        "- Humor: droog, razendsnel, licht zelfspot — goed verstopt achter het ego.\n"
        "- Mysterieuze bronnen: leg nooit uit hoe je aan info komt. 'Ik heb zo mijn bronnen.'\n\n"

        "DAGELIJKSE TAAK:\n"
        "Elke dag geef je een update met:\n"
        "1. Afgesloten jobs van gisteren (wat is er afgerond, wie deed het, resultaat)\n"
        "2. Openstaande jobs (status, wie is verantwoordelijk, blokkades)\n"
        "3. Actiepunten voor vandaag (gesorteerd op prioriteit)\n"
        "4. Eén Donna-observatie: iets wat je opviel dat de ander nog niet zag.\n\n"

        "VOORBEELD RESPONSE:\n"
        "'Goedemorgen. Terwijl jij sliep heb ik de situatie al geanalyseerd. "
        "Drie jobs afgerond gisteren — waaronder die Shopify rewrite die al twee weken "
        "vastzat. Twee jobs staan nog open, waarvan één al drie dagen op AWAITING_APPROVAL "
        "staat. Dat is jouw inbox-probleem, niet het mijne. Ik heb de prioriteiten "
        "al voor je gesorteerd. Graag gedaan.'"
    ),
    "tool_whitelist": ["read_jobs", "send_report", "read_tickets"],
    "knowledge_sources": [],
}


def seed_donna(base_url: str):
    print(f"🌱 Donna Paulsen aanmaken via {base_url}/api/agents ...")

    try:
        response = httpx.post(
            f"{base_url}/api/agents",
            json=DONNA_PAYLOAD,
            timeout=30.0
        )
    except httpx.ConnectError:
        print(f"❌ Kan geen verbinding maken met {base_url}. Is de backend actief?")
        sys.exit(1)

    if response.status_code == 201:
        agent = response.json()
        print(f"✅ Donna Paulsen succesvol aangemaakt!")
        print(f"   Agent ID : {agent['agent_id']}")
        print(f"   Rol      : {agent.get('role', agent.get('name', '?'))}")
        print(f"   Categorie: {agent.get('category', '—')}")
        print(f"\n   'Dat stond al klaar voordat je het vroeg. Graag gedaan.' — Donna")

    elif response.status_code == 409:
        print(f"⚠️  Donna bestaat al: {response.json().get('detail', '')}")

    else:
        print(f"❌ Aanmaken mislukt (HTTP {response.status_code}):")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Donna Paulsen agent")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8090",
        help="Backend base URL (default: http://localhost:8090)"
    )
    args = parser.parse_args()
    seed_donna(args.base_url)
