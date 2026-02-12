"""
StrategyRoom: Converts StrategicBrief to ExecutionPlan.

The CEO Agent uses this to determine which agents to hire and in what sequence.
"""

from typing import List, Dict, Optional
from models.unified import StrategicBrief, ExecutionPlan, JobStep
from datetime import datetime
import json
from anthropic import Anthropic


class HiredAgent:
    """Represents a hired agent for a job."""
    def __init__(self, role: str, agent_id: str):
        self.role = role
        self.agent_id = agent_id


class StrategyRoom:
    """Creates ExecutionPlans from StrategicBriefs."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self.client = Anthropic()

    def generate_execution_plan(
        self, 
        brief: StrategicBrief,
        available_agents: Optional[List[str]] = None
    ) -> ExecutionPlan:
        """
        Create an ExecutionPlan from a validated StrategicBrief.
        
        Args:
            brief: The validated StrategicBrief from IntakeEngine
            available_agents: List of agent roles we currently have access to
        
        Returns:
            ExecutionPlan with step-by-step instructions and required hires
        """
        
        if not brief.is_complete:
            raise ValueError("StrategicBrief is not complete; cannot generate plan.")

        available_agents = available_agents or []
        
        system_prompt = """You are a project manager planning an AI bureau workflow.

Given a strategic brief, create a detailed step-by-step execution plan.

For the objective in the brief, determine:
1. What sequence of agents should work on it
2. What tools each agent will use
3. Whether each step requires approval

Available agent roles: copywriter, developer, seo_specialist, reviewer, paid_ads_manager, data_analyst

Respond with JSON:
{
    "steps": [
        {
            "step_index": 1,
            "agent_role": "copywriter",
            "unified_tool": "read_product",
            "requires_approval": false,
            "description": "Fetch the current product data"
        }
    ],
    "required_hires": ["copywriter"],
    "estimated_duration_seconds": 300
}

The 'unified_tool' should be one of: read_product, read_ad, write_description, write_ad, analyze_seo, deploy_changes, etc.
"""

        context_str = json.dumps(brief.context, indent=2)
        user_message = f"""
Strategic Brief:
- Objective: {brief.context.get('objective', 'Unknown')}
- Platform: {brief.context.get('platform', 'Unknown')}
- Target Audience: {brief.context.get('target_audience', 'Not specified')}
- KPI: {brief.context.get('kpi', 'Not specified')}

Available agents: {', '.join(available_agents) or 'None specified'}

Create a step-by-step plan to achieve the objective.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        response_text = response.content[0].text
        
        # Parse JSON response
        try:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            # Fallback plan
            data = {
                "steps": [
                    {
                        "step_index": 1,
                        "agent_role": "copywriter",
                        "unified_tool": "read_product",
                        "requires_approval": False,
                        "description": "Fetch product data"
                    }
                ],
                "required_hires": ["copywriter"],
                "estimated_duration_seconds": 300
            }

        # Convert to JobStep objects
        steps = [
            JobStep(
                step_index=s.get("step_index", i),
                agent_role=s.get("agent_role", "unknown"),
                unified_tool=s.get("unified_tool", "read_product"),
                requires_approval=s.get("requires_approval", False),
                description=s.get("description", "")
            )
            for i, s in enumerate(data.get("steps", []), 1)
        ]

        plan = ExecutionPlan(
            brief=brief,
            steps=steps,
            hired_agents=data.get("required_hires", []),
            estimated_duration_seconds=data.get("estimated_duration_seconds", 0)
        )

        return plan
