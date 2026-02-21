#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI舌诊智能诊断系统 - FastAPI主应用

Main FastAPI application for tongue diagnosis AI system.
Provides RESTful API endpoints for segmentation, classification, and diagnosis.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from redis import Redis
import uvicorn

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api_service.app.api.v1 import api_router
from api_service.core.config import settings
from api_service.core.logging_config import setup_logging
from api_service.app.middleware import (
    update_model_status,
    update_redis_status
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


# Global predictor instances
pipeline_instance = None
segmentor_instance = None
classifier_instance = None

# Global middleware instances (task-4-8)
redis_client: Optional[Redis] = None


def initialize_middleware():
    """Initialize middleware components (task-4-8, task-5-2)"""
    global redis_client

    # Initialize Redis client for rate limiting
    if settings.ENABLE_RATE_LIMIT:
        try:
            redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            redis_client.ping()
            logger.info(f"Redis client initialized for rate limiting: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            update_redis_status(True)  # task-5-2: Update Prometheus metric
        except Exception as e:
            logger.warning(f"Redis unavailable for rate limiting, using in-memory fallback: {e}")
            redis_client = None
            update_redis_status(False)  # task-5-2: Update Prometheus metric

    # Initialize rate limiter
    if settings.ENABLE_RATE_LIMIT:
        from api_service.app.middleware import init_rate_limiter
        rate_limiter = init_rate_limiter(redis_client)
        logger.info(f"Rate limiter initialized: {rate_limiter.default_rate} requests/second")

    # Initialize circuit breakers
    if settings.ENABLE_CIRCUIT_BREAKER:
        from api_service.app.middleware import init_circuit_breakers
        init_circuit_breakers()
        logger.info("Circuit breakers initialized")


def initialize_models():
    """Initialize ML models on startup"""
    global pipeline_instance, segmentor_instance, classifier_instance

    try:
        from models.pipeline import (
            EndToEndPipeline,
            TongueSegmentationPredictor,
            TongueClassificationPredictor
        )

        # Model paths from environment
        seg_model_path = os.getenv("SEGMENT_MODEL_PATH", "models/deploy/segment_fp16/model_fp16.pdparams")
        clas_model_path = os.getenv("CLASSIFY_MODEL_PATH", "models/deploy/classify_fp16/model_fp16.pdparams")
        use_fp16 = os.getenv("USE_FP16", "true").lower() == "true"
        device = os.getenv("INFERENCE_DEVICE", "cpu")

        # Check if model files exist
        seg_path = Path(seg_model_path)
        clas_path = Path(clas_model_path)

        if seg_path.exists():
            logger.info(f"Initializing segmentation predictor with: {seg_model_path}")
            segmentor_instance = TongueSegmentationPredictor(
                model_path=seg_model_path,
                input_size=(512, 512),
                use_fp16=use_fp16,
                device=device
            )
            logger.info("Segmentation predictor initialized successfully")
        else:
            logger.warning(f"Segmentation model not found at {seg_model_path}, using mock mode")

        if clas_path.exists():
            logger.info(f"Initializing classification predictor with: {clas_model_path}")
            classifier_instance = TongueClassificationPredictor(
                model_path=clas_model_path,
                input_size=(224, 224),
                use_fp16=use_fp16,
                device=device
            )
            logger.info("Classification predictor initialized successfully")
        else:
            logger.warning(f"Classification model not found at {clas_model_path}, using mock mode")

        # Initialize end-to-end pipeline if both models are available
        if segmentor_instance and classifier_instance:
            logger.info("Initializing end-to-end pipeline")
            pipeline_instance = EndToEndPipeline(
                seg_model_path=seg_model_path,
                clas_model_path=clas_model_path,
                use_fp16=use_fp16,
                device=device
            )
            logger.info("End-to-end pipeline initialized successfully")

        # Set model references in v1 endpoints module
        try:
            from api_service.app.api.v1 import endpoints as v1_endpoints
            v1_endpoints.set_model_references(
                pipeline=pipeline_instance,
                segmentor=segmentor_instance,
                classifier=classifier_instance
            )
            logger.info("v1 endpoints model references set")
        except ImportError as e:
            logger.warning(f"Could not set v1 endpoints model references: {e}")

        # Set model references in v2 diagnosis module
        try:
            from api_service.app.api.v2 import diagnosis as v2_diagnosis
            v2_diagnosis.set_model_references(
                pipeline=pipeline_instance,
                segmentor=segmentor_instance,
                classifier=classifier_instance
            )
            logger.info("v2 diagnosis model references set")
        except ImportError as e:
            logger.warning(f"Could not set v2 diagnosis model references: {e}")

        # task-5-2: Update Prometheus metrics for model status
        update_model_status("segmentation", segmentor_instance is not None)
        update_model_status("classification", classifier_instance is not None)
        update_model_status("pipeline", pipeline_instance is not None)

    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        logger.warning("API will run in mock mode without models")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AI舌诊智能诊断系统 API...")

    # Initialize database first (US-118)
    try:
        from api_service.app.core.database import init_db, close_db
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.warning("API will start without database connection")

    initialize_middleware()  # task-4-8: Initialize middleware before models
    initialize_models()
    logger.info("API service ready")
    yield
    # Shutdown
    logger.info("Shutting down API service...")

    # Close database connections (US-118)
    try:
        from api_service.app.core.database import close_db
        close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning(f"Error closing database: {e}")

    if redis_client:
        try:
            redis_client.close()
            update_redis_status(False)  # task-5-2: Update Prometheus metric
        except Exception:
            pass


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.API_VERSION,
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Rate Limiting Middleware (task-4-8)
if settings.ENABLE_RATE_LIMIT:
    from api_service.app.middleware import RateLimitMiddleware, get_rate_limiter
    rate_limiter = get_rate_limiter()
    if rate_limiter:
        app.add_middleware(
            RateLimitMiddleware,
            rate_limiter=rate_limiter,
            default_limit=settings.RATE_LIMIT_PER_SECOND,
            default_window=1
        )
        logger.info("Rate limiting middleware enabled")

# Configure Prometheus Middleware (task-5-2)
from api_service.app.middleware import PrometheusMiddleware
app.add_middleware(PrometheusMiddleware)
logger.info("Prometheus metrics middleware enabled")


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "validation_error",
            "message": "请求参数验证失败",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "internal_error",
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include API v2 router (US-118 - Authentication endpoints)
try:
    from api_service.app.api.v2 import auth
    app.include_router(auth.router, prefix="/api/v2/auth", tags=["Authentication"])
    logger.info("API v2 authentication endpoints registered")
except ImportError as e:
    logger.warning(f"API v2 authentication endpoints not available: {e}")

# Include API v2 diagnosis router (US-121 - Diagnosis with database integration)
# Note: Model references will be set after initialization in initialize_models()
try:
    from api_service.app.api.v2 import diagnosis
    app.include_router(diagnosis.router, prefix="/api/v2/diagnosis", tags=["Diagnosis"])
    logger.info("API v2 diagnosis endpoints registered")
except ImportError as e:
    logger.warning(f"API v2 diagnosis endpoints not available: {e}")

# Include API v2 history router (US-123 - Diagnosis history query)
try:
    from api_service.app.api.v2 import history
    app.include_router(history.router, prefix="/api/v2/history", tags=["History"])
    logger.info("API v2 history endpoints registered")
except ImportError as e:
    logger.warning(f"API v2 history endpoints not available: {e}")

# Include API v2 health records router (US-128 - Health records management)
try:
    from api_service.app.api.v2 import health_records
    app.include_router(health_records.router, prefix="/api/v2/health-records", tags=["Health Records"])
    logger.info("API v2 health records endpoints registered")
except ImportError as e:
    logger.warning(f"API v2 health records endpoints not available: {e}")

# Include API v2 users router (US-129 - User management)
try:
    from api_service.app.api.v2 import users
    app.include_router(users.router, prefix="/api/v2/users", tags=["Users"])
    logger.info("API v2 users endpoints registered")
except ImportError as e:
    logger.warning(f"API v2 users endpoints not available: {e}")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "success": True,
        "message": "AI舌诊智能诊断系统 API",
        "version": settings.API_VERSION,
        "docs_url": "/docs" if settings.ENABLE_API_DOCS else None,
        "endpoints": {
            "health": "/api/v1/health",
            "segment": "/api/v1/segment",
            "classify": "/api/v1/classify",
            "diagnosis": "/api/v1/diagnosis"
        }
    }


# Health check endpoint (also at /api/v1/health)
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    models_loaded = {
        "segmentation": segmentor_instance is not None,
        "classification": classifier_instance is not None,
        "pipeline": pipeline_instance is not None
    }

    status_code = status.HTTP_200_OK
    if not any(models_loaded.values()):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "status": "healthy" if any(models_loaded.values()) else "degraded",
            "models": models_loaded,
            "api_version": settings.API_VERSION
        }
    )


# Circuit breaker state endpoint (task-4-8)
@app.get("/api/v1/circuit-breakers", tags=["Monitoring"])
async def get_circuit_breaker_status():
    """Get circuit breaker states for monitoring"""
    from api_service.app.middleware import get_circuit_breaker_states
    return await get_circuit_breaker_states()


# Cache statistics endpoint (task-5-1)
@app.get("/api/v1/cache/stats", tags=["Monitoring"])
async def get_cache_stats():
    """Get cache statistics for monitoring"""
    from api_service.performance import get_cache_manager
    cache_mgr = get_cache_manager()
    return cache_mgr.get_report()


# Cache management endpoint (task-5-1)
@app.post("/api/v1/cache/clear", tags=["Monitoring"])
async def clear_cache(cache_type: Optional[str] = None):
    """Clear cache by type

    Args:
        cache_type: Cache type to clear (segment/classify/diagnosis/all)
                   If None, clears all caches
    """
    from api_service.performance import get_cache_manager
    cache_mgr = get_cache_manager()

    if cache_type == "segment":
        cache_mgr.clear_segment_cache()
        message = "Segment cache cleared"
    elif cache_type == "classify":
        cache_mgr.clear_classify_cache()
        message = "Classify cache cleared"
    elif cache_type == "diagnosis":
        cache_mgr.clear_diagnosis_cache()
        message = "Diagnosis cache cleared"
    else:  # None or "all"
        cache_mgr.clear_all_cache()
        message = "All caches cleared"

    return {
        "success": True,
        "message": message
    }


# Prometheus metrics endpoint (task-5-2)
@app.get("/metrics", tags=["Monitoring"])
async def prometheus_metrics():
    """Prometheus metrics endpoint for scraping"""
    from api_service.app.middleware import metrics_endpoint
    return await metrics_endpoint()


# API v2 Health check endpoint with database status (US-118)
@app.get("/api/v2/health", tags=["Health"])
async def health_check_v2():
    """
    Health check endpoint with database status.

    Returns service health status including:
    - Model loading status
    - Database connection status
    - Overall service status
    """
    models_loaded = {
        "segmentation": segmentor_instance is not None,
        "classification": classifier_instance is not None,
        "pipeline": pipeline_instance is not None
    }

    # Check database health (US-118)
    db_health = None
    try:
        from api_service.app.core.database import check_db_health
        db_health = await check_db_health()
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        db_health = {
            "healthy": False,
            "message": "Database health check failed",
            "database": "unknown",
            "error": str(e)
        }

    # Determine overall status
    models_ok = any(models_loaded.values())
    db_ok = db_health.get("healthy", False) if db_health else False
    overall_healthy = models_ok and db_ok

    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "status": "healthy" if overall_healthy else "degraded",
            "models": models_loaded,
            "database": db_health,
            "api_version": settings.API_VERSION
        }
    )


def main():
    """Run API server"""
    uvicorn.run(
        "api_service.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
