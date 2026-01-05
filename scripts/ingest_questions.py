#!/usr/bin/env python3
"""
Question Ingestion CLI - Multiple sources!

Usage:
    python scripts/ingest_questions.py --source jeebench      # JEEBench (95 MCQs)
    python scripts/ingest_questions.py --source science       # Science-QnA (2000 default)
    python scripts/ingest_questions.py --source science --limit 5000  # More from Science-QnA
    python scripts/ingest_questions.py --stats                # Show stats
"""

import sys
import asyncio
import argparse
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_ingestion(source: str, subject: str = None, limit: int = None):
    """Run ingestion from specified source."""
    from ingestion.loaders.jeebench import JEEBenchLoader
    from ingestion.loaders.kaggle import MultiCSVLoader
    from ingestion.loaders.science_qna import ScienceQnALoader
    from app.db.supabase import get_service_client

    print(f"\n{'='*50}")
    print(f"📚 INGESTION PIPELINE")
    print(f"{'='*50}")
    print(f"Source: {source}")
    print(f"Subject: {subject or 'all'}")
    print(f"Limit: {limit or 'default'}")
    print(f"{'='*50}\n")

    client = get_service_client()
    stats = {"inserted": 0, "duplicates": 0, "errors": 0}

    def insert_question(q):
        """Insert a question into the database."""
        content = q.question_text + q.option_a + q.option_b
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        existing = client.table("questions").select("id").eq("content_hash", content_hash).execute()
        if existing.data:
            stats["duplicates"] += 1
            return False

        data = {
            "question_text": q.question_text,
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "correct_option": q.correct_option,
            "subject": q.subject,
            "chapter": q.chapter,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "source": q.source,
            "solution": q.solution,
            "is_pyq": q.is_pyq,
            "content_hash": content_hash,
        }

        try:
            client.table("questions").insert(data).execute()
            stats["inserted"] += 1
            return True
        except Exception as e:
            stats["errors"] += 1
            return False

    # Load from sources
    if source == "jeebench":
        print("📥 Loading JEEBench...")
        loader = JEEBenchLoader(subset=subject)
        for q in loader.load():
            insert_question(q)
            if limit and stats["inserted"] >= limit:
                break

    elif source == "science":
        print("📥 Loading Science-QnA...")
        loader = ScienceQnALoader(
            subject_filter=subject,
            limit=limit or 2000
        )
        for q in loader.load():
            insert_question(q)

    elif source == "kaggle":
        print("📥 Loading Kaggle CSVs...")
        loader = MultiCSVLoader(directory="data/raw", subject_filter=subject)
        for q in loader.load():
            insert_question(q)
            if limit and stats["inserted"] >= limit:
                break

    elif source == "all":
        # Load from all available sources
        print("📥 Loading from ALL sources...")

        # JEEBench
        for q in JEEBenchLoader(subset=subject).load():
            insert_question(q)

        # Science-QnA
        for q in ScienceQnALoader(subject_filter=subject, limit=limit or 1000).load():
            insert_question(q)

        # Kaggle (if CSVs exist)
        for q in MultiCSVLoader(subject_filter=subject).load():
            insert_question(q)

    else:
        print(f"❌ Unknown source: {source}")
        return

    # Final report
    print(f"\n{'='*50}")
    print(f"✅ INGESTION COMPLETE")
    print(f"{'='*50}")
    print(f"Inserted: {stats['inserted']}")
    print(f"Duplicates: {stats['duplicates']}")
    print(f"Errors: {stats['errors']}")

    # Show updated stats
    await show_stats()


async def show_stats():
    """Show current question bank stats."""
    from app.db.supabase import get_supabase_client

    client = get_supabase_client()

    total = client.table("questions").select("id", count="exact").execute()
    physics = client.table("questions").select("id", count="exact").eq("subject", "physics").execute()
    chemistry = client.table("questions").select("id", count="exact").eq("subject", "chemistry").execute()
    math = client.table("questions").select("id", count="exact").eq("subject", "mathematics").execute()

    # By source
    sources = client.table("questions").select("source").execute()
    source_counts = {}
    for row in sources.data:
        src = row.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    print(f"\n📊 Question Bank Stats")
    print(f"{'='*40}")
    print(f"Total Questions: {total.count or 0}")
    print(f"  Physics:       {physics.count or 0}")
    print(f"  Chemistry:     {chemistry.count or 0}")
    print(f"  Mathematics:   {math.count or 0}")
    print(f"\nBy Source:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")
    print(f"{'='*40}\n")


async def main():
    parser = argparse.ArgumentParser(description="Ingest JEE questions into database")

    parser.add_argument(
        "--source",
        default="jeebench",
        choices=["jeebench", "science", "kaggle", "all"],
        help="Data source"
    )

    parser.add_argument(
        "--subject",
        choices=["physics", "chemistry", "mathematics"],
        help="Filter by subject"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum questions to load"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current stats and exit"
    )

    args = parser.parse_args()

    if args.stats:
        await show_stats()
        return 0

    await run_ingestion(
        source=args.source,
        subject=args.subject,
        limit=args.limit
    )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
