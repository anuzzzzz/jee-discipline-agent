"""
Admin endpoints for Mahavihara.

Protected by API key. Used for:
- Manual nudge triggers
- User management
- Debugging
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime

from app.config import settings
from app.db.queries import (
    get_user_by_phone,
    get_user_stats,
    get_question_count,
    get_users_for_nudge,
)
from app.services.whatsapp import WhatsAppService
from app.scheduler.scheduler import get_scheduled_jobs

router = APIRouter()


def verify_admin_key(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Verify admin API key."""
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.get("/admin/stats")
async def admin_stats(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get overall system statistics."""
    verify_admin_key(api_key)

    from app.db.supabase import get_supabase_client
    client = get_supabase_client()

    # Count users
    users_result = client.table("users").select("id", count="exact").execute()
    active_result = client.table("users").select("id", count="exact").eq("is_active", True).execute()

    # Count mistakes
    mistakes_result = client.table("student_mistakes").select("id", count="exact").execute()
    mastered_result = client.table("student_mistakes").select("id", count="exact").eq("is_mastered", True).execute()

    # Count questions
    question_count = await get_question_count()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "users": {
            "total": users_result.count or 0,
            "active": active_result.count or 0
        },
        "mistakes": {
            "total": mistakes_result.count or 0,
            "mastered": mastered_result.count or 0
        },
        "questions": question_count
    }


@router.get("/admin/user/{phone}")
async def admin_get_user(
    phone: str,
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Get user details by phone number."""
    verify_admin_key(api_key)

    user = await get_user_by_phone(phone)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = await get_user_stats(user.id)

    return {
        "user": user.model_dump(),
        "stats": stats.model_dump()
    }


@router.post("/admin/nudge/trigger")
async def trigger_nudges(
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Manually trigger nudges for all eligible users.

    Useful for testing or if scheduler fails.
    """
    verify_admin_key(api_key)

    users = await get_users_for_nudge()

    sent = 0
    failed = 0

    for user in users:
        try:
            from app.services.llm import generate_nudge_message
            from app.db.queries import get_pending_mistakes_count

            pending = await get_pending_mistakes_count(user.id)

            # Calculate hours since active
            if user.last_active_at:
                hours = (datetime.utcnow() - user.last_active_at).total_seconds() / 3600
            else:
                hours = 999

            message = await generate_nudge_message(
                name=user.name,
                streak=user.current_streak,
                pending_count=pending,
                hours_since_active=hours
            )

            await WhatsAppService.send_message(
                phone_number=user.phone_number,
                message=message,
                user_last_message_at=user.last_message_at
            )

            sent += 1

        except Exception as e:
            print(f"Failed to nudge {user.phone_number}: {e}")
            failed += 1

    return {
        "status": "completed",
        "users_eligible": len(users),
        "sent": sent,
        "failed": failed
    }


@router.post("/admin/message/send")
async def send_manual_message(
    phone: str,
    message: str,
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Send a manual message to a user."""
    verify_admin_key(api_key)

    result = await WhatsAppService.send_message(
        phone_number=phone,
        message=message
    )

    return {
        "status": "sent",
        "phone": phone,
        "message": message[:50] + "..." if len(message) > 50 else message,
        "gupshup_response": result
    }


@router.get("/admin/scheduler/jobs")
async def get_jobs(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Get scheduled jobs and their next run times."""
    verify_admin_key(api_key)

    jobs = get_scheduled_jobs()

    return {
        "scheduler": "running" if jobs else "stopped",
        "jobs": jobs
    }


@router.post("/admin/scheduler/nudge-now")
async def run_nudge_now(api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """Manually trigger nudge run (for testing)."""
    verify_admin_key(api_key)

    from app.scheduler.nudger import send_nudges

    stats = await send_nudges()

    return {
        "status": "completed",
        "stats": stats
    }
