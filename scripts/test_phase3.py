#!/usr/bin/env python3
"""
Phase 3 Test - Agent Router

Tests the conversation flow locally (without WhatsApp).
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def simulate_conversation():
    """Simulate a full conversation flow."""
    print("\n Simulating conversation...\n")

    from app.agent.router import process_message

    # Use a test phone number
    phone = "919999999999"

    # Conversation flow
    messages = [
        ("Hi", None),                                    # Greeting
        ("Rahul", None),                                 # Name
        ("I confused centripetal with centrifugal", None),  # Report mistake
        ("GO", None),                                    # Start drill
        ("A", None),                                     # Answer (might be wrong)
        ("stats", None),                                 # Check stats
    ]

    for text, image in messages:
        print(f"User: {text}")

        response = await process_message(
            phone_number=phone,
            message_text=text,
            image_url=image
        )

        if response:
            # Truncate long responses for display
            display = response[:200] + "..." if len(response) > 200 else response
            print(f"Mahavihara: {display}\n")
        else:
            print("Mahavihara: [no response]\n")

        print("-" * 40)


async def test_intent_routing():
    """Test that intents route to correct handlers."""
    print("\nTesting intent routing...")

    from app.agent.router import route_message
    from app.agent.state import create_initial_state
    from app.db.models import User
    from datetime import datetime

    # Create mock user
    mock_user = User(
        id="test-123",
        phone_number="919999999999",
        name="Test User",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    # Create initial state
    state = create_initial_state(
        user_id=mock_user.id,
        phone_number=mock_user.phone_number,
        user_name=mock_user.name
    )
    state["phase"] = "idle"  # Skip onboarding

    # Test cases
    test_cases = [
        ("Hi", "GREETING"),
        ("GO", "START_DRILL"),
        ("stats", "CHECK_STATS"),
        ("help", "HELP"),
        ("stop", "STOP"),
    ]

    print("  Intent routing tests:")
    for message, expected in test_cases:
        from app.services.llm import classify_intent
        result = await classify_intent(message, False, 0)
        actual = result.get("intent")
        status = "✅" if actual == expected else "❌"
        print(f"    {status} '{message}' -> {actual} (expected {expected})")

    return True


async def main():
    print("=" * 50)
    print("PHASE 3 TEST - Agent Router")
    print("=" * 50)

    try:
        # Test intent routing
        await test_intent_routing()

        # Simulate conversation (requires Supabase)
        print("\n" + "=" * 50)
        print("CONVERSATION SIMULATION")
        print("=" * 50)
        await simulate_conversation()

        print("\n" + "=" * 50)
        print("PHASE 3 COMPLETE!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
