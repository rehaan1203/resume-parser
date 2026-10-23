"""Pytest fixtures and hermetic environment configuration."""
import os

# Set dummy environment variables for hermetic testing if not set
if not os.environ.get("MISTRAL_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = "mock-test-key"
if not os.environ.get("TAVILY_API_KEY"):
    os.environ["TAVILY_API_KEY"] = "mock-tavily-key"
os.environ.setdefault("CACHE_ENABLED", "false")

from app.config import settings
settings.orchestrator_progress_delay = 0.0
