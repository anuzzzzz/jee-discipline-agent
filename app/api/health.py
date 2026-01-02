"""
Health check endpoints for Mahavihara.

Used by Cloud Run, load balancers, and monitoring.
"""

from fastapi import APIRouter
from datetime import datetime

from app.db.supabase import get_supabase_client
from app.db.queries import get_question_count

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Basic health check.

    Returns 200 if the service is running.
    Used by Cloud Run for container health.
    """
    return {
        "status": "healthy",
        "service": "mahavihara",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with dependency status.

    Checks:
    - Database connectivity
    - Question bank status
    """
    health = {
        "status": "healthy",
        "service": "mahavihara",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check Supabase
    try:
        client = get_supabase_client()
        result = client.table("subjects").select("id").limit(1).execute()
        health["checks"]["database"] = {
            "status": "healthy",
            "message": "Connected to Supabase"
        }
    except Exception as e:
        health["checks"]["database"] = {
            "status": "unhealthy",
            "message": str(e)
        }
        health["status"] = "degraded"

    # Check question bank
    try:
        count = await get_question_count()
        health["checks"]["question_bank"] = {
            "status": "healthy" if count > 0 else "warning",
            "question_count": count,
            "message": f"{count} questions in bank" if count > 0 else "Question bank is empty!"
        }
    except Exception as e:
        health["checks"]["question_bank"] = {
            "status": "unhealthy",
            "message": str(e)
        }

    return health


@router.get("/")
async def root():
    """Root endpoint - redirect to health check."""
    return {
        "service": "Mahavihara",
        "description": "JEE Discipline Agent - WhatsApp AI Tutor",
        "version": "1.0.0",
        "health": "/api/health"
    }
