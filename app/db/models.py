"""
Pydantic models for database tables.
These models are used for validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, time
from enum import Enum


# ==================== ENUMS ====================

class ExamType(str, Enum):
    JEE = "JEE"
    NEET = "NEET"
    BOTH = "BOTH"


class Subject(str, Enum):
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    MATHEMATICS = "mathematics"


class MistakeType(str, Enum):
    CONCEPTUAL = "conceptual"
    CALCULATION = "calculation"
    SILLY = "silly"
    FORMULA = "formula"
    SIGN = "sign"
    UNIT = "unit"


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== USER MODELS ====================

class UserBase(BaseModel):
    """Base user fields for creation."""
    phone_number: str
    name: Optional[str] = None
    exam_type: ExamType = ExamType.JEE
    target_year: Optional[int] = None
    subjects_enabled: List[str] = ["physics"]
    nudge_time: time = time(18, 0)  # 6 PM default
    language: str = "en"


class UserCreate(UserBase):
    """Fields needed to create a new user."""
    pass


class User(UserBase):
    """Complete user model from database."""
    id: str
    current_streak: int = 0
    longest_streak: int = 0
    total_mistakes_fixed: int = 0
    last_active_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    last_message_at: Optional[datetime] = None
    can_send_freeform: bool = True

    class Config:
        from_attributes = True


# ==================== QUESTION MODELS ====================

class QuestionBase(BaseModel):
    """Base question fields."""
    subject: str
    chapter: str
    topic: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str = Field(..., pattern="^[ABCD]$")
    solution: str
    difficulty: int = Field(default=1, ge=1, le=5)
    source: Optional[str] = None
    is_pyq: bool = False


class QuestionCreate(QuestionBase):
    """Fields for creating a question."""
    question_image_url: Optional[str] = None
    question_latex: Optional[str] = None
    solution_image_url: Optional[str] = None
    solution_latex: Optional[str] = None
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    hint_3: Optional[str] = None
    source_question_id: Optional[str] = None
    year: Optional[int] = None
    embedding: Optional[List[float]] = None
    content_hash: Optional[str] = None


class Question(QuestionCreate):
    """Complete question model from database."""
    id: str
    topic_id: Optional[str] = None
    is_verified: bool = False
    error_reports: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== MISTAKE MODELS ====================

class MistakeClassification(BaseModel):
    """Output from LLM when classifying a mistake."""
    topic: str
    subtopic: str
    mistake_type: MistakeType
    misconception: str
    difficulty: int = Field(default=2, ge=1, le=5)


class MistakeCreate(BaseModel):
    """Fields for creating a mistake."""
    user_id: str
    subject: str
    chapter: Optional[str] = None
    topic: Optional[str] = None
    custom_mistake_text: Optional[str] = None
    original_question_id: Optional[str] = None
    topic_id: Optional[str] = None


class Mistake(BaseModel):
    """Complete mistake model from database."""
    id: str
    user_id: str
    subject: str
    chapter: Optional[str] = None
    topic: Optional[str] = None
    topic_id: Optional[str] = None
    original_question_id: Optional[str] = None
    custom_mistake_text: Optional[str] = None
    mistake_type: Optional[str] = None
    misconception: Optional[str] = None
    misconception_keywords: Optional[List[str]] = None
    times_drilled: int = 0
    times_correct: int = 0
    mastery_score: float = 0.0
    is_mastered: bool = False
    next_review_at: datetime
    easiness_factor: float = 2.5
    interval_days: int = 1
    repetition_count: int = 0
    created_at: datetime
    last_drilled_at: Optional[datetime] = None
    mastered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== DRILL MODELS ====================

class DrillQuestion(BaseModel):
    """A drill question ready to present to student."""
    id: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    solution: str
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    hint_3: Optional[str] = None
    difficulty: int = 2
    source: str = "generated"


class PreGeneratedDrill(BaseModel):
    """Pre-generated drill from database."""
    id: str
    mistake_id: str
    question_id: Optional[str] = None
    generated_question_text: Optional[str] = None
    generated_option_a: Optional[str] = None
    generated_option_b: Optional[str] = None
    generated_option_c: Optional[str] = None
    generated_option_d: Optional[str] = None
    generated_correct_option: Optional[str] = None
    generated_solution: Optional[str] = None
    generated_hint_1: Optional[str] = None
    generated_hint_2: Optional[str] = None
    generated_hint_3: Optional[str] = None
    generation_method: Optional[str] = None
    difficulty: int = 1
    order_index: int = 0
    is_used: bool = False
    used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DrillAttempt(BaseModel):
    """Record of a student's answer to a drill."""
    id: str
    user_id: str
    mistake_id: str
    drill_id: Optional[str] = None
    question_id: Optional[str] = None
    student_answer: str
    correct_answer: str
    is_correct: bool
    time_taken_seconds: Optional[int] = None
    hints_used: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== MESSAGE MODELS ====================

class MessageCreate(BaseModel):
    """Fields for saving a message."""
    user_id: str
    direction: MessageDirection
    message_text: Optional[str] = None
    message_type: str = "text"
    whatsapp_message_id: Optional[str] = None


class Message(MessageCreate):
    """Complete message from database."""
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== BACKGROUND JOB MODELS ====================

class BackgroundJobCreate(BaseModel):
    """Fields for creating a background job."""
    job_type: str
    payload: dict


class BackgroundJob(BackgroundJobCreate):
    """Complete job from database."""
    id: str
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== API RESPONSE MODELS ====================

class UserStats(BaseModel):
    """User statistics for display."""
    streak: int
    longest_streak: int
    total_mistakes: int
    mastered_mistakes: int
    pending_mistakes: int
    questions_today: int
    correct_today: int
    accuracy_today: float
    last_active: Optional[datetime] = None


class DrillSession(BaseModel):
    """Current drill session state."""
    active_mistake_id: Optional[str] = None
    current_question: Optional[DrillQuestion] = None
    hints_given: int = 0
    attempts_this_question: int = 0
    questions_answered_today: int = 0
    correct_today: int = 0
