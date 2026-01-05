#!/usr/bin/env python3
"""
Question Cloner - Generate synthetic variations of existing questions.

This multiplies your question bank by creating variations with different numbers.

Usage:
    python scripts/clone_questions.py --count 100    # Clone 100 questions
    python scripts/clone_questions.py --subject physics --count 50
"""

import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase import get_supabase_client, get_service_client
from app.services.llm import generate_json_response


CLONE_PROMPT = """You are a JEE Question Variation Generator.

Create a NEW VARIATION of this question by:
1. Changing numerical values (mass, radius, angle, velocity, etc.)
2. Recalculating the correct answer based on new values
3. Generating new plausible wrong options
4. Keeping the core physics/chemistry/math concept EXACTLY the same

Original Question: {question_text}

Original Options:
A) {option_a}
B) {option_b}
C) {option_c}
D) {option_d}

Original Correct Answer: {correct_option}
Original Solution: {solution}

Create a variation with DIFFERENT numbers but the SAME concept.

Return valid JSON:
{{
    "question_text": "The new question with different values...",
    "option_a": "New option A",
    "option_b": "New option B",
    "option_c": "New option C",
    "option_d": "New option D",
    "correct_option": "A/B/C/D",
    "solution": "Step by step solution for the new question"
}}"""


async def clone_question(question: dict) -> dict:
    """Generate a variation of a question."""

    prompt = CLONE_PROMPT.format(
        question_text=question["question_text"],
        option_a=question["option_a"],
        option_b=question["option_b"],
        option_c=question["option_c"],
        option_d=question["option_d"],
        correct_option=question["correct_option"],
        solution=question.get("solution", "Not provided")
    )

    result = await generate_json_response(prompt, model="gpt-4o-mini", temperature=0.7)

    if result and "question_text" in result:
        # Add metadata from original
        result["subject"] = question["subject"]
        result["chapter"] = question["chapter"]
        result["topic"] = question["topic"]
        result["difficulty"] = question["difficulty"]
        result["source"] = "Synthetic_Clone"
        result["is_pyq"] = False
        return result

    return None


async def save_cloned_question(client, clone: dict) -> bool:
    """Save a cloned question to database."""
    import hashlib

    # Generate content hash
    content = clone["question_text"] + clone["option_a"] + clone["option_b"]
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Check for duplicate
    existing = client.table("questions").select("id").eq(
        "content_hash", content_hash
    ).execute()

    if existing.data:
        return False  # Duplicate

    data = {
        "question_text": clone["question_text"],
        "option_a": clone["option_a"],
        "option_b": clone["option_b"],
        "option_c": clone["option_c"],
        "option_d": clone["option_d"],
        "correct_option": clone["correct_option"],
        "solution": clone.get("solution", ""),
        "subject": clone["subject"],
        "chapter": clone["chapter"],
        "topic": clone["topic"],
        "difficulty": clone["difficulty"],
        "source": clone["source"],
        "is_pyq": clone["is_pyq"],
        "content_hash": content_hash,
    }

    try:
        client.table("questions").insert(data).execute()
        return True
    except Exception as e:
        print(f"❌ Insert error: {e}")
        return False


async def clone_questions(
    count: int = 50,
    subject: str = None,
    batch_size: int = 10
):
    """Clone questions from the database."""

    print(f"\n{'='*50}")
    print(f"🧬 QUESTION CLONER")
    print(f"{'='*50}")
    print(f"Target: {count} clones")
    print(f"Subject: {subject or 'all'}")
    print(f"{'='*50}\n")

    client = get_supabase_client()
    service_client = get_service_client()

    # Fetch source questions
    query = client.table("questions").select("*")

    if subject:
        query = query.eq("subject", subject)

    # Get more than we need (some will fail)
    result = query.limit(count * 2).execute()
    source_questions = result.data

    print(f"📚 Found {len(source_questions)} source questions\n")

    cloned = 0
    failed = 0

    for i, question in enumerate(source_questions):
        if cloned >= count:
            break

        print(f"🧬 Cloning {i+1}/{count}: {question['topic'][:30]}...")

        try:
            clone = await clone_question(question)

            if clone:
                saved = await save_cloned_question(service_client, clone)

                if saved:
                    cloned += 1
                    print(f"   ✅ Created clone #{cloned}")
                else:
                    print(f"   ⏭️ Duplicate, skipping")
            else:
                failed += 1
                print(f"   ❌ Failed to generate")

        except Exception as e:
            failed += 1
            print(f"   ❌ Error: {e}")

        # Progress
        if (i + 1) % batch_size == 0:
            print(f"\n   Progress: {cloned} cloned, {failed} failed\n")

    print(f"\n{'='*50}")
    print(f"✅ CLONING COMPLETE")
    print(f"{'='*50}")
    print(f"Cloned: {cloned}")
    print(f"Failed: {failed}")
    print(f"{'='*50}\n")

    return {"cloned": cloned, "failed": failed}


async def main():
    parser = argparse.ArgumentParser(description="Clone JEE questions with variations")

    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of questions to clone"
    )

    parser.add_argument(
        "--subject",
        choices=["physics", "chemistry", "mathematics"],
        help="Filter by subject"
    )

    args = parser.parse_args()

    await clone_questions(
        count=args.count,
        subject=args.subject
    )


if __name__ == "__main__":
    asyncio.run(main())
