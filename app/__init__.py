"""
App package initialization.
Re-exports configuration for backward compatibility.
"""

from app.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
