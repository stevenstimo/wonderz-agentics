#!/usr/bin/env python3
"""
Test ANTHROPIC_API_KEY in hire context — geïsoleerde test voor system_prompt generatie.

Gebruik:
  python scripts/test_anthropic_system_prompt.py
  ANTHROPIC_API_KEY=sk-ant-... python scripts/test_anthropic_system_prompt.py

Bevestigt dat de key werkt voordat je hire via de API doet.
"""

import os
import sys

try:
    from anthropic import Anthropic
except ImportError:
    print("❌ anthropic niet gevonden. Installeer: pip install anthropic")
    sys.exit(1)


def main() -> None:
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        print("❌ ANTHROPIC_API_KEY niet gezet in deze context.")
        print("   Zet in ~/.bashrc, .env, of: ANTHROPIC_API_KEY=sk-ant-... python scripts/test_anthropic_system_prompt.py")
        sys.exit(1)

    print("✓ ANTHROPIC_API_KEY aanwezig (%d tekens)" % len(api_key))
    print("Calling Claude API for system_prompt...")

    client = Anthropic()
    try:
        response = client.messages.create(
            model=__import__("app.core.config", fromlist=["DEFAULT_MODEL"]).DEFAULT_MODEL,
            max_tokens=256,
            system="Genereer een korte system_prompt voor een AI agent. Schrijf in de tweede persoon (Jij bent...).",
            messages=[{"role": "user", "content": "Naam: The Dude\nRol: custom\nPersona: Ontspannen levensfilosoof die weigert mee te gaan in stress.\nOutput alleen de system_prompt."}],
        )
        text = (response.content[0].text if response.content else "").strip()
        if text:
            print("✓ Claude API succesvol")
            print("---")
            print(text[:100] + "..." if len(text) > 100 else text)
            print("---")
            if text.startswith("Jij bent"):
                print("✓ Output begint met 'Jij bent...' — correct")
            else:
                print("⚠ Output begint niet met 'Jij bent...' — check prompt")
        else:
            print("❌ Claude API gaf lege response")
            sys.exit(1)
    except Exception as e:
        print("❌ Claude API faalde: %s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
