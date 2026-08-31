"""FastAPI application entry point with all features."""
import os
import ssl

# Bypass SSL verification for corporate proxies (development only)
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
import nltk

from app.config import settings
from app.api.routes import analysis, health, cache, upload, streaming, advanced, feedback, learning, transition
from app.middleware.error_handler import add_error_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.monitoring import MonitoringMiddleware
from app.utils.logger import setup_logging, logger
from app.utils.redis_client import RedisClient

# Setup logging
setup_logging(settings.log_level)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"AI Service: {'Enabled' if settings.use_ai_service else 'Disabled'}")
    logger.info(f"Cache: {'Enabled' if settings.cache_enabled else 'Disabled'}")
    
    # Download NLTK data
    try:
        nltk.download('punkt', quiet=True)
        nltk.download('stopwords', quiet=True)
        logger.info("NLTK data downloaded successfully")
    except Exception as e:
        logger.warning(f"Could not download NLTK data: {e}")
    
    # Test Redis connection
    if settings.cache_enabled:
        redis_client = RedisClient()
        if await redis_client.ping():
            logger.info("Redis connection verified")
        else:
            logger.warning("Redis connection failed - cache will be disabled")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")
    if settings.cache_enabled:
        await RedisClient().close()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Resume vs Job Description Friction Matcher API with AI, Caching, and Advanced Features",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_per_minute,
    requests_per_day=settings.rate_limit_per_day
)

# Add monitoring middleware
app.add_middleware(MonitoringMiddleware)

# Add error handlers
add_error_handlers(app)

# Register routers
api_prefix = settings.api_prefix
app.include_router(health.router, prefix=api_prefix, tags=["Health"])
app.include_router(analysis.router, prefix=api_prefix, tags=["Analysis"])
app.include_router(transition.router, prefix=api_prefix, tags=["Transition"])
app.include_router(cache.router, prefix=api_prefix, tags=["Cache"])
app.include_router(upload.router, prefix=api_prefix, tags=["Upload"])
app.include_router(streaming.router, prefix=api_prefix, tags=["Streaming"])
app.include_router(advanced.router, prefix=api_prefix, tags=["Advanced"])
app.include_router(feedback.router, prefix=api_prefix, tags=["Feedback"])
app.include_router(learning.router, prefix=f"{api_prefix}/learning", tags=["Learning"])

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "ai_service": settings.use_ai_service,
        "cache_enabled": settings.cache_enabled,
        "features": [
            "PDF Resume Parsing",
            "Smart JD Extraction",
            "WebSocket Streaming",
            "Rate Limiting",
            "Monitoring",
            "Interview Questions",
            "ATS Optimization",
            "Career Advice"
        ],
        "docs": "/docs" if settings.debug else None
    }

# Metrics endpoint for Prometheus
@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return Response("Prometheus metrics disabled", status_code=503)

# Optional: Run directly (for development)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
