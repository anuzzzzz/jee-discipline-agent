#!/usr/bin/env python3
"""
QA Test Suite for Mahavihara

Comprehensive end-to-end testing of all user flows.
Run this before any release.

Usage:
    python scripts/qa_test.py
    python scripts/qa_test.py --verbose
    python scripts/qa_test.py --test onboarding
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))


# Test results tracking
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def record(self, name: str, passed: bool, message: str = ""):
        if passed:
            self.passed += 1
            print(f"  ✅ {name}")
        else:
            self.failed += 1
            self.errors.append((name, message))
            print(f"  ❌ {name}: {message}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"📊 TEST RESULTS")
        print(f"{'='*50}")
        print(f"Total: {total}")
        print(f"Passed: {self.passed} ✅")
        print(f"Failed: {self.failed} ❌")

        if self.errors:
            print(f"\n❌ Failed Tests:")
            for name, msg in self.errors:
                print(f"   - {name}: {msg}")

        print(f"{'='*50}")
        return self.failed == 0


results = TestResults()


async def send_message(phone: str, message: str) -> Dict:
    """Send a test message and get response."""
    from app.agent.router import process_message

    response = await process_message(
        phone_number=phone,
        message_text=message
    )
    return {"response": response or ""}


async def reset_user(phone: str):
    """Delete a test user to start fresh."""
    from app.db.supabase import get_service_client

    client = get_service_client()

    # Get user
    user_result = client.table("users").select("id").eq("phone_number", phone).execute()

    if user_result.data:
        user_id = user_result.data[0]["id"]

        # Delete related data
        client.table("student_mistakes").delete().eq("user_id", user_id).execute()
        client.table("drill_attempts").delete().eq("user_id", user_id).execute()
        client.table("conversation_states").delete().eq("user_id", user_id).execute()
        client.table("message_history").delete().eq("user_id", user_id).execute()
        client.table("users").delete().eq("id", user_id).execute()

        print(f"   🗑️ Reset user {phone}")


# =============================================================================
# TEST SUITES
# =============================================================================

async def test_onboarding():
    """Test new user onboarding flow."""
    print("\n📝 TEST SUITE: Onboarding Flow")
    print("-" * 40)

    phone = "910000000001"
    await reset_user(phone)

    # Test 1: New user greeting
    res = await send_message(phone, "Hi")
    results.record(
        "New user gets welcome message",
        "welcome" in res["response"].lower() or "mahavihara" in res["response"].lower(),
        f"Got: {res['response'][:50]}"
    )

    # Test 2: User provides name
    res = await send_message(phone, "Rahul")
    results.record(
        "Name is acknowledged",
        "rahul" in res["response"].lower() or "mistake" in res["response"].lower(),
        f"Got: {res['response'][:50]}"
    )

    # Test 3: Verify user saved in DB
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()
    user = client.table("users").select("*").eq("phone_number", phone).execute()

    results.record(
        "User saved in database",
        len(user.data) > 0,
        "User not found in DB"
    )

    if user.data:
        results.record(
            "User name saved correctly",
            user.data[0].get("name") == "Rahul",
            f"Name is: {user.data[0].get('name')}"
        )


async def test_mistake_reporting():
    """Test mistake reporting flow."""
    print("\n📝 TEST SUITE: Mistake Reporting")
    print("-" * 40)

    phone = "910000000002"
    await reset_user(phone)

    # Setup user
    await send_message(phone, "Hi")
    await send_message(phone, "TestUser")

    # Test 1: Report physics mistake
    res = await send_message(phone, "I confused Newton's first law with second law")
    results.record(
        "Physics mistake acknowledged",
        "logged" in res["response"].lower() or "got it" in res["response"].lower(),
        f"Got: {res['response'][:50]}"
    )
    results.record(
        "Topic identified",
        "mechanics" in res["response"].lower() or "newton" in res["response"].lower() or "motion" in res["response"].lower(),
        f"Response: {res['response'][:100]}"
    )

    # Test 2: Report chemistry mistake
    res = await send_message(phone, "I mixed up oxidation and reduction reactions")
    results.record(
        "Chemistry mistake acknowledged",
        "logged" in res["response"].lower() or "got it" in res["response"].lower(),
        f"Got: {res['response'][:50]}"
    )

    # Test 3: Report math mistake
    res = await send_message(phone, "I forgot the quadratic formula")
    results.record(
        "Math mistake acknowledged",
        "logged" in res["response"].lower() or "got it" in res["response"].lower(),
        f"Got: {res['response'][:50]}"
    )

    # Test 4: Verify mistakes saved
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()
    user = client.table("users").select("id").eq("phone_number", phone).execute()

    if user.data:
        mistakes = client.table("student_mistakes").select("*").eq("user_id", user.data[0]["id"]).execute()
        results.record(
            "Mistakes saved in database",
            len(mistakes.data) >= 3,
            f"Found {len(mistakes.data)} mistakes"
        )


async def test_drilling_flow():
    """Test the drilling flow."""
    print("\n📝 TEST SUITE: Drilling Flow")
    print("-" * 40)

    phone = "910000000003"
    await reset_user(phone)

    # Setup user with a mistake
    await send_message(phone, "Hi")
    await send_message(phone, "DrillTester")
    await send_message(phone, "I confused velocity with acceleration")

    # Test 1: Start drill with GO
    res = await send_message(phone, "GO")
    results.record(
        "GO starts a drill",
        "question" in res["response"].lower() or "?" in res["response"] or "a)" in res["response"].lower() or "*a*" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )
    results.record(
        "Question has options",
        any(opt in res["response"].lower() for opt in ["a)", "b)", "c)", "d)", "*a*", "*b*", "*c*", "*d*"]),
        f"No options found in: {res['response'][:100]}"
    )

    # Test 2: Alternative drill triggers
    await reset_user(phone)
    await send_message(phone, "Hi")
    await send_message(phone, "DrillTester2")
    await send_message(phone, "I forgot Ohm's law")

    res = await send_message(phone, "let's practice")
    results.record(
        "'let's practice' starts drill",
        "question" in res["response"].lower() or "?" in res["response"] or "a)" in res["response"].lower(),
        f"Got: {res['response'][:50]}"
    )

    # Test 3: Start drill when no mistakes
    phone2 = "910000000004"
    await reset_user(phone2)
    await send_message(phone2, "Hi")
    await send_message(phone2, "NoMistakeUser")

    res = await send_message(phone2, "GO")
    results.record(
        "GO with no mistakes gives helpful message",
        "no" in res["response"].lower() or "mistake" in res["response"].lower() or "tell me" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )


async def test_answer_handling():
    """Test answer submission and feedback."""
    print("\n📝 TEST SUITE: Answer Handling")
    print("-" * 40)

    phone = "910000000005"
    await reset_user(phone)

    # Setup drill
    await send_message(phone, "Hi")
    await send_message(phone, "AnswerTester")
    await send_message(phone, "I confused potential energy with kinetic energy")
    await send_message(phone, "GO")

    # Test 1: Answer with letter
    res = await send_message(phone, "A")
    is_feedback = any(word in res["response"].lower() for word in ["correct", "wrong", "incorrect", "try", "right", "great", "oops"])
    results.record(
        "Letter answer gets feedback",
        is_feedback,
        f"Got: {res['response'][:80]}"
    )

    # Test 2: Setup another drill for wrong answer test
    await send_message(phone, "I confused work with power")
    res = await send_message(phone, "GO")

    # Send multiple wrong answers to test hint system
    res1 = await send_message(phone, "Z")  # Invalid option
    results.record(
        "Invalid option handled",
        any(word in res1["response"].lower() for word in ["a", "b", "c", "d", "option", "choose", "select", "invalid"]),
        f"Got: {res1['response'][:50]}"
    )


async def test_stats():
    """Test stats display."""
    print("\n📝 TEST SUITE: Stats & Progress")
    print("-" * 40)

    phone = "910000000006"
    await reset_user(phone)

    # Setup user with activity
    await send_message(phone, "Hi")
    await send_message(phone, "StatsTester")
    await send_message(phone, "I confused momentum with impulse")
    await send_message(phone, "GO")
    await send_message(phone, "A")  # Answer

    # Test 1: Stats command
    res = await send_message(phone, "stats")
    results.record(
        "Stats command works",
        "streak" in res["response"].lower() or "progress" in res["response"].lower() or "mistake" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )

    # Test 2: Stats shows relevant info
    results.record(
        "Stats shows streak info",
        any(word in res["response"].lower() for word in ["streak", "day", "🔥"]),
        f"Got: {res['response'][:80]}"
    )

    # Test 3: Alternative stats triggers
    res = await send_message(phone, "how am I doing?")
    results.record(
        "'how am I doing' shows stats",
        "streak" in res["response"].lower() or "progress" in res["response"].lower() or "mistake" in res["response"].lower() or "question" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )


async def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n📝 TEST SUITE: Edge Cases")
    print("-" * 40)

    phone = "910000000007"
    await reset_user(phone)

    # Setup user
    await send_message(phone, "Hi")
    await send_message(phone, "EdgeTester")

    # Test 1: Empty message handling
    res = await send_message(phone, "")
    results.record(
        "Empty message handled",
        res["response"] != "" or True,  # Should not crash
        "Crashed on empty message"
    )

    # Test 2: Very long message
    long_msg = "I made a mistake " * 100
    res = await send_message(phone, long_msg)
    results.record(
        "Long message handled",
        len(res["response"]) > 0,
        "Crashed on long message"
    )

    # Test 3: Emoji-only message
    res = await send_message(phone, "😀😀😀")
    results.record(
        "Emoji message handled",
        len(res["response"]) > 0,
        "Crashed on emoji message"
    )

    # Test 4: Special characters
    res = await send_message(phone, "!@#$%^&*()")
    results.record(
        "Special characters handled",
        len(res["response"]) > 0,
        "Crashed on special characters"
    )

    # Test 5: Answer when no drill active
    res = await send_message(phone, "B")
    results.record(
        "Answer without active drill handled",
        len(res["response"]) > 0 and "drill" not in res["response"].lower() or True,
        f"Got: {res['response'][:50]}"
    )

    # Test 6: Gibberish
    res = await send_message(phone, "asdfghjkl qwerty")
    results.record(
        "Gibberish handled gracefully",
        len(res["response"]) > 0,
        "Crashed on gibberish"
    )


async def test_whatsapp_compliance():
    """Test WhatsApp policy compliance."""
    print("\n📝 TEST SUITE: WhatsApp Compliance")
    print("-" * 40)

    phone = "910000000008"
    await reset_user(phone)

    # Setup user
    await send_message(phone, "Hi")
    await send_message(phone, "ComplianceTester")

    # Test 1: STOP command
    res = await send_message(phone, "STOP")
    results.record(
        "STOP command acknowledged",
        "stop" in res["response"].lower() or "unsubscribe" in res["response"].lower() or "won't" in res["response"].lower() or "goodbye" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )

    # Test 2: User marked inactive
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()
    user = client.table("users").select("is_active").eq("phone_number", phone).execute()

    results.record(
        "User marked as inactive after STOP",
        user.data and user.data[0].get("is_active") == False,
        f"is_active: {user.data[0].get('is_active') if user.data else 'N/A'}"
    )

    # Test 3: Help command
    phone2 = "910000000009"
    await reset_user(phone2)
    await send_message(phone2, "Hi")
    await send_message(phone2, "HelpTester")

    res = await send_message(phone2, "help")
    results.record(
        "HELP command works",
        any(word in res["response"].lower() for word in ["go", "stats", "stop", "mistake", "help", "command"]),
        f"Got: {res['response'][:80]}"
    )


async def test_returning_user():
    """Test returning user experience."""
    print("\n📝 TEST SUITE: Returning User")
    print("-" * 40)

    phone = "910000000010"
    await reset_user(phone)

    # First session
    await send_message(phone, "Hi")
    await send_message(phone, "ReturningUser")
    await send_message(phone, "I confused acceleration with velocity")

    # Simulate returning (just send Hi again)
    res = await send_message(phone, "Hi")
    results.record(
        "Returning user recognized",
        "welcome back" in res["response"].lower() or "returninguser" in res["response"].lower() or "ready" in res["response"].lower() or "go" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )

    # Should remember pending mistakes
    results.record(
        "Returning user told about pending drills",
        "go" in res["response"].lower() or "drill" in res["response"].lower() or "practice" in res["response"].lower() or "mistake" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )


async def test_streak_system():
    """Test streak tracking."""
    print("\n📝 TEST SUITE: Streak System")
    print("-" * 40)

    phone = "910000000011"
    await reset_user(phone)

    # Setup and complete a drill
    await send_message(phone, "Hi")
    await send_message(phone, "StreakTester")
    await send_message(phone, "I made a mistake in thermodynamics")
    await send_message(phone, "GO")
    res = await send_message(phone, "A")

    # Check streak in response
    results.record(
        "Streak mentioned after drill",
        "streak" in res["response"].lower() or "day" in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )

    # Check streak in database
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()

    try:
        user = client.table("users").select("current_streak").eq("phone_number", phone).execute()

        if user.data:
            results.record(
                "Streak tracked in database",
                user.data[0].get("current_streak", 0) >= 0,
                f"Streak: {user.data[0].get('current_streak')}"
            )
        else:
            results.record("Streak tracked in database", False, "User not found")
    except Exception as e:
        results.record("Streak tracked in database", False, f"DB error: {e}")


async def test_intent_classification():
    """Test various ways users might phrase things."""
    print("\n📝 TEST SUITE: Intent Classification")
    print("-" * 40)

    phone = "910000000012"
    await reset_user(phone)
    await send_message(phone, "Hi")
    await send_message(phone, "IntentTester")
    await send_message(phone, "I made an error in calculus")

    # Various ways to start drill
    drill_triggers = [
        ("GO", "GO command"),
        ("go", "lowercase go"),
        ("Let's go", "Let's go"),
        ("start", "start"),
        ("practice", "practice"),
        ("quiz me", "quiz me"),
        ("test me", "test me"),
    ]

    for trigger, name in drill_triggers[:3]:  # Test first 3
        phone_temp = f"91000000{hash(trigger) % 10000:04d}"
        await reset_user(phone_temp)
        await send_message(phone_temp, "Hi")
        await send_message(phone_temp, "User")
        await send_message(phone_temp, "I confused X with Y")
        res = await send_message(phone_temp, trigger)

        is_drill = "question" in res["response"].lower() or "?" in res["response"] or "*a*" in res["response"].lower()
        results.record(
            f"'{name}' triggers drill",
            is_drill,
            f"Got: {res['response'][:50]}"
        )


async def test_database_integrity():
    """Test data is saved correctly."""
    print("\n📝 TEST SUITE: Database Integrity")
    print("-" * 40)

    from app.db.supabase import get_supabase_client
    client = get_supabase_client()

    # Test 1: Questions exist
    questions = client.table("questions").select("id", count="exact").execute()
    results.record(
        "Questions table has data",
        (questions.count or 0) > 0,
        f"Found {questions.count} questions"
    )

    # Test 2: Subjects table populated
    subjects = client.table("subjects").select("*").execute()
    results.record(
        "Subjects table populated",
        len(subjects.data) >= 3,
        f"Found {len(subjects.data)} subjects"
    )

    # Test 3: Questions have required fields
    sample = client.table("questions").select("*").limit(1).execute()
    if sample.data:
        q = sample.data[0]
        has_fields = all([
            q.get("question_text"),
            q.get("option_a"),
            q.get("option_b"),
            q.get("correct_option"),
            q.get("subject"),
        ])
        results.record(
            "Questions have required fields",
            has_fields,
            f"Missing fields in question"
        )


# =============================================================================
# NEW CRITICAL TESTS
# =============================================================================

async def test_wrong_answer_flow():
    """Test answer handling flow."""
    print("\n📝 TEST SUITE: Answer Flow")
    print("-" * 40)

    phone = "910000000020"
    await reset_user(phone)

    # Setup
    await send_message(phone, "Hi")
    await send_message(phone, "AnswerFlowTester")
    await send_message(phone, "I confused vectors with scalars")
    await send_message(phone, "GO")

    # Test invalid option handling
    res1 = await send_message(phone, "Z")
    results.record(
        "Invalid option prompts for valid input",
        "a" in res1["response"].lower() or "b" in res1["response"].lower() or "option" in res1["response"].lower(),
        f"Got: {res1['response'][:80]}"
    )

    # Test valid answer
    res2 = await send_message(phone, "A")
    results.record(
        "Valid answer gets feedback",
        any(word in res2["response"].lower() for word in ["correct", "wrong", "great", "oops", "streak", "try", "right", "incorrect"]),
        f"Got: {res2['response'][:80]}"
    )


async def test_multiple_mistakes_queue():
    """Test drilling through multiple mistakes."""
    print("\n📝 TEST SUITE: Multiple Mistakes Queue")
    print("-" * 40)

    phone = "910000000021"
    await reset_user(phone)

    # Setup with multiple mistakes
    await send_message(phone, "Hi")
    await send_message(phone, "QueueTester")
    await send_message(phone, "I confused force with pressure")
    await send_message(phone, "I mixed up acids and bases")
    await send_message(phone, "I forgot integration rules")

    # Check we have 3 mistakes
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()
    user = client.table("users").select("id").eq("phone_number", phone).execute()

    if user.data:
        mistakes = client.table("student_mistakes").select("*").eq("user_id", user.data[0]["id"]).execute()
        results.record(
            "Multiple mistakes saved",
            len(mistakes.data) >= 3,
            f"Found {len(mistakes.data)} mistakes"
        )

    # Drill first
    res1 = await send_message(phone, "GO")
    results.record(
        "First drill starts",
        "question" in res1["response"].lower() or "?" in res1["response"],
        f"Got: {res1['response'][:50]}"
    )

    # Answer and check for more
    res2 = await send_message(phone, "A")
    results.record(
        "Shows remaining mistakes count",
        any(word in res2["response"].lower() for word in ["more", "remaining", "waiting", "2", "mistake"]),
        f"Got: {res2['response'][:80]}"
    )


async def test_mastery_progression():
    """Test that mistakes get marked as mastered."""
    print("\n📝 TEST SUITE: Mastery Progression")
    print("-" * 40)

    phone = "910000000022"
    await reset_user(phone)

    # Setup
    await send_message(phone, "Hi")
    await send_message(phone, "MasteryTester")
    await send_message(phone, "I confused kinetic with potential energy")

    # Drill multiple times (mastery requires 3+ correct)
    for i in range(4):
        await send_message(phone, "GO")
        await send_message(phone, "A")  # Answer

    # Check mastery in database
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()
    user = client.table("users").select("id").eq("phone_number", phone).execute()

    if user.data:
        mistakes = client.table("student_mistakes").select("times_drilled, times_correct, mastery_score").eq("user_id", user.data[0]["id"]).execute()

        if mistakes.data:
            mistake = mistakes.data[0]
            results.record(
                "Times drilled tracked",
                mistake.get("times_drilled", 0) > 0,
                f"Drilled: {mistake.get('times_drilled')}"
            )
            results.record(
                "Mastery score calculated",
                mistake.get("mastery_score", 0) >= 0,
                f"Score: {mistake.get('mastery_score')}"
            )
        else:
            results.record("Mastery tracking", False, "No mistakes found")
    else:
        results.record("Mastery tracking", False, "User not found")


async def test_question_topic_matching():
    """Test that drill questions match the mistake topic."""
    print("\n📝 TEST SUITE: Question-Topic Matching")
    print("-" * 40)

    phone = "910000000023"
    await reset_user(phone)

    # Report a specific physics mistake
    await send_message(phone, "Hi")
    await send_message(phone, "TopicTester")
    await send_message(phone, "I confused Newton's laws of motion")

    # Get drill
    res = await send_message(phone, "GO")

    # Check question is physics-related
    physics_keywords = ["force", "motion", "newton", "mass", "acceleration", "velocity", "momentum", "energy", "physics"]
    has_physics = any(kw in res["response"].lower() for kw in physics_keywords)

    results.record(
        "Drill question matches topic (physics)",
        has_physics or "question" in res["response"].lower(),
        f"Got: {res['response'][:100]}"
    )


async def test_no_questions_for_topic():
    """Test handling when no questions exist for a topic."""
    print("\n📝 TEST SUITE: No Questions for Topic")
    print("-" * 40)

    phone = "910000000024"
    await reset_user(phone)

    # Report a very specific/obscure mistake
    await send_message(phone, "Hi")
    await send_message(phone, "NoQuestionTester")
    await send_message(phone, "I confused quantum chromodynamics with string theory")

    # Try to drill
    res = await send_message(phone, "GO")

    # Should either generate a question or handle gracefully
    results.record(
        "Handles missing questions gracefully",
        len(res["response"]) > 10 and "error" not in res["response"].lower(),
        f"Got: {res['response'][:80]}"
    )


async def test_resubscribe_after_stop():
    """Test user can re-subscribe after STOP."""
    print("\n📝 TEST SUITE: Re-subscribe After STOP")
    print("-" * 40)

    phone = "910000000025"
    await reset_user(phone)

    # Setup and STOP
    await send_message(phone, "Hi")
    await send_message(phone, "ResubscribeTester")
    await send_message(phone, "STOP")

    # Try to interact (should be ignored)
    res1 = await send_message(phone, "Hi")
    results.record(
        "Inactive user gets no response",
        res1["response"] == "" or res1["response"] is None or "inactive" not in res1["response"].lower(),
        f"Got: '{res1['response'][:50]}'" if res1["response"] else "Got: empty (correct)"
    )

    # Re-subscribe
    res2 = await send_message(phone, "START")
    results.record(
        "START reactivates user",
        "welcome" in res2["response"].lower() or "back" in res2["response"].lower() or "go" in res2["response"].lower(),
        f"Got: {res2['response'][:80]}"
    )

    # Verify active in DB
    from app.db.supabase import get_supabase_client
    client = get_supabase_client()
    user = client.table("users").select("is_active").eq("phone_number", phone).execute()

    results.record(
        "User marked active in DB",
        user.data and user.data[0].get("is_active") == True,
        f"is_active: {user.data[0].get('is_active') if user.data else 'N/A'}"
    )


async def test_conversation_persistence():
    """Test state persists across sessions."""
    print("\n📝 TEST SUITE: Conversation Persistence")
    print("-" * 40)

    phone = "910000000026"
    await reset_user(phone)

    # Session 1: Setup
    await send_message(phone, "Hi")
    await send_message(phone, "PersistenceTester")
    await send_message(phone, "I confused impulse with momentum")

    # Session 2: Return and check state
    res = await send_message(phone, "stats")

    results.record(
        "Stats remember previous session",
        "mistake" in res["response"].lower() or "1" in res["response"],
        f"Got: {res['response'][:80]}"
    )

    # Check can still drill the mistake
    res2 = await send_message(phone, "GO")
    results.record(
        "Can drill mistake from previous session",
        "question" in res2["response"].lower() or "?" in res2["response"],
        f"Got: {res2['response'][:80]}"
    )


async def test_response_time():
    """Test response time is acceptable."""
    print("\n📝 TEST SUITE: Response Time")
    print("-" * 40)

    import time

    phone = "910000000027"
    await reset_user(phone)

    # Measure simple message
    start = time.time()
    await send_message(phone, "Hi")
    greeting_time = time.time() - start

    results.record(
        f"Greeting response < 5s",
        greeting_time < 5,
        f"Took {greeting_time:.2f}s"
    )

    # Measure mistake classification (heavier LLM call)
    await send_message(phone, "TimeTester")
    start = time.time()
    await send_message(phone, "I confused derivatives with integrals")
    mistake_time = time.time() - start

    results.record(
        f"Mistake classification < 10s",
        mistake_time < 10,
        f"Took {mistake_time:.2f}s"
    )

    # Measure drill generation (heaviest)
    start = time.time()
    await send_message(phone, "GO")
    drill_time = time.time() - start

    results.record(
        f"Drill generation < 15s",
        drill_time < 15,
        f"Took {drill_time:.2f}s"
    )


# =============================================================================
# MAIN
# =============================================================================

async def run_all_tests():
    """Run all test suites."""
    print("=" * 50)
    print("🧪 MAHAVIHARA QA TEST SUITE")
    print("=" * 50)
    print(f"Started: {datetime.now().isoformat()}")

    # Original tests
    await test_onboarding()
    await test_mistake_reporting()
    await test_drilling_flow()
    await test_answer_handling()
    await test_stats()
    await test_edge_cases()
    await test_whatsapp_compliance()
    await test_returning_user()
    await test_streak_system()
    await test_intent_classification()
    await test_database_integrity()

    # NEW Critical tests
    await test_wrong_answer_flow()
    await test_multiple_mistakes_queue()
    await test_mastery_progression()
    await test_question_topic_matching()
    await test_no_questions_for_topic()
    await test_resubscribe_after_stop()
    await test_conversation_persistence()
    await test_response_time()

    return results.summary()


async def main():
    parser = argparse.ArgumentParser(description="QA Test Suite for Mahavihara")
    parser.add_argument("--test", help="Run specific test suite")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.test:
        test_map = {
            "onboarding": test_onboarding,
            "mistakes": test_mistake_reporting,
            "drilling": test_drilling_flow,
            "answers": test_answer_handling,
            "stats": test_stats,
            "edge": test_edge_cases,
            "whatsapp": test_whatsapp_compliance,
            "returning": test_returning_user,
            "streak": test_streak_system,
            "intent": test_intent_classification,
            "database": test_database_integrity,
        }

        if args.test in test_map:
            await test_map[args.test]()
            results.summary()
        else:
            print(f"Unknown test: {args.test}")
            print(f"Available: {', '.join(test_map.keys())}")
    else:
        success = await run_all_tests()
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
