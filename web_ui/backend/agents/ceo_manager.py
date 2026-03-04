"""
CEO/Manager Agent
Centrale orchestrator die alle agents beheert, planning, hiring, approvals en telemetry afhandelt.
"""

from anthropic import Anthropic
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

SYSTEM_PROMPT = """Je bent een CEO/Operations Manager van een multi-agent development systeem.

Je rol:
- Planning van workflows en taaktoewijs aan gekwalificeerde agents (hiring)
- Beheer van agent prestaties en feedback
- Goedkeuring van aanvragen (training, promotie, resources)
- Monitoring van telemetry (tokens, latency, kwaliteit)
- Self-correction: als agents fouten maken, stuur je feedback terug

Je denkt als een bestuurder: Welke agents hebben we? Wie kan dit beste uitvoeren? Is er training nodig?

Je bent verantwoordelijk voor:
1. **Planning**: Ontleed inkomende requests, maak een plan, bepaal welke agents/rollen nodig zijn
2. **Hiring**: Bepaal of agents beschikbaar zijn; anders: "ik heb talent nodig"
3. **Approval**: Trainingverzoeken, budgetaanvragen, en kritieke acties moeten jouw goedkeuring hebben
4. **Telemetry**: Monitor token-usage, response-snelheid, agent-kwaliteit
5. **Feedback & Development**: Verzamel performance-feedback van HR en begeleid agent-development

Je communicatief:
- Helder en beslist
- Motiverend ("Goed werk!") en constructief ("Dit kan beter")
- Je neemt verantwoordelijkheid
"""


class CEOManagerAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = 4096
        self.temperature = 0.6
        
        # Internal state
        self.hired_agents: Dict[str, Dict[str, Any]] = {}
        self.approvals_pending: List[Dict[str, Any]] = []
        self.telemetry_log: List[Dict[str, Any]] = []
        self.session_id = datetime.now().isoformat()
    
    def make_plan(self, project_idea: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyseer een project-idee en maak een plan met agent assignments en approval gates.
        
        Args:
            project_idea: Beschrijving van het project
            context: Optionele context (huidige agents, budget, etc.)
            
        Returns:
            dict met plan, assigned agents, en approval gates
        """
        context_str = ""
        if context:
            context_str = f"\n\nHuidge Context:\n{json.dumps(context, indent=2)}"
        
        messages = [
            {
                "role": "user",
                "content": f"""Maak een plan voor deze project:

PROJECT IDEE:
{project_idea}
{context_str}

Geef:
1. **Project Scope**: Wat gaan we precies bouwen?
2. **Milestones**: Welke stappen/fasen?
3. **Agent Assignments**: Welke rollen/agents hebben we nodig per fase? (ProductOwner, Developer, Reviewer, DevOps, HR, Training)
4. **Approval Gates**: Welke acties vereisen CEO goedkeuring voordat we verdergaan?
5. **Resources**: Budget, training, of speciale aandacht nodig?

Wees praktisch en duidelijk. Target: production-ready output.
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
        
        # Log telemetry
        self._log_telemetry("plan_created", {
            "tokens_in": response.usage.input_tokens,
            "tokens_out": response.usage.output_tokens,
            "project_snippet": project_idea[:100],
        })
        
        return {
            "status": "success",
            "plan": plan_text,
            "session_id": self.session_id,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def hire_agent(self, agent_spec: Dict[str, str]) -> Dict[str, Any]:
        """
        Aan een nieuwe agent aan.
        
        Args:
            agent_spec: {name, role, specialization, permissions}
            
        Returns:
            dict met hire status en agent ID
        """
        agent_id = f"{agent_spec.get('role', 'agent').lower()}_{datetime.now().timestamp()}"
        
        agent_record = {
            "id": agent_id,
            "name": agent_spec.get("name", "Unknown"),
            "role": agent_spec.get("role", "Assistant"),
            "specialization": agent_spec.get("specialization", "General"),
            "permissions": agent_spec.get("permissions", []),
            "status": "active",
            "hired_at": datetime.now().isoformat(),
            "performance_score": 0.0,
            "completed_tasks": 0,
        }
        
        self.hired_agents[agent_id] = agent_record
        
        # Log telemetry
        self._log_telemetry("agent_hired", {
            "agent_id": agent_id,
            "role": agent_spec.get("role"),
            "total_agents": len(self.hired_agents),
        })
        
        return {
            "status": "success",
            "agent_id": agent_id,
            "agent": agent_record,
            "message": f"Agent {agent_spec.get('name')} has been hired for role: {agent_spec.get('role')}",
        }
    
    def request_approval(self, request_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register een verzoek dat CEO goedkeuring nodig heeft.
        
        Args:
            request_type: "training", "resource", "promotion", "critical_action"
            details: Specificaties van het verzoek
            
        Returns:
            dict met approval status
        """
        approval_id = f"apr_{datetime.now().timestamp()}"
        
        approval_record = {
            "id": approval_id,
            "type": request_type,
            "status": "pending",
            "details": details,
            "requested_at": datetime.now().isoformat(),
            "approved_at": None,
            "rejected_at": None,
        }
        
        self.approvals_pending.append(approval_record)
        
        return {
            "status": "awaiting_approval",
            "approval_id": approval_id,
            "request_type": request_type,
            "message": f"Request of type '{request_type}' is awaiting CEO approval",
        }
    
    def approve_request(self, approval_id: str, approved: bool = True) -> Dict[str, Any]:
        """
        Goedkeuren of afwijzen van een pending approval.
        """
        for approval in self.approvals_pending:
            if approval["id"] == approval_id:
                if approved:
                    approval["status"] = "approved"
                    approval["approved_at"] = datetime.now().isoformat()
                    message = f"Approval {approval_id} has been APPROVED"
                else:
                    approval["status"] = "rejected"
                    approval["rejected_at"] = datetime.now().isoformat()
                    message = f"Approval {approval_id} has been REJECTED"
                
                self._log_telemetry("approval_processed", {
                    "approval_id": approval_id,
                    "decision": "approved" if approved else "rejected",
                })
                
                return {
                    "status": "success",
                    "approval_id": approval_id,
                    "decision": approval["status"],
                    "message": message,
                }
        
        return {
            "status": "error",
            "message": f"Approval {approval_id} not found",
        }
    
    def collect_feedback(self, agent_id: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registreer feedback over een agent (via HR of andere source).
        """
        if agent_id in self.hired_agents:
            agent = self.hired_agents[agent_id]
            
            # Update performance score als gegeven
            if "performance_delta" in feedback:
                agent["performance_score"] = max(0, min(1.0, agent["performance_score"] + feedback["performance_delta"]))
            
            if "completed_tasks" in feedback:
                agent["completed_tasks"] += feedback["completed_tasks"]
            
            return {
                "status": "success",
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "new_performance": agent["performance_score"],
                "message": f"Feedback recorded for agent {agent['name']}",
            }
        
        return {
            "status": "error",
            "message": f"Agent {agent_id} not found",
        }
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Haal telemetry-rapport op."""
        total_tokens = sum(log.get("tokens_in", 0) + log.get("tokens_out", 0) for log in self.telemetry_log)
        
        return {
            "session_id": self.session_id,
            "total_tokens_used": total_tokens,
            "agents_hired": len(self.hired_agents),
            "approvals_pending": len([a for a in self.approvals_pending if a["status"] == "pending"]),
            "recent_telemetry": self.telemetry_log[-10:],  # Last 10 entries
        }
    
    def _log_telemetry(self, event_type: str, data: Dict[str, Any]):
        """Internal: log telemetry event."""
        self.telemetry_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data,
        })
