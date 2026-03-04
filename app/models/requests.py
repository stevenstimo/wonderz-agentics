from typing import Dict, Optional, Any

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    user_id: Any = Field(...)
    job_post: str = Field(min_length=10)
    source_platform: Optional[str] = None


class SubmitAnswersRequest(BaseModel):
    answers: Dict[str, str]


class FeedbackRequest(BaseModel):
    feedback: str


class ApprovePlanRequest(BaseModel):
    approved: bool = True


class ApproveJobRequest(BaseModel):
    approved: bool = True


class CreateJobResponse(BaseModel):
    job_id: Any
    status: str
    message: str


class ErrorResponse(BaseModel):
    detail: Optional[str] = None
