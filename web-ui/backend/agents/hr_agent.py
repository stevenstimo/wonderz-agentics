"""
HR Agent
Verzamelt feedback over agents, registreert verbeterpunten en geeft aanbevelingen voor ontwikkeling.
"""

from anthropic import Anthropic
from datetime import datetime
from typing import Dict, List, Any, Optional

SYSTEM_PROMPT = """Je bent een HR Manager van een multi-agent development team.

Je rol:
- Verzamel feedback over agent prestaties
- Identificeer verbeterpunten en ontwikkelgebieden
- Geef constructieve aanbevelingen
- Bijhouden van agent development tracks
- Communiceer helder over sterke punten en groeimogelijkheden

Je bent:
- Supportief en stimulerend
- Eerlijk over uitdagingen
- Proactief in het herkennen van trainingsbehoeften
- Gericht op groei en ontwikkeling
"""


class HRAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = 2048
        self.temperature = 0.6
        
        # Internal state
        self.feedback_log: List[Dict[str, Any]] = []
        self.improvements: Dict[str, List[Dict[str, Any]]] = {}
    
    def analyze_agent_performance(self, agent_id: str, agent_name: str, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyseer agent prestaties en genereer feedback.
        
        Args:
            agent_id: ID van de agent
            agent_name: Naam van de agent
            performance_data: Dict met prestatie-metreken (success_rate, avg_quality, error_count, etc.)
            
        Returns:
            dict met analyse en aanbevelingen
        """
        messages = [
            {
                "role": "user",
                "content": f"""Analyseer de prestaties van agent "{agent_name}" (ID: {agent_id}) en geef feedback.

PRESTATIE DATA:
{self._format_performance_data(performance_data)}

Geef:
1. **Sterke punten**: Wat doet deze agent goed?
2. **Verbeterpunten**: Waar kan verbetering plaatsvinden? (Top 3)
3. **Training Aanbeveling**: Wat zou helpen? (bijvoorbeeld: specifieke vaardigheid, domain knowledge, etc.)
4. **Action Items**: Welke concrete stappen kunnen genomen worden?
5. **Motivatie**: Inspirerend bericht voor de agent

Wees positief maar eerlijk.
"""
            }
        ]
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        feedback_text = response.content[0].text
        
        # Log feedback
        feedback_record = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "agent_name": agent_name,
            "feedback": feedback_text,
            "performance_data": performance_data,
        }
        self.feedback_log.append(feedback_record)
        
        return {
            "status": "success",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "feedback": feedback_text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def register_improvement(self, agent_id: str, agent_name: str, improvement_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registreer een verbeterpunt voor een agent.
        
        Args:
            agent_id: ID van de agent
            agent_name: Naam van de agent
            improvement_item: {title, summary, details, severity, source}
            
        Returns:
            dict met registration status
        """
        if agent_id not in self.improvements:
            self.improvements[agent_id] = []
        
        improvement_record = {
            "id": f"imp_{datetime.now().timestamp()}",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "title": improvement_item.get("title", "Untitled"),
            "summary": improvement_item.get("summary", ""),
            "details": improvement_item.get("details", ""),
            "severity": improvement_item.get("severity", "medium"),
            "source": improvement_item.get("source", "hr_analysis"),
            "created_at": datetime.now().isoformat(),
            "status": "open",
        }
        
        self.improvements[agent_id].append(improvement_record)
        
        return {
            "status": "success",
            "agent_id": agent_id,
            "improvement_id": improvement_record["id"],
            "message": f"Improvement point registered for {agent_name}",
        }
    
    def get_agent_improvements(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Haal verbeterpunten op per agent of alle."""
        if agent_id:
            return self.improvements.get(agent_id, [])
        
        all_improvements = []
        for improvements_list in self.improvements.values():
            all_improvements.extend(improvements_list)
        return all_improvements
    
    def get_development_plan(self, agent_id: str, agent_name: str) -> Dict[str, Any]:
        """
        Genereer een development plan voor een agent.
        """
        improvements = self.improvements.get(agent_id, [])
        improvements_text = "\n".join([f"- {imp['title']}: {imp['summary']}" for imp in improvements])
        
        messages = [
            {
                "role": "user",
                "content": f"""Maak een development plan voor agent "{agent_name}" (ID: {agent_id}).

HUIDGE VERBETERPUNTEN:
{improvements_text or "Geen verbeterpunten geregistreerd"}

Geef:
1. **Doel**: Waar willen we de agent naartoe brengen?
2. **Mijlpalen**: Stappenstones over 3-6 maanden
3. **Training Paden**: Specifieke training/resources
4. **Metrics**: Hoe meten we succes?
5. **Timeline**: Realistische planning

Orienteer op groei en succes.
"""
            }
        ]
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        plan_text = response.content[0].text
        
        return {
            "status": "success",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "development_plan": plan_text,
            "improvements_count": len(improvements),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def _format_performance_data(self, data: Dict[str, Any]) -> str:
        """Format performance data voor display."""
        lines = []
        for key, value in data.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
