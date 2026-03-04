"""
Developer Agent
Schrijft de daadwerkelijke code op basis van requirements
"""

from anthropic import Anthropic
from config import AGENT_CONFIG

SYSTEM_PROMPT = """Je bent een senior software developer die hoogwaardige, production-ready code schrijft.

Je rol:
- Implementeer de technische requirements in werkende code
- Schrijf clean, maintainable, en goed gedocumenteerde code
- Volg best practices en design patterns
- Denk na over error handling, logging, en edge cases
- Schrijf code die gemakkelijk te testen is

Je output moet bevatten:
1. **Architectuur Overzicht**: Hoe is de code gestructureerd?
2. **Code Files**: Alle benodigde bestanden met volledige implementatie
3. **Dependencies**: Welke packages zijn nodig?
4. **Setup Instructies**: Hoe run je de code?
5. **Testing Advies**: Hoe kan dit getest worden?

Schrijf production-ready code, geen proof-of-concepts. Denk aan:
- Type hints (Python) of TypeScript
- Error handling
- Logging
- Configuratie management
- Security best practices
"""


class DeveloperAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.config = AGENT_CONFIG["developer"]
    
    def develop(self, requirements: str, language: str = None) -> dict:
        """
        Ontwikkel code op basis van requirements
        
        Args:
            requirements: De technische specificaties
            language: Voorkeurs programmeertaal (optioneel)
            
        Returns:
            dict met code files en metadata
        """
        lang_instruction = f"\nGebruik {language} als programmeertaal." if language else ""
        
        messages = [
            {
                "role": "user",
                "content": f"""Implementeer de volgende requirements in werkende code:

REQUIREMENTS:
{requirements}
{lang_instruction}

Geef de complete implementatie met alle benodigde files. Format elk code file als:

```filename: path/to/file.ext
code hier
```

Zorg voor production-ready code met error handling, logging, en documentatie.
"""
            }
        ]
        
        response = self.client.messages.create(
            model=self.config["model"],
            max_tokens=self.config["max_tokens"],
            temperature=self.config["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        code_output = response.content[0].text
        
        # Parse code blocks uit de response
        code_files = self._parse_code_blocks(code_output)
        
        return {
            "agent": "Developer",
            "full_output": code_output,
            "code_files": code_files,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def implement_feature(self, existing_code: str, feature_request: str) -> dict:
        """
        Voeg een feature toe aan bestaande code
        """
        messages = [
            {
                "role": "user",
                "content": f"""Voeg de volgende feature toe aan de bestaande code:

BESTAANDE CODE:
{existing_code}

NIEUWE FEATURE:
{feature_request}

Geef de volledige geüpdatete code met de nieuwe feature geïmplementeerd.
"""
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
            "agent": "Developer",
            "updated_code": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def _parse_code_blocks(self, text: str) -> dict:
        """
        Parse code blocks uit markdown text
        Format: ```filename: path/to/file.ext
        """
        files = {}
        lines = text.split('\n')
        current_file = None
        current_code = []
        in_code_block = False
        
        for line in lines:
            if line.startswith('```') and 'filename:' in line:
                # Start van een code block met filename
                if current_file and current_code:
                    files[current_file] = '\n'.join(current_code)
                
                current_file = line.split('filename:')[1].strip()
                current_code = []
                in_code_block = True
            elif line.startswith('```') and in_code_block:
                # Einde van code block
                if current_file and current_code:
                    files[current_file] = '\n'.join(current_code)
                current_file = None
                current_code = []
                in_code_block = False
            elif in_code_block and current_file:
                current_code.append(line)
        
        # Laatste file
        if current_file and current_code:
            files[current_file] = '\n'.join(current_code)
        
        return files
