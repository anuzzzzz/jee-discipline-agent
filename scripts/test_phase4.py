#!/usr/bin/env python3
"""
Phase 4 Test - FastAPI Server

Tests the API endpoints locally.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all API modules import correctly."""
    print("Testing imports...")

    try:
        from app.main import app
        print("  ✅ FastAPI app imported")
    except Exception as e:
        print(f"  ❌ App import failed: {e}")
        return False

    try:
        from app.api.webhooks import router as webhooks_router
        from app.api.health import router as health_router
        from app.api.admin import router as admin_router
        print("  ✅ All routers imported")
    except Exception as e:
        print(f"  ❌ Router import failed: {e}")
        return False

    return True


def test_server_startup():
    """Test that server can start (without actually starting)."""
    print("\nTesting server configuration...")

    try:
        from app.main import app

        # Check routes are registered
        routes = [route.path for route in app.routes]

        expected_routes = ["/", "/api/health", "/api/webhook/whatsapp"]

        for route in expected_routes:
            if route in routes:
                print(f"  ✅ Route: {route}")
            else:
                print(f"  ❌ Missing route: {route}")

        return True

    except Exception as e:
        print(f"  ❌ Server config failed: {e}")
        return False


async def test_health_endpoint():
    """Test health endpoint."""
    print("\nTesting health endpoint...")

    try:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        response = client.get("/api/health")

        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Health check: {data.get('status')}")
            return True
        else:
            print(f"  ❌ Health check failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"  ❌ Health test failed: {e}")
        return False


async def test_webhook_test_endpoint():
    """Test the test webhook endpoint."""
    print("\nTesting webhook test endpoint...")

    try:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        response = client.post(
            "/api/webhook/test",
            json={"phone": "919999999999", "message": "Hi"}
        )

        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Test webhook works")
            print(f"     Response preview: {data.get('response', '')[:50]}...")
            return True
        else:
            print(f"  ❌ Test webhook failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"  ❌ Webhook test failed: {e}")
        return False


async def main():
    print("=" * 50)
    print("PHASE 4 TEST - FastAPI Server")
    print("=" * 50)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Server Config", test_server_startup()))
    results.append(("Health Endpoint", await test_health_endpoint()))
    results.append(("Webhook Test", await test_webhook_test_endpoint()))

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
        print("PHASE 4 COMPLETE!")
        print("\nTo run the server:")
        print("  uvicorn app.main:app --reload")
        print("\nThen test with:")
        print('  curl -X POST http://localhost:8000/api/webhook/test \\')
        print('       -H "Content-Type: application/json" \\')
        print('       -d \'{"phone": "919999999999", "message": "Hi"}\'')
    else:
        print("Some tests failed")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
