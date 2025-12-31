"""
Database queries for Tiger Mom AI.
All Supabase interactions go through this module.

Why centralize queries?
1. Single place to update if schema changes
2. Easier to test/mock
3. Type safety with Pydantic models
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import hashlib

from app.db.supabase import get_supabase_client
from app.db.models import (
    User, UserCreate,
    Question, QuestionCreate,
    Mistake, MistakeCreate, MistakeClassification,
    PreGeneratedDrill, DrillAttempt,
    Message, MessageDirection,
    BackgroundJob, JobStatus,
    UserStats
)


# ==================== USER QUERIES ====================

async def get_user_by_phone(phone_number: str) -> Optional[User]:
    """Get user by phone number."""
    client = get_supabase_client()

    result = client.table("users").select("*").eq(
        "phone_number", phone_number
    ).execute()

    if result.data and len(result.data) > 0:
        return User(**result.data[0])
    return None


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by ID."""
    client = get_supabase_client()

    result = client.table("users").select("*").eq("id", user_id).execute()

    if result.data and len(result.data) > 0:
        return User(**result.data[0])
    return None


async def create_user(user_data: UserCreate) -> User:
    """Create a new user."""
    client = get_supabase_client()

    result = client.table("users").insert(
        user_data.model_dump(mode="json")
    ).execute()

    return User(**result.data[0])


async def get_or_create_user(phone_number: str) -> User:
    """
    Get existing user or create new one.
    This is called on every incoming WhatsApp message.
    """
    user = await get_user_by_phone(phone_number)

    if user is None:
        user = await create_user(UserCreate(phone_number=phone_number))
        print(f"📱 New user created: {phone_number}")

    return user


async def update_user(user_id: str, updates: Dict[str, Any]) -> User:
    """Update user fields."""
    client = get_supabase_client()

    result = client.table("users").update(updates).eq("id", user_id).execute()

    return User(**result.data[0])


async def update_user_last_message(user_id: str) -> None:
    """
    Update user's last_message_at timestamp.
    Called on every incoming message for 24-hour window tracking.
    """
    client = get_supabase_client()

    now = datetime.utcnow().isoformat()
    client.table("users").update({
        "last_message_at": now,
        "last_active_at": now
    }).eq("id", user_id).execute()


async def update_user_streak(user_id: str, increment: bool = True) -> int:
    """
    Update user's streak.

    Args:
        increment: True to add 1, False to reset to 0

    Returns:
        New streak value
    """
    user = await get_user_by_id(user_id)
    if not user:
        return 0

    if increment:
        new_streak = user.current_streak + 1
        longest = max(user.longest_streak, new_streak)
    else:
        new_streak = 0
        longest = user.longest_streak

    await update_user(user_id, {
        "current_streak": new_streak,
        "longest_streak": longest
    })

    return new_streak


async def set_user_inactive(user_id: str) -> None:
    """
    Set user as inactive.
    Called when user sends STOP command (WhatsApp compliance).
    """
    client = get_supabase_client()

    client.table("users").update({
        "is_active": False
    }).eq("id", user_id).execute()

    print(f"🛑 User {user_id} deactivated (STOP command)")


async def get_user_stats(user_id: str) -> UserStats:
    """Get comprehensive user statistics for display."""
    client = get_supabase_client()

    user = await get_user_by_id(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Get mistake counts
    mistakes_result = client.table("student_mistakes").select(
        "id, is_mastered"
    ).eq("user_id", user_id).execute()

    total_mistakes = len(mistakes_result.data)
    mastered = sum(1 for m in mistakes_result.data if m.get("is_mastered"))
    pending = total_mistakes - mastered

    # Get today's attempts
    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    attempts_result = client.table("drill_attempts").select(
        "is_correct"
    ).eq("user_id", user_id).gte(
        "created_at", today_start.isoformat()
    ).execute()

    questions_today = len(attempts_result.data)
    correct_today = sum(1 for a in attempts_result.data if a.get("is_correct"))
    accuracy = (correct_today / questions_today * 100) if questions_today > 0 else 0.0

    return UserStats(
        streak=user.current_streak,
        longest_streak=user.longest_streak,
        total_mistakes=total_mistakes,
        mastered_mistakes=mastered,
        pending_mistakes=pending,
        questions_today=questions_today,
        correct_today=correct_today,
        accuracy_today=accuracy,
        last_active=user.last_active_at
    )


async def get_users_for_nudge() -> List[User]:
    """
    Get active users who should be nudged.
    Filters: is_active=True AND haven't practiced today
    """
    client = get_supabase_client()

    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    result = client.table("users").select("*").eq(
        "is_active", True
    ).lt(
        "last_active_at", today_start.isoformat()
    ).execute()

    return [User(**u) for u in result.data]


# ==================== QUESTION QUERIES ====================

async def create_question(question_data: QuestionCreate) -> Question:
    """Create a new question with deduplication."""
    client = get_supabase_client()

    # Generate content hash for deduplication
    content = (
        question_data.question_text +
        question_data.option_a +
        question_data.option_b
    )
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    data = question_data.model_dump(mode="json")
    data["content_hash"] = content_hash

    # Upsert - insert or update if hash exists
    result = client.table("questions").upsert(
        data, on_conflict="content_hash"
    ).execute()

    return Question(**result.data[0])


async def get_question_by_id(question_id: str) -> Optional[Question]:
    """Get question by ID."""
    client = get_supabase_client()

    result = client.table("questions").select("*").eq("id", question_id).execute()

    if result.data and len(result.data) > 0:
        return Question(**result.data[0])
    return None


async def get_questions_by_topic(
    subject: str,
    chapter: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty: Optional[int] = None,
    limit: int = 10
) -> List[Question]:
    """Get questions filtered by topic/difficulty."""
    client = get_supabase_client()

    query = client.table("questions").select("*").eq("subject", subject)

    if chapter:
        query = query.eq("chapter", chapter)
    if topic:
        query = query.eq("topic", topic)
    if difficulty:
        query = query.eq("difficulty", difficulty)

    result = query.limit(limit).execute()

    return [Question(**q) for q in result.data]


async def get_similar_questions(
    misconception: str,
    topic: str,
    subject: str,
    limit: int = 3,
    exclude_question_id: Optional[str] = None
) -> List[Question]:
    """
    Get questions similar to a misconception.

    Currently uses keyword matching.
    TODO: Upgrade to vector similarity search with embeddings.
    """
    client = get_supabase_client()

    query = client.table("questions").select("*").eq(
        "subject", subject
    ).ilike(
        "topic", f"%{topic}%"
    )

    if exclude_question_id:
        query = query.neq("id", exclude_question_id)

    result = query.limit(limit).execute()

    return [Question(**q) for q in result.data]


async def get_question_count(subject: Optional[str] = None) -> int:
    """Get total question count, optionally filtered by subject."""
    client = get_supabase_client()

    query = client.table("questions").select("id", count="exact")

    if subject:
        query = query.eq("subject", subject)

    result = query.execute()

    return result.count or 0


# ==================== MISTAKE QUERIES ====================

async def create_mistake(
    user_id: str,
    subject: str,
    chapter: Optional[str] = None,
    topic: Optional[str] = None,
    custom_mistake_text: Optional[str] = None,
    original_question_id: Optional[str] = None,
    classification: Optional[MistakeClassification] = None
) -> Mistake:
    """
    Create a new mistake record.

    This is called when a student reports a mistake.
    The classification comes from LLM analysis.
    """
    client = get_supabase_client()

    data = {
        "user_id": user_id,
        "subject": subject,
        "chapter": chapter or (classification.topic if classification else None),
        "topic": topic or (classification.subtopic if classification else None),
        "custom_mistake_text": custom_mistake_text,
        "original_question_id": original_question_id,
    }

    if classification:
        data["mistake_type"] = classification.mistake_type.value
        data["misconception"] = classification.misconception

    result = client.table("student_mistakes").insert(data).execute()

    return Mistake(**result.data[0])


async def get_mistake_by_id(mistake_id: str) -> Optional[Mistake]:
    """Get mistake by ID."""
    client = get_supabase_client()

    result = client.table("student_mistakes").select("*").eq(
        "id", mistake_id
    ).execute()

    if result.data and len(result.data) > 0:
        return Mistake(**result.data[0])
    return None


async def get_user_mistakes(
    user_id: str,
    mastered: Optional[bool] = None,
    limit: int = 50
) -> List[Mistake]:
    """Get user's mistakes, optionally filtered by mastery status."""
    client = get_supabase_client()

    query = client.table("student_mistakes").select("*").eq("user_id", user_id)

    if mastered is not None:
        query = query.eq("is_mastered", mastered)

    result = query.order("created_at", desc=True).limit(limit).execute()

    return [Mistake(**m) for m in result.data]


async def get_next_due_mistake(user_id: str) -> Optional[Mistake]:
    """
    Get the next mistake due for review (spaced repetition).

    Returns the mistake with earliest next_review_at that's:
    - Not mastered
    - Due for review (next_review_at <= now)
    """
    client = get_supabase_client()

    now = datetime.utcnow().isoformat()

    result = client.table("student_mistakes").select("*").eq(
        "user_id", user_id
    ).eq(
        "is_mastered", False
    ).lte(
        "next_review_at", now
    ).order(
        "next_review_at"
    ).limit(1).execute()

    if result.data and len(result.data) > 0:
        return Mistake(**result.data[0])
    return None


async def get_pending_mistakes_count(user_id: str) -> int:
    """Get count of pending (not mastered) mistakes."""
    client = get_supabase_client()

    result = client.table("student_mistakes").select(
        "id", count="exact"
    ).eq("user_id", user_id).eq("is_mastered", False).execute()

    return result.count or 0


async def update_mistake_after_drill(
    mistake_id: str,
    is_correct: bool
) -> Mistake:
    """
    Update mistake after a drill attempt.

    Uses SM-2 spaced repetition algorithm:
    - Correct: Increase interval, improve easiness
    - Wrong: Reset interval, decrease easiness
    """
    mistake = await get_mistake_by_id(mistake_id)
    if not mistake:
        raise ValueError(f"Mistake {mistake_id} not found")

    client = get_supabase_client()

    # Update drill counts
    times_drilled = mistake.times_drilled + 1
    times_correct = mistake.times_correct + (1 if is_correct else 0)

    # SM-2 algorithm
    ef = mistake.easiness_factor

    if is_correct:
        # Correct answer - increase interval
        ef = min(2.5, ef + 0.1)
        repetition = mistake.repetition_count + 1

        if repetition == 1:
            interval = 1  # Review tomorrow
        elif repetition == 2:
            interval = 6  # Review in 6 days
        else:
            interval = int(mistake.interval_days * ef)
    else:
        # Wrong answer - reset
        ef = max(1.3, ef - 0.2)
        repetition = 0
        interval = 1  # Review tomorrow

    # Calculate mastery (need 80%+ over 3+ drills)
    mastery_score = times_correct / times_drilled if times_drilled > 0 else 0
    is_mastered = mastery_score >= 0.8 and times_drilled >= 3

    next_review = datetime.utcnow() + timedelta(days=interval)

    updates = {
        "times_drilled": times_drilled,
        "times_correct": times_correct,
        "mastery_score": mastery_score,
        "is_mastered": is_mastered,
        "easiness_factor": ef,
        "interval_days": interval,
        "repetition_count": repetition,
        "next_review_at": next_review.isoformat(),
        "last_drilled_at": datetime.utcnow().isoformat()
    }

    # Mark mastery timestamp if just mastered
    if is_mastered and not mistake.is_mastered:
        updates["mastered_at"] = datetime.utcnow().isoformat()
        print(f"🎉 Mistake {mistake_id} MASTERED!")

    result = client.table("student_mistakes").update(updates).eq(
        "id", mistake_id
    ).execute()

    return Mistake(**result.data[0])


# ==================== PRE-GENERATED DRILL QUERIES ====================

async def save_pre_generated_drill(
    mistake_id: str,
    question_id: Optional[str] = None,
    generated_question_text: Optional[str] = None,
    generated_option_a: Optional[str] = None,
    generated_option_b: Optional[str] = None,
    generated_option_c: Optional[str] = None,
    generated_option_d: Optional[str] = None,
    generated_correct_option: Optional[str] = None,
    generated_solution: Optional[str] = None,
    generated_hint_1: Optional[str] = None,
    generated_hint_2: Optional[str] = None,
    generated_hint_3: Optional[str] = None,
    generation_method: str = "llm_generated",
    difficulty: int = 2,
    order_index: int = 0
) -> PreGeneratedDrill:
    """Save a pre-generated drill question."""
    client = get_supabase_client()

    data = {
        "mistake_id": mistake_id,
        "question_id": question_id,
        "generated_question_text": generated_question_text,
        "generated_option_a": generated_option_a,
        "generated_option_b": generated_option_b,
        "generated_option_c": generated_option_c,
        "generated_option_d": generated_option_d,
        "generated_correct_option": generated_correct_option,
        "generated_solution": generated_solution,
        "generated_hint_1": generated_hint_1,
        "generated_hint_2": generated_hint_2,
        "generated_hint_3": generated_hint_3,
        "generation_method": generation_method,
        "difficulty": difficulty,
        "order_index": order_index
    }

    result = client.table("pre_generated_drills").insert(data).execute()

    return PreGeneratedDrill(**result.data[0])


async def get_next_unused_drill(mistake_id: str) -> Optional[PreGeneratedDrill]:
    """Get the next unused pre-generated drill for a mistake."""
    client = get_supabase_client()

    result = client.table("pre_generated_drills").select("*").eq(
        "mistake_id", mistake_id
    ).eq(
        "is_used", False
    ).order("order_index").limit(1).execute()

    if result.data and len(result.data) > 0:
        return PreGeneratedDrill(**result.data[0])
    return None


async def mark_drill_used(drill_id: str) -> None:
    """Mark a pre-generated drill as used."""
    client = get_supabase_client()

    client.table("pre_generated_drills").update({
        "is_used": True,
        "used_at": datetime.utcnow().isoformat()
    }).eq("id", drill_id).execute()


# ==================== DRILL ATTEMPT QUERIES ====================

async def save_drill_attempt(
    user_id: str,
    mistake_id: str,
    student_answer: str,
    correct_answer: str,
    is_correct: bool,
    drill_id: Optional[str] = None,
    question_id: Optional[str] = None,
    time_taken_seconds: Optional[int] = None,
    hints_used: int = 0
) -> DrillAttempt:
    """Save a drill attempt."""
    client = get_supabase_client()

    data = {
        "user_id": user_id,
        "mistake_id": mistake_id,
        "drill_id": drill_id,
        "question_id": question_id,
        "student_answer": student_answer,
        "correct_answer": correct_answer,
        "is_correct": is_correct,
        "time_taken_seconds": time_taken_seconds,
        "hints_used": hints_used
    }

    result = client.table("drill_attempts").insert(data).execute()

    return DrillAttempt(**result.data[0])


async def get_today_attempts(user_id: str) -> List[DrillAttempt]:
    """Get user's drill attempts from today."""
    client = get_supabase_client()

    today_start = datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    result = client.table("drill_attempts").select("*").eq(
        "user_id", user_id
    ).gte(
        "created_at", today_start.isoformat()
    ).execute()

    return [DrillAttempt(**a) for a in result.data]


# ==================== MESSAGE QUERIES ====================

async def save_message(
    user_id: str,
    direction: str,
    message_text: Optional[str] = None,
    message_type: str = "text",
    whatsapp_message_id: Optional[str] = None
) -> Message:
    """Save a message to history."""
    client = get_supabase_client()

    data = {
        "user_id": user_id,
        "direction": direction,
        "message_text": message_text,
        "message_type": message_type,
        "whatsapp_message_id": whatsapp_message_id
    }

    result = client.table("message_history").insert(data).execute()

    return Message(**result.data[0])


async def is_duplicate_message(whatsapp_message_id: str) -> bool:
    """
    Check if a message has already been processed.
    WhatsApp sometimes sends the same webhook twice.
    """
    if not whatsapp_message_id:
        return False

    client = get_supabase_client()

    result = client.table("message_history").select("id").eq(
        "whatsapp_message_id", whatsapp_message_id
    ).execute()

    return len(result.data) > 0


# ==================== CONVERSATION STATE QUERIES ====================

async def get_conversation_state(user_id: str) -> Dict[str, Any]:
    """Get conversation state for a user."""
    client = get_supabase_client()

    result = client.table("conversation_states").select("*").eq(
        "user_id", user_id
    ).execute()

    if result.data and len(result.data) > 0:
        return result.data[0].get("state_data", {})
    return {}


async def save_conversation_state(user_id: str, state: Dict[str, Any]) -> None:
    """Save conversation state for a user (upsert)."""
    client = get_supabase_client()

    client.table("conversation_states").upsert({
        "user_id": user_id,
        "state_data": state
    }, on_conflict="user_id").execute()


# ==================== BACKGROUND JOB QUERIES ====================

async def create_background_job(
    job_type: str,
    payload: Dict[str, Any]
) -> BackgroundJob:
    """Create a new background job."""
    client = get_supabase_client()

    data = {
        "job_type": job_type,
        "payload": payload
    }

    result = client.table("background_jobs").insert(data).execute()

    return BackgroundJob(**result.data[0])


async def get_pending_jobs(limit: int = 10) -> List[BackgroundJob]:
    """Get pending background jobs."""
    client = get_supabase_client()

    result = client.table("background_jobs").select("*").eq(
        "status", "pending"
    ).order("created_at").limit(limit).execute()

    return [BackgroundJob(**j) for j in result.data]


async def update_job_status(
    job_id: str,
    status: str,
    error_message: Optional[str] = None
) -> None:
    """Update background job status."""
    client = get_supabase_client()

    updates: Dict[str, Any] = {"status": status}

    if status == "processing":
        updates["started_at"] = datetime.utcnow().isoformat()
    elif status in ["completed", "failed"]:
        updates["completed_at"] = datetime.utcnow().isoformat()

    if error_message:
        updates["error_message"] = error_message

    client.table("background_jobs").update(updates).eq("id", job_id).execute()


# ==================== NUDGE QUERIES ====================

async def log_nudge(
    user_id: str,
    nudge_type: str,
    message_sent: str,
    template_name: Optional[str] = None
) -> None:
    """Log a nudge that was sent."""
    client = get_supabase_client()

    client.table("nudge_logs").insert({
        "user_id": user_id,
        "nudge_type": nudge_type,
        "template_name": template_name,
        "message_sent": message_sent
    }).execute()
