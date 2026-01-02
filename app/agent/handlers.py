"""
Intent handlers for Mahavihara.

Each function handles one type of user intent.
All handlers have the same signature:
    async def handle_X(user, state, message, image_url) -> (response, new_state)
"""

from typing import Tuple, Optional

from app.db.models import User
from app.db.queries import (
    update_user,
    create_mistake,
    get_next_due_mistake,
    get_pending_mistakes_count,
    get_user_stats,
    save_drill_attempt,
    update_mistake_after_drill,
    get_next_unused_drill,
    mark_drill_used,
    set_user_inactive,
    update_user_streak,
)
from app.services.llm import (
    classify_mistake,
    generate_drill_question,
    generate_correct_response,
    generate_wrong_response,
    generate_welcome_message,
    extract_question_from_image,
)
from app.agent.state import (
    ConversationState,
    DrillState,
    has_active_drill,
    clear_drill,
    update_drill_attempts,
    increment_hints,
)


# ==================== GREETING ====================

async def handle_greeting(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "Hi", "Hello", "Hey"

    Welcome new users or greet returning ones.
    """
    is_new = state.get("phase") == "onboarding" or not user.name

    response = await generate_welcome_message(is_new_user=is_new, name=user.name)

    if is_new:
        state["phase"] = "onboarding"
    else:
        state["phase"] = "idle"

    return response, state


# ==================== ONBOARDING (Name Collection) ====================

async def handle_onboarding(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle name collection during onboarding.

    Called when phase="onboarding" and user sends a message that's likely their name.
    """
    # Extract name (assume the message IS the name if it's short)
    name = message.strip().title()

    if len(name) < 2 or len(name) > 50:
        return "What's your name? Just tell me!", state

    # Save name to database
    await update_user(user.id, {"name": name})

    # Update state
    state["user_name"] = name
    state["phase"] = "idle"

    # Get pending mistakes count
    pending = await get_pending_mistakes_count(user.id)

    if pending > 0:
        response = (
            f"Welcome {name}! 💪\n\n"
            f"You have {pending} mistakes waiting to be fixed.\n\n"
            f"Reply *GO* to start drilling, or tell me about a new mistake!"
        )
    else:
        response = (
            f"Welcome {name}!\n\n"
            f"I'm Mahavihara - your strict JEE guru.\n\n"
            f"Tell me about a mistake you made in your last test or practice. "
            f"I'll make sure you never repeat it! 🔥"
        )

    return response, state


# ==================== REPORT MISTAKE ====================

async def handle_report_mistake(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "I confused torque with force", "Got Q17 wrong", [sends image]

    Capture and classify the mistake, create drill questions.
    """
    mistake_text = message

    # If image was sent, extract question from it
    if image_url:
        extraction = await extract_question_from_image(image_url)

        if not extraction.get("readable"):
            return (
                "Couldn't read that image clearly.\n\n"
                "Can you send a clearer photo or type out what went wrong?"
            ), state

        # Use extracted question as mistake context
        mistake_text = f"Question: {extraction.get('question_text', '')}\n"
        mistake_text += f"Topic: {extraction.get('topic', 'unknown')}\n"
        mistake_text += f"Student marked: {extraction.get('student_marked', '?')}, "
        mistake_text += f"Correct: {extraction.get('correct_answer', '?')}"

    # Classify the mistake using LLM
    classification = await classify_mistake(mistake_text)

    # Save to database
    mistake = await create_mistake(
        user_id=user.id,
        subject=classification.topic.split("/")[0] if "/" in classification.topic else "physics",
        chapter=classification.topic,
        topic=classification.subtopic,
        custom_mistake_text=mistake_text,
        classification=classification
    )

    # Update state
    state["phase"] = "idle"

    # Build response
    response = (
        f"📝 Got it! Logged your mistake:\n\n"
        f"*Topic:* {classification.topic} → {classification.subtopic}\n"
        f"*Type:* {classification.mistake_type.value}\n"
        f"*Issue:* {classification.misconception}\n\n"
        f"I'll drill you on this until it's fixed! 💪\n\n"
        f"Reply *GO* to start practicing now, or tell me another mistake."
    )

    return response, state


# ==================== START DRILL ====================

async def handle_start_drill(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "GO", "Start", "Practice", "Quiz me"

    Find next due mistake and present a drill question.
    """
    # Get next mistake due for review
    mistake = await get_next_due_mistake(user.id)

    if not mistake:
        pending = await get_pending_mistakes_count(user.id)
        if pending == 0:
            return (
                "🎉 No mistakes to drill!\n\n"
                "Tell me about a mistake from your recent test or practice."
            ), state
        else:
            return (
                f"You have {pending} mistakes, but none are due for review yet.\n\n"
                "They'll come back based on spaced repetition. "
                "Meanwhile, tell me about new mistakes!"
            ), state

    # Try to get pre-generated drill first
    drill = await get_next_unused_drill(mistake.id)

    if drill and drill.generated_question_text:
        # Use pre-generated drill
        question_data = {
            "question": drill.generated_question_text,
            "option_a": drill.generated_option_a,
            "option_b": drill.generated_option_b,
            "option_c": drill.generated_option_c,
            "option_d": drill.generated_option_d,
            "correct_option": drill.generated_correct_option,
            "solution": drill.generated_solution,
            "hint_1": drill.generated_hint_1,
            "hint_2": drill.generated_hint_2,
            "hint_3": drill.generated_hint_3,
        }
        await mark_drill_used(drill.id)
        drill_id = drill.id
    else:
        # Generate new question with LLM
        question_data = await generate_drill_question(
            misconception=mistake.misconception or mistake.custom_mistake_text or "general",
            topic=mistake.topic or mistake.chapter or "physics",
            difficulty=2
        )
        drill_id = None

    # Update state with active drill
    state["phase"] = "drilling"
    state["active_drill"] = DrillState(
        mistake_id=mistake.id,
        drill_id=drill_id,
        question_text=question_data.get("question", ""),
        options={
            "A": question_data.get("option_a", ""),
            "B": question_data.get("option_b", ""),
            "C": question_data.get("option_c", ""),
            "D": question_data.get("option_d", ""),
        },
        correct_option=question_data.get("correct_option", "A"),
        solution=question_data.get("solution", ""),
        hint_1=question_data.get("hint_1"),
        hint_2=question_data.get("hint_2"),
        hint_3=question_data.get("hint_3"),
        attempts=0,
        hints_given=0
    )

    # Format question for WhatsApp
    q = state["active_drill"]
    response = (
        f"*Drilling:* {mistake.topic or mistake.chapter}\n"
        f"_{mistake.misconception or 'Fix this mistake!'}_\n\n"
        f"*Question:*\n{q['question_text']}\n\n"
        f"*A)* {q['options']['A']}\n"
        f"*B)* {q['options']['B']}\n"
        f"*C)* {q['options']['C']}\n"
        f"*D)* {q['options']['D']}\n\n"
        f"Reply with *A*, *B*, *C*, or *D*"
    )

    return response, state


# ==================== ANSWER DRILL ====================

async def handle_answer_drill(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "A", "B", "C", "D" (when drill is active)

    Check answer, give feedback, update mastery.
    """
    if not has_active_drill(state):
        return "No active question. Reply *GO* to start drilling!", state

    drill = state["active_drill"]

    # Extract answer (first letter, uppercase)
    answer = message.strip().upper()
    if answer.startswith("OPTION"):
        answer = answer.replace("OPTION", "").strip()
    answer = answer[0] if answer else ""

    if answer not in ["A", "B", "C", "D"]:
        return "Please reply with *A*, *B*, *C*, or *D*", state

    correct_answer = drill["correct_option"]
    is_correct = (answer == correct_answer)

    # Update attempts
    state = update_drill_attempts(state)
    attempts = drill["attempts"] + 1  # +1 because we just incremented

    # Save attempt to database
    await save_drill_attempt(
        user_id=user.id,
        mistake_id=drill["mistake_id"],
        student_answer=answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
        drill_id=drill.get("drill_id"),
        hints_used=drill["hints_given"]
    )

    # Update mistake mastery
    updated_mistake = await update_mistake_after_drill(
        mistake_id=drill["mistake_id"],
        is_correct=is_correct
    )

    if is_correct:
        # CORRECT!
        state["correct_today"] = state.get("correct_today", 0) + 1
        state["questions_today"] = state.get("questions_today", 0) + 1

        # Update streak
        new_streak = await update_user_streak(user.id, increment=True)

        # Generate celebration response
        response = await generate_correct_response(
            streak=new_streak,
            questions_today=state["questions_today"],
            drill_count=updated_mistake.times_drilled,
            is_mastered=updated_mistake.is_mastered
        )

        # Clear drill, check for more
        state = clear_drill(state)

        pending = await get_pending_mistakes_count(user.id)
        if pending > 0:
            response += f"\n\n{pending} more mistakes waiting. Reply *GO* to continue!"
        else:
            response += "\n\n🏆 All caught up! Tell me about new mistakes."

    else:
        # WRONG
        hints_given = drill["hints_given"]

        if attempts >= 3:
            # After 3 attempts, show solution and move on
            response = await generate_wrong_response(
                student_answer=answer,
                correct_answer=correct_answer,
                attempt_number=attempts,
                hints_given=hints_given,
                solution=drill["solution"]
            )
            response += f"\n\n*Solution:* {drill['solution']}"
            response += "\n\nWe'll revisit this tomorrow. Reply *GO* to continue."

            state = clear_drill(state)

        else:
            # Give hint and let them try again
            hint_key = f"hint_{hints_given + 1}"
            hint_text = drill.get(hint_key)

            response = await generate_wrong_response(
                student_answer=answer,
                correct_answer=correct_answer,
                attempt_number=attempts,
                hints_given=hints_given,
                hint_text=hint_text
            )

            state = increment_hints(state)

    return response, state


# ==================== CHECK STATS ====================

async def handle_stats(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "stats", "progress", "how am I doing?"

    Show user's streak, mastery, and progress.
    """
    stats = await get_user_stats(user.id)

    name = user.name or "there"

    response = (
        f"📊 *{name}'s Progress*\n\n"
        f"🔥 *Streak:* {stats.streak} days "
        f"(Best: {stats.longest_streak})\n\n"
        f"📝 *Mistakes:*\n"
        f"   • Total tracked: {stats.total_mistakes}\n"
        f"   • Mastered: {stats.mastered_mistakes} ✅\n"
        f"   • Pending: {stats.pending_mistakes}\n\n"
        f"📅 *Today:*\n"
        f"   • Questions: {stats.questions_today}\n"
        f"   • Correct: {stats.correct_today}\n"
        f"   • Accuracy: {stats.accuracy_today:.0f}%\n\n"
    )

    if stats.pending_mistakes > 0:
        response += f"Reply *GO* to drill your {stats.pending_mistakes} pending mistakes!"
    else:
        response += "🎉 All caught up! Tell me about new mistakes."

    return response, state


# ==================== HELP ====================

async def handle_help(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "help", "?", "commands"

    Show available commands.
    """
    response = (
        "*Mahavihara Commands*\n\n"
        "*GO* - Start drilling your mistakes\n"
        "*STATS* - See your progress & streak\n"
        "*STOP* - Unsubscribe from messages\n\n"
        "*To report a mistake:*\n"
        "Just tell me! Examples:\n"
        "• 'I confused torque with force'\n"
        "• 'Made a sign error in kinematics'\n"
        "• Send a photo of the question\n\n"
        "*To answer:*\n"
        "Reply with A, B, C, or D\n\n"
        "Questions? Just ask! 💪"
    )

    return response, state


# ==================== STOP (Unsubscribe) ====================

async def handle_stop(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: "stop", "unsubscribe", "cancel"

    CRITICAL: Must honor this immediately per WhatsApp policy.
    """
    await set_user_inactive(user.id)

    state["phase"] = "stopped"

    response = (
        "You've been unsubscribed from Mahavihara.\n\n"
        "I won't send you any more messages.\n"
        "Reply *START* anytime to resume."
    )

    return response, state


# ==================== CHITCHAT / FALLBACK ====================

async def handle_chitchat(
    user: User,
    state: ConversationState,
    message: str,
    image_url: Optional[str] = None
) -> Tuple[str, ConversationState]:
    """
    Handle: Anything that doesn't match other intents.

    Gently redirect to core functionality.
    """
    name = user.name or "there"
    pending = await get_pending_mistakes_count(user.id)

    if pending > 0:
        response = (
            f"Hey {name}, let's focus! 📚\n\n"
            f"You have {pending} mistakes waiting.\n"
            f"Reply *GO* to practice, or tell me about a new mistake."
        )
    else:
        response = (
            f"Hey {name}! I'm here to fix your JEE mistakes.\n\n"
            f"Tell me about a mistake you made recently, "
            f"and I'll make sure you never repeat it!"
        )

    return response, state
