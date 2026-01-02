#!/usr/bin/env python3
"""
Question Ingestion CLI

Usage:
    python scripts/ingest_questions.py                    # Load all from JEEBench
    python scripts/ingest_questions.py --limit 100        # Load 100 questions
    python scripts/ingest_questions.py --subject physics  # Only physics
    python scripts/ingest_questions.py --stats            # Show current stats
"""

import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    parser = argparse.ArgumentParser(description="Ingest JEE questions into database")

    parser.add_argument(
        "--source",
        default="jeebench",
        choices=["jeebench"],
        help="Data source (default: jeebench)"
    )

    parser.add_argument(
        "--subject",
        choices=["physics", "chemistry", "mathematics", "phy", "chem", "math"],
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
        help="Show current question bank stats and exit"
    )

    args = parser.parse_args()

    # Import here to avoid loading before args are parsed
    from ingestion.pipeline import run_ingestion, get_question_stats

    if args.stats:
        print("\nCurrent Question Bank Stats")
        print("=" * 40)
        stats = await get_question_stats()
        print(f"Total Questions: {stats['total']}")
        print(f"  Physics:       {stats['physics']}")
        print(f"  Chemistry:     {stats['chemistry']}")
        print(f"  Mathematics:   {stats['mathematics']}")
        print("=" * 40)
        return 0

    # Run ingestion
    await run_ingestion(
        source=args.source,
        subject_filter=args.subject,
        limit=args.limit
    )

    # Show final stats
    print("\nUpdated Question Bank Stats")
    print("=" * 40)
    stats = await get_question_stats()
    print(f"Total Questions: {stats['total']}")
    print(f"  Physics:       {stats['physics']}")
    print(f"  Chemistry:     {stats['chemistry']}")
    print(f"  Mathematics:   {stats['mathematics']}")
    print("=" * 40)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
