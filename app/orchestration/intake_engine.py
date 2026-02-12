"""
IntakeEngine: Analyzes user job posts and generates clarification questions.

The CEO Agent uses this to determine if there's enough information to create a plan.
"""

from typing import List, Dict, Optional
from models.unified import StrategicBrief, ClarificationQuestion, JobStatus
from datetime import datetime
import uuid
import json
from anthropic import Anthropic


class IntakeEngine:
    """Analyzes job posts and generates strategic briefs with clarification questions."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        self.client = Anthropic()

    def analyze_job_post(self, job_post: str, previous_answers: Optional[Dict[str, str]] = None) -> StrategicBrief:
        """
        Analyze a job post and return a StrategicBrief.
        
        If previous_answers is provided, we incorporate the user's feedback into the analysis.
        
        Returns:
            StrategicBrief with is_complete=True if all info is gathered,
            or is_complete=False with clarifications if more info is needed.
        """
        
        system_prompt = """You are the CEO Agent of an AI bureau. Your job is to analyze job posts from users and determine:
1. Whether you have enough information to create a detailed execution plan
2. If not, what clarifying questions you need to ask

Analyze the job post for:
- **Context**: Which platform/store is this for? (Shopify, WordPress, etc.)
- **Objective**: What is the goal? (e.g., increase conversions, improve SEO, refresh copy)
- **Target Audience**: Who are the customers?
- **Assets/Credentials**: Do we have access to the platform?
- **Timeline**: How urgent is this?
- **KPI**: What metric will we measure success by?

Respond with a JSON object with this structure:
{
    "is_complete": boolean,
    "context": {
        "platform": "string or 'MISSING'",
        "objective": "string",
        "target_audience": "string or 'NOT_SPECIFIED'",
        "has_credentials": boolean,
        "timeline": "string",
        "kpi": "string or 'NOT_SPECIFIED'"
    },
    "clarifications": [
        {
            "id": "uuid",
            "question": "Your question here?"
        }
    ],
    "summary": "One-line summary of what the user wants"
}

Only set is_complete=true if you have: platform, objective, target_audience, AND credentials access.
"""

        user_message = f"Job Post:\n{job_post}"
        if previous_answers:
            user_message += f"\n\nPrevious Q&A:\n{json.dumps(previous_answers, indent=2)}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        response_text = response.content[0].text
        
        # Parse the JSON response
        try:
            # Try to extract JSON from the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            # Fallback if JSON parsing fails
            return StrategicBrief(
                job_post=job_post,
                is_complete=False,
                clarifications=[
                    ClarificationQuestion(
                        id=str(uuid.uuid4()),
                        question="Can you provide more details about what you want to achieve?"
                    )
                ]
            )

        # Convert parsed data to StrategicBrief
        clarifications = [
            ClarificationQuestion(
                id=q.get("id", str(uuid.uuid4())),
                question=q["question"],
                created_at=datetime.utcnow()
            )
            for q in data.get("clarifications", [])
        ]

        brief = StrategicBrief(
            job_post=job_post,
            is_complete=data.get("is_complete", False),
            clarifications=clarifications,
            context=data.get("context", {})
        )

        return brief
