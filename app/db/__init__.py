"""Database models and utilities."""

from app.db.supabase import (
    get_supabase_client,
    get_service_client,
    init_supabase,
    supabase,
)
from app.db.models import (
    # Enums
    ExamType,
    Subject,
    MistakeType,
    MessageDirection,
    JobStatus,
    # User models
    UserBase,
    UserCreate,
    User,
    # Question models
    QuestionBase,
    QuestionCreate,
    Question,
    # Mistake models
    MistakeClassification,
    MistakeCreate,
    Mistake,
    # Drill models
    DrillQuestion,
    PreGeneratedDrill,
    DrillAttempt,
    # Message models
    MessageCreate,
    Message,
    # Job models
    BackgroundJobCreate,
    BackgroundJob,
    # API response models
    UserStats,
    DrillSession,
)

__all__ = [
    # Supabase
    "get_supabase_client",
    "get_service_client",
    "init_supabase",
    "supabase",
    # Enums
    "ExamType",
    "Subject",
    "MistakeType",
    "MessageDirection",
    "JobStatus",
    "UserBase",
    "UserCreate",
    "User",
    "QuestionBase",
    "QuestionCreate",
    "Question",
    "MistakeClassification",
    "MistakeCreate",
    "Mistake",
    "DrillQuestion",
    "PreGeneratedDrill",
    "DrillAttempt",
    "MessageCreate",
    "Message",
    "BackgroundJobCreate",
    "BackgroundJob",
    "UserStats",
    "DrillSession",
]
