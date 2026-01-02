"""
APScheduler setup for Mahavihara.

Runs background jobs:
- Daily nudges (configurable time, default 6 PM IST)
- Streak warnings (9 PM for users with streaks)
- Pre-generate drill questions (background)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz

from app.config import settings


# Global scheduler instance
scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler instance."""
    global scheduler

    if scheduler is None:
        scheduler = AsyncIOScheduler(
            timezone=pytz.timezone("Asia/Kolkata")  # IST
        )

    return scheduler


async def daily_nudge_job():
    """Job: Send daily nudges to inactive users."""
    print(f"⏰ Running daily nudge job at {datetime.now()}")

    from app.scheduler.nudger import send_nudges
    await send_nudges()


async def streak_warning_job():
    """Job: Send streak warnings to users at risk."""
    print(f"⏰ Running streak warning job at {datetime.now()}")

    from app.db.queries import get_users_for_nudge
    from app.scheduler.nudger import send_streak_warning

    users = await get_users_for_nudge()

    # Filter to users with streaks
    streak_users = [u for u in users if u.current_streak >= 3]

    for user in streak_users:
        await send_streak_warning(user)


async def pregeneate_drills_job():
    """Job: Pre-generate drill questions for new mistakes."""
    print(f"⏰ Running drill pre-generation at {datetime.now()}")

    # TODO: Implement pre-generation logic
    # This would find mistakes without pre-generated drills
    # and generate them in the background
    pass


def start_scheduler():
    """
    Start the scheduler with all jobs.

    Called on application startup.
    """
    sched = get_scheduler()

    if sched.running:
        print("⚠️ Scheduler already running")
        return

    # Parse nudge time from settings (format: "HH:MM")
    nudge_time = settings.DEFAULT_NUDGE_TIME.split(":")
    nudge_hour = int(nudge_time[0])
    nudge_minute = int(nudge_time[1]) if len(nudge_time) > 1 else 0

    # Job 1: Daily nudges at configured time (default 6 PM IST)
    sched.add_job(
        daily_nudge_job,
        CronTrigger(hour=nudge_hour, minute=nudge_minute),
        id="daily_nudge",
        name="Daily Nudge",
        replace_existing=True
    )
    print(f"   📅 Daily nudge scheduled for {nudge_hour:02d}:{nudge_minute:02d} IST")

    # Job 2: Streak warnings at 9 PM IST
    sched.add_job(
        streak_warning_job,
        CronTrigger(hour=21, minute=0),
        id="streak_warning",
        name="Streak Warning",
        replace_existing=True
    )
    print(f"   📅 Streak warnings scheduled for 21:00 IST")

    # Job 3: Pre-generate drills every 4 hours
    sched.add_job(
        pregeneate_drills_job,
        CronTrigger(hour="*/4"),
        id="pregen_drills",
        name="Pre-generate Drills",
        replace_existing=True
    )
    print(f"   📅 Drill pre-generation scheduled every 4 hours")

    # Start the scheduler
    sched.start()
    print("✅ Scheduler started!")


def stop_scheduler():
    """
    Stop the scheduler gracefully.

    Called on application shutdown.
    """
    global scheduler

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        print("👋 Scheduler stopped")


def get_scheduled_jobs() -> list:
    """Get list of scheduled jobs (for admin endpoint)."""
    sched = get_scheduler()

    jobs = []
    for job in sched.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })

    return jobs
