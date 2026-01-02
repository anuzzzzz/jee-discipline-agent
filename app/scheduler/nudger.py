"""
Nudge Service for Mahavihara.

Sends daily reminders to students who haven't practiced.

Nudge Strategy:
- Only nudge active users (is_active=True)
- Only nudge if they haven't practiced today
- Respect 24-hour WhatsApp window (use templates if needed)
- Personalize based on streak and pending mistakes
"""

from datetime import datetime

from app.db.queries import (
    get_users_for_nudge,
    get_pending_mistakes_count,
    log_nudge,
)
from app.db.models import User
from app.services.llm import generate_nudge_message
from app.services.whatsapp import (
    WhatsAppService,
    can_send_freeform,
)


async def send_nudge_to_user(user: User) -> bool:
    """
    Send a nudge to a single user.

    Args:
        user: User to nudge

    Returns:
        True if nudge sent successfully
    """
    try:
        # Get user's pending mistakes
        pending = await get_pending_mistakes_count(user.id)

        if pending == 0:
            print(f"   {user.phone_number}: No pending mistakes, skipping")
            return False

        # Calculate hours since last active
        if user.last_active_at:
            hours_since = (datetime.utcnow() - user.last_active_at).total_seconds() / 3600
        else:
            hours_since = 999  # Never active

        # Check if within 24-hour window
        if can_send_freeform(user.last_message_at):
            # Generate personalized nudge
            message = await generate_nudge_message(
                name=user.name,
                streak=user.current_streak,
                pending_count=pending,
                hours_since_active=hours_since
            )

            # Send free-form message
            result = await WhatsAppService.send_message(
                phone_number=user.phone_number,
                message=message,
                user_last_message_at=user.last_message_at
            )

            nudge_type = "freeform"

        else:
            # Outside 24-hour window - use template
            # Template variables: {{1}}=name, {{2}}=streak, {{3}}=pending
            try:
                result = await WhatsAppService.send_template_message(
                    phone_number=user.phone_number,
                    template_key="daily_nudge",
                    variables=[
                        user.name or "there",
                        str(user.current_streak),
                        str(pending)
                    ]
                )
                message = f"[Template: daily_nudge] name={user.name}, streak={user.current_streak}, pending={pending}"
                nudge_type = "template"

            except Exception as e:
                print(f"   Template failed for {user.phone_number}: {e}")
                print(f"   User outside 24hr window, can't send freeform")
                return False

        # Log the nudge
        await log_nudge(
            user_id=user.id,
            nudge_type=nudge_type,
            message_sent=message[:500]  # Truncate for DB
        )

        print(f"   {user.phone_number}: Nudged ({nudge_type})")
        return True

    except Exception as e:
        print(f"   {user.phone_number}: Error - {e}")
        return False


async def send_nudges() -> dict:
    """
    Send nudges to all eligible users.

    Called by scheduler at configured time (default 6 PM).

    Returns:
        Stats dict with sent/failed counts
    """
    print(f"\n{'='*50}")
    print(f"NUDGE RUN - {datetime.utcnow().isoformat()}")
    print(f"{'='*50}")

    # Get eligible users
    users = await get_users_for_nudge()

    print(f"Found {len(users)} users to nudge\n")

    stats = {
        "eligible": len(users),
        "sent": 0,
        "skipped": 0,
        "failed": 0
    }

    for user in users:
        success = await send_nudge_to_user(user)

        if success:
            stats["sent"] += 1
        else:
            stats["skipped"] += 1

    print(f"\n{'='*50}")
    print(f"NUDGE RUN COMPLETE")
    print(f"   Eligible: {stats['eligible']}")
    print(f"   Sent: {stats['sent']}")
    print(f"   Skipped: {stats['skipped']}")
    print(f"{'='*50}\n")

    return stats


async def send_streak_warning(user: User) -> bool:
    """
    Send urgent warning when streak is about to break.

    Called when user has high streak but hasn't practiced today
    and it's getting late (e.g., 9 PM).
    """
    if user.current_streak < 3:
        return False  # Only warn for meaningful streaks

    message = (
        f"*STREAK ALERT*\n\n"
        f"{user.name or 'Hey'}, your {user.current_streak}-day streak "
        f"is about to break!\n\n"
        f"You have until midnight. Reply *GO* now!"
    )

    try:
        if can_send_freeform(user.last_message_at):
            await WhatsAppService.send_message(
                phone_number=user.phone_number,
                message=message,
                user_last_message_at=user.last_message_at
            )

            await log_nudge(
                user_id=user.id,
                nudge_type="streak_warning",
                message_sent=message
            )

            return True

    except Exception as e:
        print(f"Streak warning failed for {user.phone_number}: {e}")

    return False


async def send_milestone_celebration(user: User, milestone: int) -> bool:
    """
    Celebrate streak milestones (7 days, 30 days, etc.)

    Called after a drill when user hits a milestone.
    """
    messages = {
        7: "*1 WEEK STREAK!*\n\nWell done {name}! 7 days of consistency. You're building real discipline!",
        14: "*2 WEEK STREAK!*\n\n{name}, 14 days! Most students give up by now. You're different.",
        30: "*30 DAY STREAK!*\n\n{name}, ONE MONTH! You're in the top 5% of disciplined JEE aspirants!",
        60: "*60 DAY STREAK!*\n\n{name}, 2 months of daily practice! Your consistency is legendary.",
        100: "*100 DAY STREAK!*\n\n{name}, HUNDRED DAYS! You've proven you have what it takes for IIT!",
    }

    if milestone not in messages:
        return False

    message = messages[milestone].format(name=user.name or "Champion")

    try:
        await WhatsAppService.send_message(
            phone_number=user.phone_number,
            message=message
        )

        await log_nudge(
            user_id=user.id,
            nudge_type="milestone",
            message_sent=message
        )

        return True

    except Exception as e:
        print(f"Milestone celebration failed: {e}")
        return False
