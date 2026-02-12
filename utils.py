"""
Utility functies voor het multi-agent systeem
"""

import os
import json
from typing import Dict, Any, List
from datetime import datetime


def save_json(data: Dict[str, Any], filepath: str):
    """
    Save data as JSON
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(filepath: str) -> Dict[str, Any]:
    """
    Load JSON data
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def estimate_tokens(text: str) -> int:
    """
    Rough estimate van tokens (1 token ≈ 4 characters)
    """
    return len(text) // 4


def calculate_cost(input_tokens: int, output_tokens: int, model: str = "claude-sonnet-4") -> float:
    """
    Bereken kosten op basis van tokens
    Prijzen per 1M tokens (februari 2025 schatting):
    - Sonnet 4: $3 input, $15 output
    - Haiku 4: $0.25 input, $1.25 output
    - Opus 4: $15 input, $75 output
    """
    pricing = {
        "claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "claude-haiku-4": {"input": 0.25, "output": 1.25},
        "claude-opus-4": {"input": 15.0, "output": 75.0},
    }
    
    # Default naar sonnet
    rates = pricing.get(model, pricing["claude-sonnet-4"])
    
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    
    return input_cost + output_cost


def format_code_block(code: str, language: str = "") -> str:
    """
    Format code als markdown code block
    """
    return f"```{language}\n{code}\n```"


def extract_code_from_markdown(text: str) -> List[Dict[str, str]]:
    """
    Extract alle code blocks uit markdown text
    """
    blocks = []
    lines = text.split('\n')
    in_block = False
    current_block = []
    current_lang = ""
    
    for line in lines:
        if line.startswith('```'):
            if in_block:
                # Einde van block
                blocks.append({
                    "language": current_lang,
                    "code": '\n'.join(current_block)
                })
                current_block = []
                current_lang = ""
                in_block = False
            else:
                # Start van block
                current_lang = line[3:].strip()
                in_block = True
        elif in_block:
            current_block.append(line)
    
    return blocks


def create_timestamp() -> str:
    """
    Maak timestamp string
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate lange tekst
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def validate_api_key(api_key: str) -> bool:
    """
    Valideer API key format
    """
    return (
        api_key and 
        isinstance(api_key, str) and 
        api_key.startswith("sk-ant-api03-") and
        len(api_key) > 50
    )


def format_token_count(count: int) -> str:
    """
    Format token count voor display
    """
    if count < 1000:
        return f"{count}"
    elif count < 1_000_000:
        return f"{count/1000:.1f}K"
    else:
        return f"{count/1_000_000:.2f}M"


def merge_dicts(*dicts: Dict) -> Dict:
    """
    Merge meerdere dictionaries
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


class SessionLogger:
    """
    Logger voor het tracken van een development sessie
    """
    
    def __init__(self, session_id: str, output_dir: str = "output"):
        self.session_id = session_id
        self.output_dir = output_dir
        self.log_file = os.path.join(output_dir, f"{session_id}_session.log")
        self.events = []
    
    def log(self, event_type: str, message: str, metadata: Dict = None):
        """
        Log een event
        """
        event = {
            "timestamp": create_timestamp(),
            "type": event_type,
            "message": message,
            "metadata": metadata or {}
        }
        self.events.append(event)
        
        # Write to file
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{event['timestamp']} [{event_type}] {message}\n")
            if metadata:
                f.write(f"  Metadata: {json.dumps(metadata, indent=2)}\n")
    
    def save_summary(self):
        """
        Save sessie summary als JSON
        """
        summary_file = os.path.join(self.output_dir, f"{self.session_id}_summary.json")
        save_json({
            "session_id": self.session_id,
            "events": self.events,
            "total_events": len(self.events)
        }, summary_file)
