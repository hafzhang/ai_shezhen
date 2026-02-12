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
import uvicorn

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api_service.app.api.v1 import api_router
from api_service.core.config import settings
from api_service.core.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


# Global predictor instances
pipeline_instance = None
segmentor_instance = None
classifier_instance = None


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

    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        logger.warning("API will run in mock mode without models")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting AI舌诊智能诊断系统 API...")
    initialize_models()
    logger.info("API service ready")
    yield
    # Shutdown
    logger.info("Shutting down API service...")


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


def main():
    """Run the API server"""
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
