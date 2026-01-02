"""
Mahavihara - JEE Discipline Agent

FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload

Run in production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.db.supabase import init_supabase
from app.api.webhooks import router as webhooks_router
from app.api.health import router as health_router
from app.api.admin import router as admin_router
from app.scheduler.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup: Initialize connections, start scheduler
    Shutdown: Cleanup resources, stop scheduler
    """
    # Startup
    print("🚀 Starting Mahavihara...")
    await init_supabase()

    # Start scheduler (only in production or if explicitly enabled)
    if not settings.DEBUG or settings.ENVIRONMENT == "production":
        print("📅 Starting scheduler...")
        start_scheduler()
    else:
        print("📅 Scheduler disabled in debug mode (set DEBUG=False to enable)")

    print("✅ Mahavihara is ready!")

    yield

    # Shutdown
    print("👋 Shutting down Mahavihara...")
    stop_scheduler()


# Create FastAPI app
app = FastAPI(
    title="Mahavihara",
    description="JEE Discipline Agent - WhatsApp AI Tutor that hunts you until you fix your mistakes!",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware (needed if you add a frontend later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(webhooks_router, prefix="/api", tags=["Webhooks"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Mahavihara",
        "tagline": "We don't teach. We don't diagnose. We ENFORCE.",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
