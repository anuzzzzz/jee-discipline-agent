"""
Conversation state for Mahavihara.

State is stored in Supabase (conversation_states table) between messages.
Each user has their own state that persists across the conversation.
"""

from typing import TypedDict, Optional
from datetime import datetime


class DrillState(TypedDict, total=False):
    """State for an active drill session."""
    mistake_id: str              # Which mistake we're drilling
    drill_id: str                # Current drill question ID
    question_text: str           # The question
    options: dict                # {A: "...", B: "...", C: "...", D: "..."}
    correct_option: str          # "A", "B", "C", or "D"
    solution: str                # Explanation
    hint_1: Optional[str]
    hint_2: Optional[str]
    hint_3: Optional[str]
    attempts: int                # How many tries on this question
    hints_given: int             # How many hints shown


class ConversationState(TypedDict, total=False):
    """
    Full conversation state for a user.

    This is saved to DB after each message and loaded at start of next.
    """
    # User info (cached for quick access)
    user_id: str
    user_name: Optional[str]
    phone_number: str

    # Conversation phase
    phase: str  # "onboarding", "idle", "drilling", "reporting_mistake"

    # Active drill (if any)
    active_drill: Optional[DrillState]

    # Session stats (reset daily)
    questions_today: int
    correct_today: int
    session_started_at: Optional[str]  # ISO timestamp

    # Last interaction
    last_intent: Optional[str]
    last_message_at: Optional[str]


def create_initial_state(user_id: str, phone_number: str, user_name: str = None) -> ConversationState:
    """Create a fresh state for a new user."""
    return ConversationState(
        user_id=user_id,
        user_name=user_name,
        phone_number=phone_number,
        phase="onboarding",
        active_drill=None,
        questions_today=0,
        correct_today=0,
        session_started_at=None,
        last_intent=None,
        last_message_at=datetime.utcnow().isoformat()
    )


def has_active_drill(state: ConversationState) -> bool:
    """Check if user is in the middle of a drill."""
    return state.get("active_drill") is not None


def clear_drill(state: ConversationState) -> ConversationState:
    """Clear the active drill from state."""
    state["active_drill"] = None
    state["phase"] = "idle"
    return state


def update_drill_attempts(state: ConversationState) -> ConversationState:
    """Increment attempts on current drill."""
    if state.get("active_drill"):
        state["active_drill"]["attempts"] = state["active_drill"].get("attempts", 0) + 1
    return state


def increment_hints(state: ConversationState) -> ConversationState:
    """Increment hints given on current drill."""
    if state.get("active_drill"):
        state["active_drill"]["hints_given"] = state["active_drill"].get("hints_given", 0) + 1
    return state
