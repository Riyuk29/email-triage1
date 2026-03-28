"""
Email Triage Environment - Type-Safe Models (Pydantic version)
"""
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class Priority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    IGNORE = "ignore"

class Category(str, Enum):
    CUSTOMER_COMPLAINT = "customer_complaint"
    SALES_INQUIRY = "sales_inquiry"
    TECHNICAL_SUPPORT = "technical_support"
    BILLING = "billing"
    PARTNERSHIP = "partnership"
    INTERNAL = "internal"
    SPAM = "spam"
    LEGAL = "legal"
    PRESS = "press"
    OTHER = "other"

class Department(str, Enum):
    SUPPORT = "support"
    SALES = "sales"
    ENGINEERING = "engineering"
    FINANCE = "finance"
    LEGAL = "legal"
    MARKETING = "marketing"
    EXECUTIVE = "executive"
    IGNORE = "ignore"

class ActionType(str, Enum):
    CLASSIFY = "classify"
    RESPOND = "respond"
    ESCALATE = "escalate"
    ARCHIVE = "archive"
    FLAG = "flag"
    SKIP = "skip"


class Email(BaseModel):
    id: str = ""
    sender: str = ""
    sender_domain: str = ""
    subject: str = ""
    body: str = ""
    timestamp: str = ""
    has_attachments: bool = False
    thread_length: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TriageAction(BaseModel):
    action_type: ActionType = ActionType.CLASSIFY
    category: Optional[Category] = None
    priority: Optional[Priority] = None
    department: Optional[Department] = None
    draft_response: Optional[str] = None
    escalation_reason: Optional[str] = None
    flag_reason: Optional[str] = None
    reasoning: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriageAction":
        # Remove empty strings to avoid validation errors for Optional fields
        cleaned_data = {k: v for k, v in data.items() if v != ""}
        return cls.model_validate(cleaned_data)


class TriageObservation(BaseModel):
    done: bool = False
    reward: Optional[float] = None
    current_email: Optional[Email] = None
    email_index: int = 0
    total_emails: int = 0
    emails_remaining: int = 0
    action_feedback: str = ""
    partial_score: float = 0.0
    emails_processed: int = 0
    correct_classifications: int = 0
    cumulative_score: float = 0.0
    task_instructions: str = ""


class TriageState(BaseModel):
    episode_id: Optional[str] = None
    step_count: int = 0
    task_id: str = ""
    task_name: str = ""
    task_difficulty: str = ""
    total_emails: int = 0
    emails_processed: int = 0
    cumulative_score: float = 0.0
    max_steps: int = 50


class GradeResult(BaseModel):
    score: float = 0.0
    passed: bool = False
    breakdown: Dict[str, float] = Field(default_factory=dict)
    details: str = ""

    @model_validator(mode="after")
    def clamp_score(self):
        if self.score is not None:
            self.score = max(0.0, min(1.0, float(self.score)))
        return self
