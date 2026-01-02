#!/usr/bin/env python3
"""
Phase 2 Test Script
Tests database queries and services.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_database_queries():
    """Test that query functions work."""
    print("\nTesting database queries...")

    try:
        from app.db.queries import (
            get_or_create_user,
            get_user_stats,
            get_question_count
        )
        print("  ✅ Query functions imported")

        # Test user creation (will fail without real Supabase)
        # Just testing imports for now
        return True

    except Exception as e:
        print(f"  ❌ Query import failed: {e}")
        return False


async def test_llm_service():
    """Test LLM service."""
    print("\nTesting LLM service...")

    try:
        from app.services.llm import test_llm_connection

        # This will actually call OpenAI
        result = await test_llm_connection()
        return result

    except Exception as e:
        print(f"  ❌ LLM test failed: {e}")
        return False


async def test_whatsapp_service():
    """Test WhatsApp service configuration."""
    print("\nTesting WhatsApp service...")

    try:
        from app.services.whatsapp import test_whatsapp_connection

        result = await test_whatsapp_connection()
        return result

    except Exception as e:
        print(f"  ❌ WhatsApp test failed: {e}")
        return False


async def test_intent_classification():
    """Test intent classification with sample messages."""
    print("\nTesting intent classification...")

    try:
        from app.services.llm import classify_intent

        test_cases = [
            ("Hi", False, 0),
            ("GO", False, 5),
            ("A", True, 0),
            ("I confused torque with force", False, 0),
            ("stats", False, 3),
            ("stop", False, 0),
        ]

        for message, has_drill, pending in test_cases:
            result = await classify_intent(message, has_drill, pending)
            print(f"  '{message}' -> {result['intent']} ({result['confidence']:.1f})")

        return True

    except Exception as e:
        print(f"  ❌ Intent classification failed: {e}")
        return False


async def main():
    print("=" * 50)
    print("PHASE 2 TEST - Services")
    print("=" * 50)

    results = []

    # Test imports
    results.append(("Database Queries", await test_database_queries()))

    # Test LLM (requires OPENAI_API_KEY)
    results.append(("LLM Service", await test_llm_service()))

    # Test WhatsApp config
    results.append(("WhatsApp Config", await test_whatsapp_service()))

    # Test intent classification (requires OpenAI)
    results.append(("Intent Classification", await test_intent_classification()))

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
        print("🎉 PHASE 2 COMPLETE!")
        print("\nNext: Phase 3 - LangGraph Agent")
    else:
        print("⚠️ Some tests failed.")
        print("Make sure you have:")
        print("  1. OPENAI_API_KEY in .env")
        print("  2. Supabase credentials in .env")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
