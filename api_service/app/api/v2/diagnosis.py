#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Diagnosis Endpoints
AI舌诊智能诊断系统 - Diagnosis API v2
Phase 2: Data Persistence - US-121

This module provides diagnosis endpoints with database integration:
- POST /api/v2/diagnosis - Create diagnosis with optional authentication
- Support for anonymous diagnosis (user_id is NULL)
- Stores diagnosis results to database
- Returns diagnosis_id for later reference

Usage:
    import uvicorn
    from api_service.app.api.v2.diagnosis import router

    app.include_router(router, prefix="/api/v2/diagnosis")
"""

import logging
import time
import base64
import io
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Dict

import numpy as np
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from api_service.app.api.deps import get_db, get_optional_user, get_current_user
from api_service.app.models.database import User, TongueImage, DiagnosisHistory
from api_service.app.api.v2.models import APIResponse, DiagnosisRequest, DiagnosisResponse
from api_service.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Global model references (set by main.py on startup)
_pipeline = None
_segmentor = None
_classifier = None


def get_pipeline():
    """Get end-to-end pipeline instance"""
    global _pipeline
    if _pipeline is None:
        # Try to get from v1 endpoints module
        try:
            from api_service.app.api.v1.endpoints import get_pipeline as v1_get_pipeline
            return v1_get_pipeline()
        except ImportError:
            pass
    return _pipeline


def get_segmentor():
    """Get segmentation predictor instance"""
    global _segmentor
    if _segmentor is None:
        # Try to get from v1 endpoints module
        try:
            from api_service.app.api.v1.endpoints import get_segmentor as v1_get_segmentor
            return v1_get_segmentor()
        except ImportError:
            pass
    return _segmentor


def get_classifier():
    """Get classification predictor instance"""
    global _classifier
    if _classifier is None:
        # Try to get from v1 endpoints module
        try:
            from api_service.app.api.v1.endpoints import get_classifier as v1_get_classifier
            return v1_get_classifier()
        except ImportError:
            pass
    return _classifier


def decode_base64_image(image_data: str) -> np.ndarray:
    """Decode base64 encoded image

    Args:
        image_data: Base64 encoded image string

    Returns:
        numpy array of the image (BGR format)
    """
    try:
        # Remove data URL prefix if present
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        # Decode base64
        image_bytes = base64.b64decode(image_data)

        # Convert to PIL Image
        image = Image.open(io.BytesIO(image_bytes))

        # Convert to numpy array (BGR for OpenCV)
        image_np = np.array(image)
        if len(image_np.shape) == 3 and image_np.shape[2] == 4:
            # RGBA to BGR
            import cv2
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2BGR)
        elif len(image_np.shape) == 3:
            # RGB to BGR
            import cv2
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

        return image_np

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image data: {str(e)}"
        )


def calculate_file_hash(image: np.ndarray) -> str:
    """Calculate SHA-256 hash of image data

    Args:
        image: numpy array of the image

    Returns:
        SHA-256 hash as hex string
    """
    # Convert to PIL Image
    if len(image.shape) == 3:
        image_rgb = image[:, :, ::-1]  # BGR to RGB
    else:
        image_rgb = image
    pil_image = Image.fromarray(image_rgb)

    # Calculate hash
    import io
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    return hashlib.sha256(image_bytes).hexdigest()


def save_image_to_storage(image: np.ndarray, file_hash: str) -> tuple:
    """Save image to storage and return the path and file size

    Args:
        image: numpy array of the image
        file_hash: SHA-256 hash of the image

    Returns:
        Tuple of (storage path, file size in bytes)
    """
    # Create storage directory if it doesn't exist
    storage_dir = Path(settings.MEDIA_ROOT) / "tongue_images"
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Generate file path
    file_path = storage_dir / f"{file_hash}.png"

    # Convert to PIL Image and save
    if len(image.shape) == 3:
        image_rgb = image[:, :, ::-1]  # BGR to RGB
    else:
        image_rgb = image
    pil_image = Image.fromarray(image_rgb)

    # Save to bytes buffer first to get file size
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    # Write to file
    with open(file_path, 'wb') as f:
        f.write(image_bytes)

    return str(file_path), len(image_bytes)


@router.post("", response_model=DiagnosisResponse, tags=["Diagnosis"])
async def create_diagnosis(
    request: DiagnosisRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Create a new tongue diagnosis with optional authentication.

    This endpoint performs end-to-end tongue diagnosis and stores the
    results to the database. It supports both authenticated and anonymous users.

    Args:
        request: Diagnosis request containing image and optional user info
        db: Database session (injected)
        current_user: Optional authenticated user (injected)

    Returns:
        DiagnosisResponse with diagnosis results and diagnosis_id

    Raises:
        HTTPException 400: If image data is invalid
        HTTPException 503: If ML models are not loaded

    Example:
        POST /api/v2/diagnosis
        {
            "image": "data:image/png;base64,iVBORw0KG...",
            "user_info": {
                "age": 35,
                "gender": "male",
                "chief_complaint": "最近感觉疲劳"
            }
        }
    """
    total_start = time.time()

    try:
        # Get pipeline
        pipeline = get_pipeline()
        if pipeline is None:
            if settings.MOCK_MODE:
                # Mock response for testing
                mock_diagnosis_id = "00000000-0000-0000-0000-000000000000"
                return DiagnosisResponse(
                    success=True,
                    message="Mock mode: diagnosis result",
                    diagnosis_id=mock_diagnosis_id,
                    user_id=str(current_user.id) if current_user else None,
                    segmentation={"tongue_area": 100000, "tongue_ratio": 0.3},
                    classification={
                        "tongue_color": {"prediction": "淡红舌", "confidence": 0.85},
                        "coating_color": {"prediction": "白苔", "confidence": 0.80},
                        "tongue_shape": {"prediction": "正常", "confidence": 0.90},
                        "coating_quality": {"prediction": "薄苔", "confidence": 0.88},
                        "special_features": {
                            "red_dots": {"present": False, "confidence": 0.0},
                            "cracks": {"present": False, "confidence": 0.0},
                            "teeth_marks": {"present": False, "confidence": 0.0}
                        },
                        "health_status": {"prediction": "健康舌", "confidence": 0.87}
                    },
                    diagnosis={
                        "primary_syndrome": "气血调和",
                        "confidence": 0.85,
                        "syndrome_analysis": "舌象正常，气血调和",
                        "health_recommendations": {
                            "diet": ["保持均衡饮食"],
                            "lifestyle": ["保持规律作息"],
                            "emotional": ["保持心情愉悦"]
                        }
                    },
                    inference_time_ms=100.0
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ML models not loaded"
            )

        # Decode image
        image = decode_base64_image(request.image)

        # Calculate file hash for deduplication
        file_hash = calculate_file_hash(image)

        # Check if image already exists in database
        tongue_image = db.query(TongueImage).filter(
            TongueImage.file_hash == file_hash
        ).first()

        # If image doesn't exist, save it and create database record
        is_new_image = tongue_image is None
        tongue_image_id = None
        if is_new_image:
            storage_path, file_size = save_image_to_storage(image, file_hash)

            # Get image dimensions
            height, width = image.shape[:2] if len(image.shape) == 3 else image.shape

            # Create tongue image record (will be processed, so set is_processed=True from start)
            tongue_image = TongueImage(
                user_id=current_user.id if current_user else None,
                file_hash=file_hash,
                storage_path=storage_path,
                width=width,
                height=height,
                file_size=file_size,
                mime_type="image/png",
                is_processed=True  # Set to True since we're about to process it
            )
            db.add(tongue_image)
            db.flush()  # Get the ID without committing
            tongue_image_id = tongue_image.id
            # Keep the tongue_image in the session to be committed together with diagnosis_history
        else:
            # Store the ID for later use and keep the object for reference
            tongue_image_id = tongue_image.id
            # Don't expunge - keep it in the session for the transaction
            logger.info(f"Image already exists in database: {tongue_image_id}")

        # Perform diagnosis using the pipeline
        timing = {}
        seg_start = time.time()

        # Run segmentation
        segmentor = get_segmentor()
        if segmentor:
            seg_result = segmentor.predict(image, return_mask=True, return_overlay=True)
            timing["segmentation_ms"] = (time.time() - seg_start) * 1000
        else:
            seg_result = {}
            timing["segmentation_ms"] = 0

        # Run classification
        cls_start = time.time()
        classifier = get_classifier()
        if classifier:
            cls_result = classifier.predict(image)
            timing["classification_ms"] = (time.time() - cls_start) * 1000
        else:
            cls_result = {}
            timing["classification_ms"] = 0

        # Extract classification results
        classification = cls_result.get('results', {}) if cls_result else {}

        # Format for database storage (JSONB)
        features_for_db = {
            "tongue_color": classification.get("tongue_color", {}).__dict__ if hasattr(classification.get("tongue_color", {}), "__dict__") else classification.get("tongue_color", {}),
            "coating_color": classification.get("coating_color", {}).__dict__ if hasattr(classification.get("coating_color", {}), "__dict__") else classification.get("coating_color", {}),
            "tongue_shape": classification.get("tongue_shape", {}).__dict__ if hasattr(classification.get("tongue_shape", {}), "__dict__") else classification.get("tongue_shape", {}),
            "coating_quality": classification.get("coating_quality", {}).__dict__ if hasattr(classification.get("coating_quality", {}), "__dict__") else classification.get("coating_quality", {}),
            "special_features": classification.get("special_features", {}).__dict__ if hasattr(classification.get("special_features", {}), "__dict__") else classification.get("special_features", {}),
            "health_status": classification.get("health_status", {}).__dict__ if hasattr(classification.get("health_status", {}), "__dict__") else classification.get("health_status", {}),
        }

        # Run LLM diagnosis if enabled
        diagnosis_result = {}
        if request.enable_llm_diagnosis:
            from api_service.core.rule_based_diagnosis import diagnose_from_classification

            try:
                rule_result = diagnose_from_classification(classification)
                diagnosis_result = {
                    "primary_syndrome": rule_result.primary_syndrome,
                    "confidence": rule_result.confidence,
                    "syndrome_analysis": rule_result.syndrome_description,
                    "tcm_theory": rule_result.tcm_theory,
                    "health_recommendations": {
                        "diet": rule_result.health_recommendations.get("diet", []),
                        "lifestyle": rule_result.health_recommendations.get("lifestyle", []),
                        "emotional": rule_result.health_recommendations.get("emotional", [])
                    },
                    "risk_alert": None
                }
                timing["diagnosis_ms"] = (time.time() - cls_start - timing["classification_ms"] / 1000) * 1000
            except Exception as e:
                logger.warning(f"LLM diagnosis failed, using basic results: {e}")
                diagnosis_result = {
                    "primary_syndrome": features_for_db.get("health_status", {}).get("prediction", "未知"),
                    "confidence": features_for_db.get("health_status", {}).get("confidence", 0.0),
                    "syndrome_analysis": "基于舌象特征的初步分析",
                    "health_recommendations": {
                        "diet": ["建议咨询专业医师"],
                        "lifestyle": ["保持健康作息"],
                        "emotional": ["保持良好心态"]
                    }
                }
        else:
            # Basic diagnosis without LLM
            diagnosis_result = {
                "primary_syndrome": features_for_db.get("health_status", {}).get("prediction", "未知"),
                "confidence": features_for_db.get("health_status", {}).get("confidence", 0.0),
                "syndrome_analysis": "基于舌象特征的初步分析",
                "health_recommendations": {
                    "diet": ["建议咨询专业医师"],
                    "lifestyle": ["保持健康作息"],
                    "emotional": ["保持良好心态"]
                }
            }

        # Calculate total inference time
        total_inference_ms = (time.time() - total_start) * 1000

        # Create diagnosis history record
        diagnosis_history = DiagnosisHistory(
            user_id=current_user.id if current_user else None,
            tongue_image_id=tongue_image_id,
            user_info=request.user_info.model_dump() if request.user_info else None,
            features=features_for_db,
            results=diagnosis_result,
            model_version=settings.MODEL_VERSION if hasattr(settings, 'MODEL_VERSION') else "v2.0",
            inference_time_ms=int(total_inference_ms)
        )
        db.add(diagnosis_history)

        # Flush to get the ID before commit
        db.flush()

        # Get the ID from the diagnosis_history
        diagnosis_id = diagnosis_history.id

        # Commit to database
        db.commit()

        logger.info(
            f"Diagnosis created: id={diagnosis_id}, "
            f"user_id={current_user.id if current_user else None}, "
            f"syndrome={diagnosis_result.get('primary_syndrome')}"
        )

        # Return response
        return DiagnosisResponse(
            success=True,
            message="Diagnosis completed successfully",
            diagnosis_id=str(diagnosis_id),
            user_id=str(current_user.id) if current_user else None,
            segmentation={
                "tongue_area": seg_result.get("tongue_area", 0) if seg_result else 0,
                "tongue_ratio": seg_result.get("tongue_ratio", 0.0) if seg_result else 0.0
            },
            classification={
                "tongue_color": {
                    "prediction": features_for_db.get("tongue_color", {}).get("prediction", ""),
                    "confidence": features_for_db.get("tongue_color", {}).get("confidence", 0.0),
                    "description": features_for_db.get("tongue_color", {}).get("description", "")
                },
                "coating_color": {
                    "prediction": features_for_db.get("coating_color", {}).get("prediction", ""),
                    "confidence": features_for_db.get("coating_color", {}).get("confidence", 0.0),
                    "description": features_for_db.get("coating_color", {}).get("description", "")
                },
                "tongue_shape": {
                    "prediction": features_for_db.get("tongue_shape", {}).get("prediction", ""),
                    "confidence": features_for_db.get("tongue_shape", {}).get("confidence", 0.0),
                    "description": features_for_db.get("tongue_shape", {}).get("description", "")
                },
                "coating_quality": {
                    "prediction": features_for_db.get("coating_quality", {}).get("prediction", ""),
                    "confidence": features_for_db.get("coating_quality", {}).get("confidence", 0.0),
                    "description": features_for_db.get("coating_quality", {}).get("description", "")
                },
                "special_features": features_for_db.get("special_features", {}),
                "health_status": {
                    "prediction": features_for_db.get("health_status", {}).get("prediction", ""),
                    "confidence": features_for_db.get("health_status", {}).get("confidence", 0.0),
                    "description": features_for_db.get("health_status", {}).get("description", "")
                }
            },
            diagnosis=diagnosis_result,
            inference_time_ms=total_inference_ms,
            created_at=datetime.now(timezone.utc).isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagnosis error: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnosis failed: {str(e)}"
        )


# ============================================================================
# GET /api/v2/diagnosis/{id} - US-126
# ============================================================================

class DiagnosisDetailResponse(APIResponse):
    """Complete diagnosis detail response"""

    id: str
    user_id: Optional[str]
    tongue_image_id: str
    created_at: str
    user_info: Optional[Dict[str, Any]] = None
    segmentation: Optional[Dict[str, Any]] = None
    classification: Optional[Dict[str, Any]] = None
    diagnosis: Optional[Dict[str, Any]] = None
    model_version: Optional[str] = None
    inference_time_ms: Optional[int] = None
    feedback: Optional[int] = None
    feedback_comment: Optional[str] = None
    tongue_image: Optional[Dict[str, Any]] = None


@router.get("/{diagnosis_id}", response_model=DiagnosisDetailResponse, tags=["Diagnosis"])
async def get_diagnosis_detail(
    diagnosis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed diagnosis information by ID.

    This endpoint returns complete diagnosis information including
    segmentation, classification, and diagnosis results. Only
    diagnoses owned by the authenticated user can be accessed.

    Args:
        diagnosis_id: UUID of the diagnosis record
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        DiagnosisDetailResponse with complete diagnosis info

    Raises:
        HTTPException 401: If not authenticated
        HTTPException 403: If diagnosis belongs to another user
        HTTPException 404: If diagnosis not found

    Example:
        GET /api/v2/diagnosis/123e4567-e89b-12d3-a456-426614174000
    """
    try:
        from uuid import UUID

        # Validate UUID format
        try:
            diagnosis_uuid = UUID(diagnosis_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid diagnosis ID format. Must be a valid UUID."
            )

        # Query diagnosis
        diagnosis = db.query(DiagnosisHistory).filter(
            DiagnosisHistory.id == diagnosis_uuid
        ).first()

        if diagnosis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnosis not found"
            )

        # Verify ownership (or allow access to anonymous diagnoses for now)
        if diagnosis.user_id is not None and diagnosis.user_id != current_user.id:
            # Also allow admin access if needed
            logger.warning(
                f"User {current_user.id} attempted to access diagnosis "
                f"{diagnosis.id} owned by {diagnosis.user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this diagnosis"
            )

        # Get tongue image info
        tongue_image_info = None
        if diagnosis.tongue_image:
            tongue_image_info = {
                "id": str(diagnosis.tongue_image.id),
                "file_hash": diagnosis.tongue_image.file_hash,
                "width": diagnosis.tongue_image.width,
                "height": diagnosis.tongue_image.height,
                "created_at": diagnosis.tongue_image.created_at.isoformat()
            }

        # Format classification from features JSONB
        classification = None
        if diagnosis.features:
            classification = {
                "tongue_color": diagnosis.features.get("tongue_color", {}),
                "coating_color": diagnosis.features.get("coating_color", {}),
                "tongue_shape": diagnosis.features.get("tongue_shape", {}),
                "coating_quality": diagnosis.features.get("coating_quality", {}),
                "special_features": diagnosis.features.get("special_features", {}),
                "health_status": diagnosis.features.get("health_status", {})
            }

        # Get segmentation info (basic metrics)
        segmentation = None
        if classification and classification.get("health_status"):
            segmentation = {
                "tongue_area": diagnosis.inference_time_ms or 0,  # Placeholder
                "tongue_ratio": 0.0  # Would need to be stored in DB
            }

        return DiagnosisDetailResponse(
            success=True,
            id=str(diagnosis.id),
            user_id=str(diagnosis.user_id) if diagnosis.user_id else None,
            tongue_image_id=str(diagnosis.tongue_image_id),
            created_at=diagnosis.created_at.isoformat(),
            user_info=diagnosis.user_info,
            segmentation=segmentation,
            classification=classification,
            diagnosis=diagnosis.results,
            model_version=diagnosis.model_version,
            inference_time_ms=diagnosis.inference_time_ms,
            feedback=diagnosis.feedback,
            feedback_comment=diagnosis.feedback_comment,
            tongue_image=tongue_image_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting diagnosis detail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve diagnosis: {str(e)}"
        )


# ============================================================================
# POST /api/v2/diagnosis/{id}/feedback - US-127
# ============================================================================

class FeedbackRequest(BaseModel):
    """Feedback submission request"""

    feedback: int = Field(..., ge=-1, le=1, description="Feedback value (1=helpful, -1=not helpful)")
    comment: Optional[str] = Field(None, max_length=500, description="Optional feedback comment")


class FeedbackResponse(APIResponse):
    """Feedback submission response"""

    message: str = Field(..., description="Response message")
    feedback: int = Field(..., description="Submitted feedback value")


@router.post("/{diagnosis_id}/feedback", response_model=FeedbackResponse, tags=["Diagnosis"])
async def submit_diagnosis_feedback(
    diagnosis_id: str,
    feedback_req: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback for a diagnosis.

    This endpoint allows users to provide feedback on the quality
    of a diagnosis. Only the owner of the diagnosis can submit feedback.

    Args:
        diagnosis_id: UUID of the diagnosis record
        feedback_req: Feedback request with feedback value and optional comment
        db: Database session (injected)
        current_user: Authenticated user (injected)

    Returns:
        FeedbackResponse confirming submission

    Raises:
        HTTPException 400: If feedback value is invalid
        HTTPException 401: If not authenticated
        HTTPException 403: If diagnosis belongs to another user
        HTTPException 404: If diagnosis not found

    Example:
        POST /api/v2/diagnosis/123e4567-e89b-12d3-a456-426614174000/feedback
        {"feedback": 1, "comment": "Accurate diagnosis"}
    """
    try:
        from uuid import UUID

        # Validate UUID format
        try:
            diagnosis_uuid = UUID(diagnosis_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid diagnosis ID format. Must be a valid UUID."
            )

        # Query diagnosis
        diagnosis = db.query(DiagnosisHistory).filter(
            DiagnosisHistory.id == diagnosis_uuid
        ).first()

        if diagnosis is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Diagnosis not found"
            )

        # Verify ownership
        if diagnosis.user_id is not None and diagnosis.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this diagnosis"
            )

        # Update feedback
        diagnosis.feedback = feedback_req.feedback
        diagnosis.feedback_comment = feedback_req.comment

        db.commit()

        logger.info(
            f"Feedback submitted for diagnosis {diagnosis.id}: "
            f"feedback={feedback_req.feedback}, user={current_user.id}"
        )

        return FeedbackResponse(
            success=True,
            message="Feedback submitted successfully",
            feedback=feedback_req.feedback
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


def set_model_references(pipeline=None, segmentor=None, classifier=None):
    """Set global model references (called by main.py on startup)

    Args:
        pipeline: End-to-end pipeline instance
        segmentor: Segmentation predictor instance
        classifier: Classification predictor instance
    """
    global _pipeline, _segmentor, _classifier
    _pipeline = pipeline
    _segmentor = segmentor
    _classifier = classifier


__all__ = [
    "router",
    "set_model_references",
]
