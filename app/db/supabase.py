"""
Supabase client initialization and helper functions.
"""

from supabase import create_client, Client
from typing import Optional
from app.config import settings

# Global client instance (singleton pattern)
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get the Supabase client instance.
    Creates a new client if one doesn't exist.

    Uses ANON key - for normal app operations.
    """
    global _supabase_client

    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY
        )

    return _supabase_client


def get_service_client() -> Client:
    """
    Get a Supabase client with SERVICE ROLE key.

    Use this for admin operations:
    - Ingestion pipeline (bulk inserts)
    - Bypassing RLS policies
    - Background jobs

    ⚠️ Never expose this key to frontend!
    """
    if not settings.SUPABASE_SERVICE_KEY:
        raise ValueError(
            "SUPABASE_SERVICE_KEY not set. "
            "Required for admin operations."
        )

    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY
    )


async def init_supabase() -> bool:
    """
    Initialize and test Supabase connection.
    Called on application startup.

    Returns True if connection successful.
    """
    try:
        client = get_supabase_client()

        # Test connection with a simple query
        result = client.table("subjects").select("id").limit(1).execute()

        print(f"✅ Supabase connected successfully")
        print(f"   Found {len(result.data)} subjects in database")

        return True

    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("   Make sure you've:")
        print("   1. Created a Supabase project")
        print("   2. Run schema.sql in SQL Editor")
        print("   3. Added credentials to .env")

        return False


# Convenience alias for quick access
supabase = get_supabase_client
