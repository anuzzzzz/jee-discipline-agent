#!/usr/bin/env python3
"""Quick test for Phase 1 setup."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    print("Testing imports...")

    try:
        from app.config import settings
        print(f"  ✅ Config loaded (DEBUG={settings.DEBUG})")
    except Exception as e:
        print(f"  ❌ Config failed: {e}")
        return False

    try:
        from app.db.models import User, Question, Mistake
        print("  ✅ Models imported")
    except Exception as e:
        print(f"  ❌ Models failed: {e}")
        return False

    try:
        from app.db.supabase import get_supabase_client
        print("  ✅ Supabase client imported")
    except Exception as e:
        print(f"  ❌ Supabase failed: {e}")
        return False

    return True


def test_supabase_connection():
    print("\nTesting Supabase connection...")

    try:
        from app.db.supabase import init_supabase
        import asyncio

        result = asyncio.run(init_supabase())
        return result
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("PHASE 1 TEST")
    print("=" * 50)

    imports_ok = test_imports()
    db_ok = test_supabase_connection()

    print("\n" + "=" * 50)
    if imports_ok and db_ok:
        print("🎉 PHASE 1 COMPLETE!")
    else:
        print("⚠️  Some tests failed - check errors above")
