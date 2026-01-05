"""
Message Router for Mahavihara.

This is the main entry point for processing messages.
It classifies intent and routes to the appropriate handler.
"""

from typing import Optional, Tuple
from datetime import datetime

from app.db.queries import (
    get_or_create_user,
    get_conversation_state,
    save_conversation_state,
    update_user_last_message,
    save_message,
    is_duplicate_message,
    get_pending_mistakes_count,
)
from app.services.llm import classify_intent
from app.services.whatsapp import WhatsAppService
from app.agent.state import (
    ConversationState,
    create_initial_state,
    has_active_drill,
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


async def process_message(
    phone_number: str,
    message_text: Optional[str] = None,
    image_url: Optional[str] = None,
    whatsapp_message_id: Optional[str] = None
) -> str:
    """
    Main entry point for processing incoming messages.

    This function:
    1. Gets/creates user
    2. Loads conversation state
    3. Classifies intent
    4. Routes to appropriate handler
    5. Saves state
    6. Returns response

    Args:
        phone_number: User's WhatsApp number
        message_text: Text message (if any)
        image_url: Image URL (if photo was sent)
        whatsapp_message_id: For deduplication

    Returns:
        Response text to send back to user
    """
    # Deduplicate (WhatsApp sometimes sends twice)
    if whatsapp_message_id and await is_duplicate_message(whatsapp_message_id):
        print(f"⚠️ Duplicate message ignored: {whatsapp_message_id}")
        return None

    # Get or create user
    user = await get_or_create_user(phone_number)

    # Update last message timestamp (for 24-hour window)
    await update_user_last_message(user.id)

    # Save inbound message to history
    await save_message(
        user_id=user.id,
        direction="inbound",
        message_text=message_text,
        message_type="image" if image_url else "text",
        whatsapp_message_id=whatsapp_message_id
    )

    # Load conversation state
    state_data = await get_conversation_state(user.id)

    if not state_data:
        state = create_initial_state(user.id, phone_number, user.name)
    else:
        state = ConversationState(**state_data)

    # Update state with current user info
    state["user_id"] = user.id
    state["phone_number"] = phone_number
    state["user_name"] = user.name
    state["last_message_at"] = datetime.utcnow().isoformat()

    # Route and handle
    response, new_state = await route_message(
        user=user,
        state=state,
        message=message_text or "",
        image_url=image_url
    )

    # Save updated state
    await save_conversation_state(user.id, dict(new_state))

    # Save outbound message to history
    if response:
        await save_message(
            user_id=user.id,
            direction="outbound",
            message_text=response
        )

    return response


async def route_message(
    user,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Route message to appropriate handler based on intent.

    Returns:
        Tuple of (response_text, updated_state)
    """
    # Check if user is inactive (said STOP before)
    if not user.is_active:
        # Only respond to START
        if message.strip().upper() == "START":
            from app.db.queries import update_user
            await update_user(user.id, {"is_active": True})
            return (
                "Welcome back! Mahavihara missed you.\n\n"
                "Reply *GO* to start drilling your mistakes!"
            ), state
        else:
            # Don't respond to inactive users
            return None, state

    # Special case: Onboarding (waiting for name)
    if state.get("phase") == "onboarding" and user.name is None:
        # Check if this looks like a name (not a command or greeting)
        upper_msg = message.strip().upper()
        excluded = ["GO", "STATS", "HELP", "STOP", "START", "HI", "HELLO", "HEY", "HOLA", "YO", "SUP", "NAMASTE"]
        if upper_msg not in excluded and not upper_msg.startswith("HI ") and not upper_msg.startswith("HELLO "):
            return await handle_onboarding(user, state, message, image_url)

    # Special case: Active drill - check if answering
    if has_active_drill(state):
        # If message is A/B/C/D, treat as answer
        first_char = message.strip().upper()[:1]
        if first_char in ["A", "B", "C", "D"]:
            return await handle_answer_drill(user, state, message, image_url)

    # Quick keyword matching for common intents (skip LLM for obvious cases)
    upper_msg = message.strip().upper()
    quick_intents = {
        "GO": "START_DRILL",
        "LET'S GO": "START_DRILL",
        "LETS GO": "START_DRILL",
        "START": "START_DRILL",
        "BEGIN": "START_DRILL",
        "PRACTICE": "START_DRILL",
        "STATS": "CHECK_STATS",
        "MY STATS": "CHECK_STATS",
        "PROGRESS": "CHECK_STATS",
        "HELP": "HELP",
        "STOP": "STOP",
        "UNSUBSCRIBE": "STOP",
    }

    if upper_msg in quick_intents:
        intent = quick_intents[upper_msg]
        state["last_intent"] = intent
        handlers = {
            "START_DRILL": handle_start_drill,
            "CHECK_STATS": handle_stats,
            "HELP": handle_help,
            "STOP": handle_stop,
        }
        handler = handlers.get(intent)
        if handler:
            return await handler(user, state, message, image_url)

    # Classify intent using LLM
    pending = await get_pending_mistakes_count(user.id)
    intent_result = await classify_intent(
        message=message,
        has_active_drill=has_active_drill(state),
        pending_mistakes=pending
    )

    intent = intent_result.get("intent", "CHITCHAT")
    confidence = intent_result.get("confidence", 0.5)

    print(f"Intent: {intent} ({confidence:.1%}) for: '{message[:50]}...'")

    # Update state with last intent
    state["last_intent"] = intent

    # Route to handler
    handlers = {
        "GREETING": handle_greeting,
        "REPORT_MISTAKE": handle_report_mistake,
        "START_DRILL": handle_start_drill,
        "ANSWER_DRILL": handle_answer_drill,
        "CHECK_STATS": handle_stats,
        "HELP": handle_help,
        "STOP": handle_stop,
        "CHITCHAT": handle_chitchat,
    }

    handler = handlers.get(intent, handle_chitchat)

    return await handler(user, state, message, image_url)


async def send_response(phone_number: str, response: str) -> None:
    """
    Send response back to user via WhatsApp.

    This is called by the webhook after process_message.
    """
    if response:
        await WhatsAppService.send_message(
            phone_number=phone_number,
            message=response
        )
