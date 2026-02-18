from typing import Dict, Optional

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    user_id: str = Field(default="anonymous")
    job_post: str = Field(min_length=1)
    source_platform: str = Field(default="custom")


class SubmitAnswersRequest(BaseModel):
    answers: Dict[str, str]


class FeedbackRequest(BaseModel):
    feedback: str


class ApprovePlanRequest(BaseModel):
    approved: bool = True


class ApproveJobRequest(BaseModel):
    approved: bool = True


class CreateJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ErrorResponse(BaseModel):
    detail: Optional[str] = None
