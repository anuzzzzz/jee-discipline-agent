"""Test Supabase and Gupshup connections"""
import os
from dotenv import load_dotenv

load_dotenv()

def test_supabase():
    """Test Supabase connection"""
    print("\n=== Testing Supabase ===")
    try:
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
            return False

        client = create_client(url, key)
        # Try listing tables via RPC or just check auth works
        # The error about table not existing means auth worked
        try:
            response = client.table("_fake_table_test_").select("*").limit(1).execute()
        except Exception as e:
            if "PGRST205" in str(e) or "not find" in str(e) or "does not exist" in str(e):
                print("✅ Supabase connection successful! (no tables yet)")
                return True
            raise e
        print("✅ Supabase connection successful!")
        return True
    except Exception as e:
        print(f"❌ Supabase error: {e}")
        return False

def test_database():
    """Test direct PostgreSQL connection"""
    print("\n=== Testing Database (PostgreSQL) ===")
    try:
        import asyncpg
        import asyncio

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ Missing DATABASE_URL")
            return False

        async def connect():
            conn = await asyncpg.connect(database_url)
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            return version

        version = asyncio.run(connect())
        print(f"✅ Database connection successful!")
        print(f"   PostgreSQL: {version[:50]}...")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_gupshup():
    """Test Gupshup API connection"""
    print("\n=== Testing Gupshup ===")
    try:
        import httpx

        api_key = os.getenv("GUPSHUP_API_KEY")
        app_name = os.getenv("WHATSAPP_APP_NAME")

        if not api_key:
            print("❌ Missing GUPSHUP_API_KEY")
            return False

        if not app_name:
            print("❌ Missing WHATSAPP_APP_NAME")
            return False

        # Test API by listing templates
        response = httpx.get(
            f"https://api.gupshup.io/sm/api/v1/template/list/{app_name}",
            headers={"apikey": api_key}
        )

        if response.status_code == 200:
            data = response.json()
            template_count = len(data.get("templates", []))
            print(f"✅ Gupshup connection successful!")
            print(f"   App: {app_name}")
            print(f"   Templates: {template_count}")
            return True
        else:
            print(f"❌ Gupshup error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Gupshup error: {e}")
        return False

if __name__ == "__main__":
    print("Testing connections...\n")

    results = {
        "Supabase": test_supabase(),
        "Database": test_database(),
        "Gupshup": test_gupshup(),
    }

    print("\n" + "="*40)
    print("SUMMARY")
    print("="*40)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
