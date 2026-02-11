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
