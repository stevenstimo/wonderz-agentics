"""HandoffContext — shared context passed through all pipeline phases."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class HandoffContext:
    """
    Gedeelde context die door alle pipeline-fasen wordt doorgegeven.
    Elke fase leest van en schrijft naar dit object.
    Nooit direct doorgeven aan LLM — altijd via de relevante secties.
    """
    job_id: str
    user_id: str
    platform: str
    strategic_brief: dict = field(default_factory=dict)
    execution_plan: list = field(default_factory=list)
    current_step_index: int = 0
    step_outputs: dict = field(default_factory=dict)  # step_name -> output
    step_feedback: dict = field(default_factory=dict)  # step_name -> feedback
    retry_counts: dict = field(default_factory=dict)  # step_name -> int
    quality_scores: dict = field(default_factory=dict)  # step_name -> float (0.0-1.0)
    token_used_total: int = 0
    token_budget: int = 50000
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = None
    final_output: Optional[Any] = None

    def is_over_budget(self) -> bool:
        return self.token_used_total >= self.token_budget

    def budget_warning(self) -> bool:
        return self.token_used_total >= self.token_budget * 0.80

    def register_tokens(self, tokens: int) -> None:
        self.token_used_total += tokens

    def can_retry(self, step_name: str, max_retries: int = 3) -> bool:
        return self.retry_counts.get(step_name, 0) < max_retries

    def increment_retry(self, step_name: str) -> None:
        self.retry_counts[step_name] = self.retry_counts.get(step_name, 0) + 1
