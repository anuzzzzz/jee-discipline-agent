#!/usr/bin/env python3
"""
Phase 6 Test - Scheduler and Nudges

Tests the nudge system locally.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_imports():
    """Test that scheduler modules import."""
    print("Testing imports...")

    try:
        from app.scheduler import send_nudges, start_scheduler, stop_scheduler
        print("  ✅ Scheduler imports OK")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False


async def test_scheduler_setup():
    """Test scheduler can be configured."""
    print("\nTesting scheduler setup...")

    try:
        from app.scheduler.scheduler import get_scheduler, get_scheduled_jobs

        sched = get_scheduler()
        print(f"  ✅ Scheduler created: {type(sched).__name__}")

        # Don't start it, just verify configuration
        return True

    except Exception as e:
        print(f"  ❌ Scheduler setup failed: {e}")
        return False


async def test_nudge_query():
    """Test that we can query users for nudging."""
    print("\nTesting nudge user query...")

    try:
        from app.db.queries import get_users_for_nudge

        users = await get_users_for_nudge()
        print(f"  ✅ Found {len(users)} users eligible for nudge")

        for user in users[:3]:  # Show first 3
            print(f"     - {user.phone_number}: streak={user.current_streak}")

        return True

    except Exception as e:
        print(f"  ❌ Query failed: {e}")
        return False


async def test_nudge_message_generation():
    """Test nudge message generation."""
    print("\nTesting nudge message generation...")

    try:
        from app.services.llm import generate_nudge_message

        message = await generate_nudge_message(
            name="Test Student",
            streak=5,
            pending_count=3,
            hours_since_active=26
        )

        print(f"  ✅ Generated nudge message:")
        print(f"     {message[:100]}...")

        return True

    except Exception as e:
        print(f"  ❌ Message generation failed: {e}")
        return False


async def main():
    print("=" * 50)
    print("PHASE 6 TEST - Scheduler & Nudges")
    print("=" * 50)

    results = []

    results.append(("Imports", await test_imports()))
    results.append(("Scheduler Setup", await test_scheduler_setup()))
    results.append(("Nudge Query", await test_nudge_query()))
    results.append(("Message Generation", await test_nudge_message_generation()))

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 PHASE 6 COMPLETE!")
        print("\nTo test nudges manually:")
        print('  curl -X POST http://localhost:8000/api/admin/scheduler/nudge-now \\')
        print('       -H "X-API-Key: admin-secret-key"')
        print("\nScheduler runs automatically when DEBUG=False")
    else:
        print("⚠️ Some tests failed")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
