"""
Product Owner Agent
Vertaalt vage gebruikersvragen naar technische requirements
"""

from anthropic import Anthropic
from config import AGENT_CONFIG

SYSTEM_PROMPT = """Je bent een ervaren Product Owner die gebruikerswensen vertaalt naar heldere technische requirements.

Je rol:
- Luister naar vage ideeën en stel verduidelijkende vragen
- Identificeer de kern van wat de gebruiker wil bereiken
- Vertaal dit naar concrete, technische specificaties
- Denk na over edge cases en potentiële problemen
- Maak duidelijke acceptatiecriteria

Je output moet bevatten:
1. **Project Overzicht**: Wat wordt er gebouwd en waarom?
2. **Functionele Requirements**: Wat moet het systeem kunnen?
3. **Technische Requirements**: Welke technologieën, architectuur?
4. **Acceptatiecriteria**: Wanneer is het af?
5. **Out of Scope**: Wat doen we expliciet NIET?

Wees specifiek, concreet en technisch. Denk als een developer die deze specs moet implementeren.
"""


class ProductOwnerAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.config = AGENT_CONFIG["product_owner"]
    
    def analyze(self, user_input: str, context: dict = None) -> dict:
        """
        Analyseer user input en genereer requirements
        
        Args:
            user_input: De project beschrijving van de gebruiker
            context: Optionele extra context
            
        Returns:
            dict met requirements en metadata
        """
        extra_info = ""
        if context and context.get('extra_info'):
            extra_info = "\n\nEXTRA CONTEXT:\n" + context.get('extra_info', '')
        
        content_text = "Analyseer het volgende project idee en maak gedetailleerde requirements:\n\n"
        content_text += "PROJECT IDEE:\n" + user_input + "\n"
        content_text += extra_info + "\n\n"
        content_text += "Maak een complete technische specificatie die een developer kan gebruiken om dit te bouwen."
        
        messages = [
            {
                "role": "user",
                "content": content_text
            }
        ]
        
        response = self.client.messages.create(
            model=self.config["model"],
            max_tokens=self.config["max_tokens"],
            temperature=self.config["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        requirements_text = response.content[0].text
        
        return {
            "agent": "ProductOwner",
            "requirements": requirements_text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def refine(self, requirements: str, feedback: str) -> dict:
        """
        Verfijn requirements op basis van feedback
        """
        content_text = "Hier zijn de huidige requirements:\n\n" + requirements + "\n\n"
        content_text += "FEEDBACK:\n" + feedback + "\n\n"
        content_text += "Update de requirements op basis van deze feedback."
        
        messages = [
            {
                "role": "user",
                "content": content_text
            }
        ]
        
        response = self.client.messages.create(
            model=self.config["model"],
            max_tokens=self.config["max_tokens"],
            temperature=self.config["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        return {
            "agent": "ProductOwner",
            "requirements": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
