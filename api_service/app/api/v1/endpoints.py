#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v1 端点定义

RESTful API endpoints for tongue segmentation, classification, and diagnosis.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import time
import base64
import io
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
import numpy as np
from PIL import Image
import cv2
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from api_service.schemas.schemas import (
    SegmentRequest,
    SegmentResponse,
    ClassifyRequest,
    ClassifyResponse,
    DiagnosisRequest,
    DiagnosisResponse,
    HealthResponse,
    ErrorResponse,
    SyndromeInfo,
    SyndromeAnalysis,
    AnomalyDetection,
    HealthRecommendations,
    ConfidenceAnalysis,
    Disclaimer,
    LDiagnosisResult
)
from api_service.core.config import settings
from api_service.core.logging_config import (
    log_api_request,
    log_api_response,
    log_diagnosis_request,
    log_error,
    AuditContext
)
from api_service.core.rule_based_diagnosis import (
    diagnose_from_classification,
    RuleDiagnosisResult
)
from api_service.core.case_retrieval import (
    retrieve_similar_cases_from_classification,
    RetrievalResult
)

logger = logging.getLogger(__name__)

# Create API router
api_router = APIRouter()

# Global model references (set by main.py on startup)
_pipeline = None
_segmentor = None
_classifier = None


def get_pipeline():
    """Get end-to-end pipeline instance"""
    global _pipeline
    return _pipeline


def get_segmentor():
    """Get segmentation predictor instance"""
    global _segmentor
    return _segmentor


def get_classifier():
    """Get classification predictor instance"""
    global _classifier
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
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2BGR)
        elif len(image_np.shape) == 3:
            # RGB to BGR
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

        return image_np

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image data: {str(e)}"
        )


def encode_image_to_base64(image: np.ndarray, format: str = "png") -> str:
    """Encode numpy array image to base64

    Args:
        image: numpy array (BGR format)
        format: Image format (png/jpeg)

    Returns:
        Base64 encoded image string
    """
    try:
        # Convert BGR to RGB for PIL
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image

        # Convert to PIL Image
        pil_image = Image.fromarray(image_rgb)

        # Save to bytes
        buffer = io.BytesIO()
        pil_image.save(buffer, format=format.upper())
        buffer.seek(0)

        # Encode to base64
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')

        return f"data:image/{format};base64,{image_base64}"

    except Exception as e:
        logger.error(f"Failed to encode image: {e}")
        return ""


# ============================================================================
# 健康检查端点
# ============================================================================

@api_router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    健康检查端点

    检查API服务和模型加载状态。

    返回:
        - status: "healthy" (至少一个模型加载) 或 "degraded" (无模型)
        - models: 各模型加载状态
    """
    models_status = {
        "segmentation": get_segmentor() is not None,
        "classification": get_classifier() is not None,
        "pipeline": get_pipeline() is not None
    }

    health_status = "healthy" if any(models_status.values()) else "degraded"

    return HealthResponse(
        success=True,
        status=health_status,
        models=models_status,
        api_version=settings.API_VERSION
    )


# ============================================================================
# 舌体分割端点
# ============================================================================

@api_router.post("/segment", response_model=SegmentResponse, tags=["Segmentation"])
async def segment_tongue(
    request: SegmentRequest
):
    """
    舌体分割

    使用BiSeNetV2模型对输入图像进行舌体分割。

    请求参数:
        - image: Base64编码的图像数据
        - image_id: 可选的图像标识符
        - return_overlay: 是否返回分割叠加图像
        - return_mask: 是否返回分割mask

    返回:
        - mask: 分割mask (base64编码)
        - overlay: 分割叠加图像 (base64编码)
        - tongue_area: 舌体区域像素数
        - tongue_ratio: 舌体区域占比
        - inference_time_ms: 推理耗时
    """
    start_time = time.time()

    try:
        segmentor = get_segmentor()
        if segmentor is None:
            if settings.MOCK_MODE:
                # Mock response for testing
                return SegmentResponse(
                    success=True,
                    message="Mock mode: segmentation result",
                    image_id=request.image_id,
                    result=SegmentResult(
                        mask=None,
                        overlay=None,
                        tongue_area=100000,
                        tongue_ratio=0.3,
                        inference_time_ms=50.0
                    )
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Segmentation model not loaded"
            )

        # Decode image
        image = decode_base64_image(request.image)

        # Run segmentation
        with AuditContext("segmentation", image_id=request.image_id):
            result = segmentor.predict(
                image,
                return_mask=request.return_mask,
                return_overlay=request.return_overlay
            )

        # Encode results
        mask_base64 = None
        overlay_base64 = None

        if request.return_mask and 'mask' in result:
            mask_base64 = encode_image_to_base64(result['mask'])

        if request.return_overlay and 'overlay' in result:
            overlay_base64 = encode_image_to_base64(result['overlay'])

        # Extract metrics
        tongue_area = int(result.get('tongue_area', 0))
        tongue_ratio = float(result.get('tongue_ratio', 0.0))
        inference_time = float(result.get('inference_time', 0.0))

        return SegmentResponse(
            success=True,
            message="Segmentation completed successfully",
            image_id=request.image_id,
            result=SegmentResult(
                mask=mask_base64,
                overlay=overlay_base64,
                tongue_area=tongue_area,
                tongue_ratio=tongue_ratio,
                inference_time_ms=inference_time * 1000
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Segmentation error: {e}", exc_info=True)
        log_error("segmentation", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Segmentation failed: {str(e)}"
        )


# ============================================================================
# 舌象分类端点
# ============================================================================

@api_router.post("/classify", response_model=ClassifyResponse, tags=["Classification"])
async def classify_tongue(
    request: ClassifyRequest
):
    """
    舌象特征分类

    使用PP-HGNetV2-B4模型对舌象进行多维度特征分类。

    分类维度:
        - 舌色: 淡红舌、红舌、绛紫舌、淡白舌
        - 苔色: 白苔、黄苔、黑苔、花剥苔
        - 舌形: 正常、胖大舌、瘦薄舌
        - 苔质: 薄苔、厚苔、腐苔、腻苔
        - 特征: 红点、裂纹、齿痕
        - 健康: 健康舌、不健康舌

    请求参数:
        - image: Base64编码的图像数据
        - image_id: 可选的图像标识符
        - crop_to_tongue: 是否先进行分割裁剪

    返回:
        - 各维度的预测结果、置信度和描述
        - inference_time_ms: 推理耗时
    """
    start_time = time.time()

    try:
        classifier = get_classifier()
        if classifier is None:
            if settings.MOCK_MODE:
                # Mock response for testing
                from api_service.schemas.schemas import (
                    ClassificationHeadResult,
                    SpecialFeaturesResult
                )
                return ClassifyResponse(
                    success=True,
                    message="Mock mode: classification result",
                    image_id=request.image_id,
                    result=ClassificationResult(
                        tongue_color=ClassificationHeadResult(
                            prediction="淡红舌", confidence=0.85, description="气血调和"
                        ),
                        coating_color=ClassificationHeadResult(
                            prediction="白苔", confidence=0.80, description="薄白苔"
                        ),
                        tongue_shape=ClassificationHeadResult(
                            prediction="正常", confidence=0.90, description="舌体适中"
                        ),
                        coating_quality=ClassificationHeadResult(
                            prediction="薄苔", confidence=0.88, description="苔质薄"
                        ),
                        special_features=SpecialFeaturesResult(
                            red_dots={"present": False, "confidence": 0.0},
                            cracks={"present": False, "confidence": 0.0},
                            teeth_marks={"present": False, "confidence": 0.0}
                        ),
                        health_status=ClassificationHeadResult(
                            prediction="健康舌", confidence=0.87, description="舌象正常"
                        )
                    ),
                    inference_time_ms=100.0
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Classification model not loaded"
            )

        # Decode image
        image = decode_base64_image(request.image)

        # If crop_to_tongue and segmentor is available, crop first
        if request.crop_to_tongue:
            segmentor = get_segmentor()
            if segmentor:
                seg_result = segmentor.predict(image, return_mask=True)
                mask = seg_result['mask']

                # Find bounding box
                contours, _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(largest_contour)

                    # Add padding
                    padding = max(w, h) // 5
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(image.shape[1], x + w + padding)
                    y2 = min(image.shape[0], y + h + padding)

                    # Crop
                    image = image[y1:y2, x1:x2]

        # Run classification
        with AuditContext("classification", image_id=request.image_id):
            result = classifier.predict(image)

        # Format response
        classification = result['results']

        return ClassifyResponse(
            success=True,
            message="Classification completed successfully",
            image_id=request.image_id,
            result=classification,
            inference_time_ms=result.get('inference_time', 0) * 1000
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification error: {e}", exc_info=True)
        log_error("classification", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}"
        )


# ============================================================================
# 端到端诊断端点
# ============================================================================

@api_router.post("/diagnosis", response_model=DiagnosisResponse, tags=["Diagnosis"])
async def diagnosis_tongue(
    request: DiagnosisRequest
):
    """
    端到端舌诊

    完整的舌诊流程：分割 -> 分类 -> (可选) LLM诊断

    请求参数:
        - image: Base64编码的图像数据
        - image_id: 可选的图像标识符
        - user_info: 可选的用户信息 (年龄、性别、症状等)
        - enable_llm_diagnosis: 是否启用LLM诊断
        - enable_rule_fallback: 是否启用本地规则库兜底

    返回:
        - segmentation: 分割结果
        - classification: 分类结果
        - diagnosis: LLM诊断结果 (如果启用)
        - used_fallback: 是否使用了兜底方案
        - inference_time_ms: 总推理耗时
        - timing_breakdown: 各阶段耗时明细
    """
    total_start = time.time()
    timing = {}

    try:
        pipeline = get_pipeline()
        if pipeline is None:
            if settings.MOCK_MODE:
                # Mock response for testing
                from api_service.schemas.schemas import (
                    SegmentResult,
                    ClassificationHeadResult,
                    SpecialFeaturesResult,
                    ClassificationResult,
                    SyndromeInfo,
                    SyndromeAnalysis,
                    AnomalyDetection,
                    HealthRecommendations,
                    ConfidenceAnalysis,
                    Disclaimer,
                    LDiagnosisResult
                )
                return DiagnosisResponse(
                    success=True,
                    message="Mock mode: diagnosis result",
                    image_id=request.image_id,
                    segmentation=SegmentResult(
                        mask=None, overlay=None,
                        tongue_area=100000, tongue_ratio=0.3, inference_time_ms=50.0
                    ),
                    classification=ClassificationResult(
                        tongue_color=ClassificationHeadResult(
                            prediction="淡红舌", confidence=0.85, description="气血调和"
                        ),
                        coating_color=ClassificationHeadResult(
                            prediction="白苔", confidence=0.80, description="薄白苔"
                        ),
                        tongue_shape=ClassificationHeadResult(
                            prediction="正常", confidence=0.90, description="舌体适中"
                        ),
                        coating_quality=ClassificationHeadResult(
                            prediction="薄苔", confidence=0.88, description="苔质薄"
                        ),
                        special_features=SpecialFeaturesResult(
                            red_dots={"present": False, "confidence": 0.0},
                            cracks={"present": False, "confidence": 0.0},
                            teeth_marks={"present": False, "confidence": 0.0}
                        ),
                        health_status=ClassificationHeadResult(
                            prediction="健康舌", confidence=0.87, description="舌象正常"
                        )
                    ),
                    diagnosis=LDiagnosisResult(
                        syndrome_analysis=SyndromeAnalysis(
                            possible_syndromes=[],
                            primary_syndrome=None,
                            secondary_syndromes=[],
                            syndrome_description="健康舌象，无明显病理特征"
                        ),
                        anomaly_detection=AnomalyDetection(
                            detected=False, reason=None, recommendations=[]
                        ),
                        health_recommendations=HealthRecommendations(
                            dietary=["保持均衡饮食", "适量饮水"],
                            lifestyle=["规律作息", "适度运动"],
                            tcm_therapy=["无需特殊治疗"],
                            medical_consultation="定期健康体检即可"
                        ),
                        confidence_analysis=ConfidenceAnalysis(
                            overall_confidence=0.87,
                            confidence_breakdown={"feature_extraction": 0.85},
                            uncertainty_factors=[]
                        ),
                        disclaimer=Disclaimer(
                            ai_assistant_only=True,
                            not_medical_advice=True,
                            consult_doctor_reminder=False,
                            emergency_warning=None
                        )
                    ),
                    used_fallback=False,
                    inference_time_ms=150.0,
                    timing_breakdown={"segmentation_ms": 50.0, "classification_ms": 100.0}
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="End-to-end pipeline not loaded"
            )

        # Decode image
        image = decode_base64_image(request.image)

        # Step 1: Run end-to-end pipeline
        with AuditContext("end_to_end_diagnosis", image_id=request.image_id):
            result = pipeline.predict(image, return_intermediates=False)

        # Check if pipeline succeeded
        if not result.get('success', True):
            error_type = result.get('error', 'unknown_error')
            error_msg = result.get('message', 'Prediction failed')

            return DiagnosisResponse(
                success=False,
                error=error_type,
                detail=error_msg,
                image_id=request.image_id,
                used_fallback=False,
                inference_time_ms=0.0
            )

        # Extract results
        timing_breakdown = result.get('timing_breakdown', {})

        # Format segmentation result
        seg_result = None
        if 'segmentation' in result:
            seg_data = result['segmentation']
            mask_base64 = None
            overlay_base64 = None

            # Encode mask and overlay if requested
            if request.return_mask and 'mask' in result:
                mask_base64 = encode_image_to_base64(seg_data.get('mask'))

            if request.return_overlay and 'overlay' in result:
                overlay_base64 = encode_image_to_base64(seg_data.get('overlay'))

            seg_result = SegmentResult(
                mask=mask_base64,
                overlay=overlay_base64,
                tongue_area=seg_data.get('tongue_area', 0),
                tongue_ratio=seg_data.get('tongue_ratio', 0.0),
                inference_time_ms=timing_breakdown.get('segmentation_ms', 0)
            )

        # Format classification result
        classification = result.get('classification')

        # Step 2: LLM Diagnosis (if enabled)
        diagnosis = None
        used_fallback = False

        if request.enable_llm_diagnosis:
            llm_start = time.time()

            try:
                # TODO: Implement LLM diagnosis (will be added in future tasks)
                # For now, use rule-based fallback directly
                if request.enable_rule_fallback:
                    # Use rule-based diagnosis as fallback
                    rule_result = diagnose_from_classification(classification)

                    # Convert rule result to diagnosis format
                    possible_syndromes = []
                    for match in rule_result.possible_syndromes:
                        possible_syndromes.append(SyndromeInfo(
                            name=match.name,
                            confidence=match.confidence,
                            evidence=f"匹配特征: {', '.join(match.matched_features)}",
                            tcm_theory=rule_result.tcm_theory
                        ))

                    diagnosis = LDiagnosisResult(
                        syndrome_analysis=SyndromeAnalysis(
                            possible_syndromes=possible_syndromes,
                            primary_syndrome=rule_result.primary_syndrome,
                            secondary_syndromes=[m.name for m in rule_result.possible_syndromes[1:3]],
                            syndrome_description=rule_result.syndrome_description
                        ),
                        anomaly_detection=AnomalyDetection(
                            detected=rule_result.confidence < 0.5,
                            reason="置信度较低，建议咨询专业中医师" if rule_result.confidence < 0.5 else None,
                            recommendations=["建议进一步面诊确认"] if rule_result.confidence < 0.5 else []
                        ),
                        health_recommendations=HealthRecommendations(
                            dietary=rule_result.health_recommendations.get("dietary", []),
                            lifestyle=rule_result.health_recommendations.get("lifestyle", []),
                            tcm_therapy=rule_result.health_recommendations.get("tcm_therapy", []),
                            medical_consultation=rule_result.health_recommendations.get("medical_consultation", "")
                        ),
                        confidence_analysis=ConfidenceAnalysis(
                            overall_confidence=rule_result.confidence,
                            confidence_breakdown={
                                "rule_based": rule_result.confidence,
                                "feature_coverage": len(rule_result.used_rules) / 7
                            },
                            uncertainty_factors=[
                                "基于规则库诊断，建议结合LLM诊断提高准确性"
                            ]
                        ),
                        disclaimer=Disclaimer(
                            ai_assistant_only=True,
                            not_medical_advice=True,
                            consult_doctor_reminder=True,
                            emergency_warning=None
                        )
                    )
                    used_fallback = True
                    logger.info(f"Used rule-based fallback: {rule_result.primary_syndrome}")

            except Exception as e:
                logger.warning(f"LLM diagnosis failed: {e}")
                if request.enable_rule_fallback:
                    # Rule-based fallback on error
                    try:
                        rule_result = diagnose_from_classification(classification)

                        possible_syndromes = []
                        for match in rule_result.possible_syndromes:
                            possible_syndromes.append(SyndromeInfo(
                                name=match.name,
                                confidence=match.confidence,
                                evidence=f"匹配特征: {', '.join(match.matched_features)}",
                                tcm_theory=rule_result.tcm_theory
                            ))

                        diagnosis = LDiagnosisResult(
                            syndrome_analysis=SyndromeAnalysis(
                                possible_syndromes=possible_syndromes,
                                primary_syndrome=rule_result.primary_syndrome,
                                secondary_syndromes=[m.name for m in rule_result.possible_syndromes[1:3]],
                                syndrome_description=rule_result.syndrome_description
                            ),
                            anomaly_detection=AnomalyDetection(
                                detected=rule_result.confidence < 0.5,
                                reason="置信度较低，建议咨询专业中医师" if rule_result.confidence < 0.5 else None,
                                recommendations=["建议进一步面诊确认"] if rule_result.confidence < 0.5 else []
                            ),
                            health_recommendations=HealthRecommendations(
                                dietary=rule_result.health_recommendations.get("dietary", []),
                                lifestyle=rule_result.health_recommendations.get("lifestyle", []),
                                tcm_therapy=rule_result.health_recommendations.get("tcm_therapy", []),
                                medical_consultation=rule_result.health_recommendations.get("medical_consultation", "")
                            ),
                            confidence_analysis=ConfidenceAnalysis(
                                overall_confidence=rule_result.confidence,
                                confidence_breakdown={
                                    "rule_based": rule_result.confidence,
                                    "feature_coverage": len(rule_result.used_rules) / 7
                                },
                                uncertainty_factors=[
                                    "LLM诊断失败，使用规则库兜底",
                                    "建议结合临床诊断"
                                ]
                            ),
                            disclaimer=Disclaimer(
                                ai_assistant_only=True,
                                not_medical_advice=True,
                                consult_doctor_reminder=True,
                                emergency_warning=None
                            )
                        )
                    except Exception as fallback_error:
                        logger.error(f"Rule-based fallback also failed: {fallback_error}")
                    used_fallback = True

            timing['llm_ms'] = (time.time() - llm_start) * 1000

        total_time = (time.time() - total_start) * 1000

        return DiagnosisResponse(
            success=True,
            message="Diagnosis completed successfully",
            image_id=request.image_id,
            segmentation=seg_result,
            classification=classification,
            diagnosis=diagnosis,
            used_fallback=used_fallback,
            inference_time_ms=total_time,
            timing_breakdown=timing_breakdown
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagnosis error: {e}", exc_info=True)
        log_error("diagnosis", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnosis failed: {str(e)}"
        )


# ============================================================================
# 文件上传端点 (便捷接口)
# ============================================================================

@api_router.post("/upload/segment", tags=["Upload"])
async def upload_segment(
    file: UploadFile = File(...),
    image_id: Optional[str] = Form(None)
):
    """
    上传图像进行分割 (便捷接口)

    接受multipart/form-data文件上传，返回分割结果。
    """
    # Read file
    contents = await file.read()

    # Encode to base64
    image_base64 = base64.b64encode(contents).decode('utf-8')

    # Create request
    request = SegmentRequest(
        image=image_base64,
        image_id=image_id or file.filename,
        return_overlay=True,
        return_mask=True
    )

    # Call segment endpoint
    return await segment_tongue(request)


@api_router.post("/upload/classify", tags=["Upload"])
async def upload_classify(
    file: UploadFile = File(...),
    image_id: Optional[str] = Form(None)
):
    """
    上传图像进行分类 (便捷接口)

    接受multipart/form-data文件上传，返回分类结果。
    """
    # Read file
    contents = await file.read()

    # Encode to base64
    image_base64 = base64.b64encode(contents).decode('utf-8')

    # Create request
    request = ClassifyRequest(
        image=image_base64,
        image_id=image_id or file.filename,
        crop_to_tongue=True
    )

    # Call classify endpoint
    return await classify_tongue(request)


@api_router.post("/upload/diagnosis", tags=["Upload"])
async def upload_diagnosis(
    file: UploadFile = File(...),
    image_id: Optional[str] = Form(None),
    user_info_json: Optional[str] = Form(None)
):
    """
    上传图像进行完整诊断 (便捷接口)

    接受multipart/form-data文件上传，返回完整诊断结果。
    """
    # Read file
    contents = await file.read()

    # Encode to base64
    image_base64 = base64.b64encode(contents).decode('utf-8')

    # Parse user info if provided
    user_info = None
    if user_info_json:
        import json
        try:
            user_info = json.loads(user_info_json)
        except:
            pass

    # Create request
    request = DiagnosisRequest(
        image=image_base64,
        image_id=image_id or file.filename,
        user_info=user_info,
        enable_llm_diagnosis=True,
        enable_rule_fallback=True
    )

    # Call diagnosis endpoint
    return await diagnosis_tongue(request)
