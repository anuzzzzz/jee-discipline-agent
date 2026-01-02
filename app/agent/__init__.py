"""
Mahavihara Agent - Simple Router Pattern.

Main entry point: process_message()
"""

from app.agent.router import process_message, route_message, send_response
from app.agent.state import (
    ConversationState,
    DrillState,
    create_initial_state,
    has_active_drill,
    clear_drill,
)
from app.agent.handlers import (
    handle_greeting,
    handle_onboarding,
    handle_report_mistake,
    handle_start_drill,
    handle_answer_drill,
    handle_stats,
    handle_help,
    handle_stop,
    handle_chitchat,
)

__all__ = [
    # Main entry
    "process_message",
    "route_message",
    "send_response",
    # State
    "ConversationState",
    "DrillState",
    "create_initial_state",
    "has_active_drill",
    "clear_drill",
    # Handlers
    "handle_greeting",
    "handle_onboarding",
    "handle_report_mistake",
    "handle_start_drill",
    "handle_answer_drill",
    "handle_stats",
    "handle_help",
    "handle_stop",
    "handle_chitchat",
]
