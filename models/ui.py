from pydantic import BaseModel, Field
from typing import List, Optional

class CrewMember(BaseModel):
    id: str
    name: str
    role: str
    status: str  # e.g. 'active', 'busy', 'idle'
    current_task: Optional[str] = None
    progress: int = 0  # percentage
    avatar_url: Optional[str] = None

class TaskCrewShare(BaseModel):
    crew_id: str
    share: int  # percentage

class Task(BaseModel):
    id: str
    title: str
    status: str  # e.g. 'pending', 'in_progress', 'completed'
    crew: List[TaskCrewShare]
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class ImprovementItem(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    title: str
    summary: Optional[str] = None
    details: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
