"""
Task Type Detector Service

Purpose: Detect what type of task the user is requesting.
DRY: Single source of truth for task classification.
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple


class TaskType(str, Enum):
    """Types of tasks the system can handle."""
    COPY_WRITING = "copy_writing"
    IMAGE_GENERATION = "image_generation"
    DATA_ANALYSIS = "data_analysis"
    CODE_WRITING = "code_writing"
    VIDEO_EDITING = "video_editing"
    AUDIO_PRODUCTION = "audio_production"
    TRANSLATION = "translation"
    RESEARCH = "research"
    UNKNOWN = "unknown"


class AgentRole(str, Enum):
    """Agent roles that can handle each task type."""
    COPYWRITER = "copywriter"
    IMAGE_GENERATOR = "image-generator"
    DATA_ANALYST = "data-analyst"
    CODE_WRITER = "code-writer"
    VIDEO_EDITOR = "video-editor"
    AUDIO_PRODUCER = "audio-producer"
    TRANSLATOR = "translator"
    RESEARCHER = "researcher"


class TaskTypeDetector:
    """
    Detects task type from user request.

    DRY Principle:
    - Single task classification logic
    - Reusable keyword matching
    - Extensible for new task types
    """

    # Task type keywords (ordered by specificity)
    TASK_KEYWORDS: Dict[TaskType, List[str]] = {
        TaskType.IMAGE_GENERATION: [
            "afbeelding", "image", "foto", "picture", "visual", "graphic",
            "illustratie", "illustration", "design", "logo", "icon",
            "maak een plaatje", "genereer een afbeelding", "create image",
        ],
        TaskType.VIDEO_EDITING: [
            "video", "film", "montage", "edit video", "render",
            "animation", "animatie", "movie", "clip",
        ],
        TaskType.CODE_WRITING: [
            "code", "programming", "script", "python", "javascript",
            "function", "algorithm", "api", "schrijf code",
            "maak een script", "programmeer",
        ],
        TaskType.DATA_ANALYSIS: [
            "analyseer", "analyze", "data", "statistics", "metrics",
            "dashboard", "visualize", "visualiseer", "chart", "graph",
            "spreadsheet", "excel", "csv",
        ],
        TaskType.AUDIO_PRODUCTION: [
            "audio", "sound", "music", "podcast", "voice",
            "geluid", "muziek", "opname", "recording",
        ],
        TaskType.TRANSLATION: [
            "vertaal", "translate", "translation", "vertaling",
            "engels naar nederlands", "dutch to english",
        ],
        TaskType.RESEARCH: [
            "onderzoek", "research", "find information", "zoek uit",
            "vergelijk", "compare", "what is", "wat is",
        ],
        TaskType.COPY_WRITING: [
            "schrijf", "write", "maak tekst", "create content",
            "artikel", "article", "blog", "post", "description",
            "beschrijving", "content", "copy", "text", "tekst",
        ],
    }

    # Map task types to required agent roles
    TASK_TO_ROLE: Dict[TaskType, AgentRole] = {
        TaskType.COPY_WRITING: AgentRole.COPYWRITER,
        TaskType.IMAGE_GENERATION: AgentRole.IMAGE_GENERATOR,
        TaskType.DATA_ANALYSIS: AgentRole.DATA_ANALYST,
        TaskType.CODE_WRITING: AgentRole.CODE_WRITER,
        TaskType.VIDEO_EDITING: AgentRole.VIDEO_EDITOR,
        TaskType.AUDIO_PRODUCTION: AgentRole.AUDIO_PRODUCER,
        TaskType.TRANSLATION: AgentRole.TRANSLATOR,
        TaskType.RESEARCH: AgentRole.RESEARCHER,
    }

    def detect_task_type(self, user_request: str) -> TaskType:
        """
        Detect task type from user request.

        Args:
            user_request: User's job description

        Returns:
            Detected task type
        """
        request_lower = (user_request or "").lower()

        # Check each task type in order of specificity
        for task_type, keywords in self.TASK_KEYWORDS.items():
            if any(keyword in request_lower for keyword in keywords):
                return task_type

        # Default to unknown if no match
        return TaskType.UNKNOWN

    def get_required_role(self, task_type: TaskType) -> Optional[AgentRole]:
        """
        Get the agent role required for a task type.

        Args:
            task_type: Detected task type

        Returns:
            Required agent role or None if unknown
        """
        return self.TASK_TO_ROLE.get(task_type)

    def detect_with_role(self, user_request: str) -> Tuple[TaskType, Optional[AgentRole]]:
        """
        Detect both task type and required role.

        Returns:
            (task_type, required_role)
        """
        task_type = self.detect_task_type(user_request)
        role = self.get_required_role(task_type)
        return task_type, role


# Singleton instance
task_type_detector = TaskTypeDetector()
