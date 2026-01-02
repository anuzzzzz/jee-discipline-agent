"""
Ingestion Pipeline - Orchestrates loading questions into database.

Usage:
    from ingestion.pipeline import run_ingestion
    await run_ingestion(source="jeebench")
"""

import hashlib
from typing import Optional
from datetime import datetime

from app.db.supabase import get_service_client
from ingestion.loaders.base import RawQuestion
from ingestion.loaders.jeebench import JEEBenchLoader


async def insert_question(question: RawQuestion, client) -> bool:
    """
    Insert a single question into database.

    Uses content hash for deduplication.

    Returns:
        True if inserted, False if duplicate or error
    """
    # Generate content hash
    content = question.question_text + question.option_a + question.option_b
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Check for duplicate
    existing = client.table("questions").select("id").eq(
        "content_hash", content_hash
    ).execute()

    if existing.data and len(existing.data) > 0:
        return False  # Duplicate

    # Prepare data
    data = {
        "question_text": question.question_text,
        "option_a": question.option_a,
        "option_b": question.option_b,
        "option_c": question.option_c,
        "option_d": question.option_d,
        "correct_option": question.correct_option,
        "subject": question.subject,
        "chapter": question.chapter,
        "topic": question.topic,
        "difficulty": question.difficulty,
        "source": question.source,
        "source_question_id": question.source_id,
        "year": question.year,
        "is_pyq": question.is_pyq,
        "solution": question.solution,
        "hint_1": question.hint_1,
        "hint_2": question.hint_2,
        "hint_3": question.hint_3,
        "content_hash": content_hash,
    }

    try:
        client.table("questions").insert(data).execute()
        return True
    except Exception as e:
        print(f"Insert error: {e}")
        return False


async def run_ingestion(
    source: str = "jeebench",
    subject_filter: Optional[str] = None,
    limit: Optional[int] = None,
    batch_size: int = 50
) -> dict:
    """
    Run the ingestion pipeline.

    Args:
        source: Data source ("jeebench")
        subject_filter: Optional filter ("physics", "chemistry", "mathematics")
        limit: Maximum questions to load (None = all)
        batch_size: Insert batch size for progress reporting

    Returns:
        Dict with stats: {"inserted": N, "duplicates": N, "errors": N}
    """
    print(f"\n{'='*50}")
    print(f"INGESTION PIPELINE")
    print(f"{'='*50}")
    print(f"Source: {source}")
    print(f"Filter: {subject_filter or 'all subjects'}")
    print(f"Limit: {limit or 'no limit'}")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"{'='*50}\n")

    # Get service client (bypasses RLS)
    client = get_service_client()

    # Select loader
    if source == "jeebench":
        loader = JEEBenchLoader(subset=subject_filter)
    else:
        raise ValueError(f"Unknown source: {source}")

    # Stats
    stats = {"inserted": 0, "duplicates": 0, "errors": 0}
    count = 0

    # Process questions
    for question in loader.load():
        count += 1

        if limit and count > limit:
            break

        result = await insert_question(question, client)

        if result:
            stats["inserted"] += 1
        else:
            stats["duplicates"] += 1

        # Progress report
        if count % batch_size == 0:
            print(f"   Processed {count}... ({stats['inserted']} inserted)")

    # Final report
    print(f"\n{'='*50}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*50}")
    print(f"Total processed: {count}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Duplicates: {stats['duplicates']}")
    print(f"Errors: {stats['errors']}")
    print(f"{'='*50}\n")

    return stats


async def get_question_stats() -> dict:
    """Get current question bank statistics."""
    from app.db.supabase import get_supabase_client

    client = get_supabase_client()

    # Total count
    total = client.table("questions").select("id", count="exact").execute()

    # By subject
    physics = client.table("questions").select("id", count="exact").eq("subject", "physics").execute()
    chemistry = client.table("questions").select("id", count="exact").eq("subject", "chemistry").execute()
    math = client.table("questions").select("id", count="exact").eq("subject", "mathematics").execute()

    return {
        "total": total.count or 0,
        "physics": physics.count or 0,
        "chemistry": chemistry.count or 0,
        "mathematics": math.count or 0,
    }
