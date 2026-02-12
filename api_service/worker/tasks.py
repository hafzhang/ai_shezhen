#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Celery异步任务定义

Celery task definitions for background processing.
Implements segmentation, classification, diagnosis, and batch processing tasks.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import time
import base64
import io
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded, Retry

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api_service.worker.celery_app import get_celery_app
from api_service.core.config import settings
from api_service.core.logging_config import get_audit_logger

logger = logging.getLogger(__name__)
audit_logger = get_audit_logger()

# Get Celery app
celery_app = get_celery_app()


# ============================================================================
# 自定义任务基类
# ============================================================================

class BaseModelTask(Task):
    """自定义任务基类，提供模型访问和错误处理"""

    _segmentor = None
    _classifier = None
    _pipeline = None

    @property
    def segmentor(self):
        """获取分割模型实例"""
        if self._segmentor is None:
            try:
                from models.pipeline import TongueSegmentationPredictor
                seg_model_path = os.getenv("SEGMENT_MODEL_PATH", "models/deploy/segment_fp16/model_fp16.pdparams")
                use_fp16 = os.getenv("USE_FP16", "true").lower() == "true"
                device = os.getenv("INFERENCE_DEVICE", "cpu")

                if Path(seg_model_path).exists():
                    self._segmentor = TongueSegmentationPredictor(
                        model_path=seg_model_path,
                        input_size=(512, 512),
                        use_fp16=use_fp16,
                        device=device
                    )
                    logger.info("Segmentation model loaded in worker")
            except Exception as e:
                logger.error(f"Failed to load segmentation model: {e}")
        return self._segmentor

    @property
    def classifier(self):
        """获取分类模型实例"""
        if self._classifier is None:
            try:
                from models.pipeline import TongueClassificationPredictor
                clas_model_path = os.getenv("CLASSIFY_MODEL_PATH", "models/deploy/classify_fp16/model_fp16.pdparams")
                use_fp16 = os.getenv("USE_FP16", "true").lower() == "true"
                device = os.getenv("INFERENCE_DEVICE", "cpu")

                if Path(clas_model_path).exists():
                    self._classifier = TongueClassificationPredictor(
                        model_path=clas_model_path,
                        input_size=(224, 224),
                        use_fp16=use_fp16,
                        device=device
                    )
                    logger.info("Classification model loaded in worker")
            except Exception as e:
                logger.error(f"Failed to load classification model: {e}")
        return self._classifier

    @property
    def pipeline(self):
        """获取端到端pipeline实例"""
        if self._pipeline is None:
            try:
                from models.pipeline import EndToEndPipeline
                seg_model_path = os.getenv("SEGMENT_MODEL_PATH", "models/deploy/segment_fp16/model_fp16.pdparams")
                clas_model_path = os.getenv("CLASSIFY_MODEL_PATH", "models/deploy/classify_fp16/model_fp16.pdparams")
                use_fp16 = os.getenv("USE_FP16", "true").lower() == "true"
                device = os.getenv("INFERENCE_DEVICE", "cpu")

                seg_path = Path(seg_model_path)
                clas_path = Path(clas_model_path)

                if seg_path.exists() and clas_path.exists():
                    self._pipeline = EndToEndPipeline(
                        seg_model_path=seg_model_path,
                        clas_model_path=clas_model_path,
                        use_fp16=use_fp16,
                        device=device
                    )
                    logger.info("End-to-end pipeline loaded in worker")
            except Exception as e:
                logger.error(f"Failed to load pipeline: {e}")
        return self._pipeline

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的回调"""
        logger.error(f"Task {task_id} failed: {exc}")
        audit_logger.error(f"task_id={task_id}, status=failed, error={str(exc)}")

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的回调"""
        logger.info(f"Task {task_id} completed successfully")
        audit_logger.info(f"task_id={task_id}, status=success")


# ============================================================================
# 图像解码/编码工具函数
# ============================================================================

def decode_base64_image(image_data: str) -> np.ndarray:
    """Decode base64 encoded image to numpy array"""
    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        image_np = np.array(image)
        if len(image_np.shape) == 3 and image_np.shape[2] == 4:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2BGR)
        elif len(image_np.shape) == 3:
            image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

        return image_np
    except Exception as e:
        raise ValueError(f"Invalid image data: {str(e)}")


def encode_image_to_base64(image: np.ndarray, format: str = "png") -> str:
    """Encode numpy array image to base64 string"""
    try:
        from PIL import Image
        import cv2

        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image

        pil_image = Image.fromarray(image_rgb)
        buffer = io.BytesIO()
        pil_image.save(buffer, format=format.upper())
        buffer.seek(0)

        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/{format};base64,{image_base64}"
    except Exception as e:
        logger.error(f"Failed to encode image: {e}")
        return ""


# ============================================================================
# 分割任务
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseModelTask,
    name="api_service.worker.tasks.segment_task",
    max_retries=3,
    soft_time_limit=30,
)
def segment_task(
    self,
    image_data: str,
    image_id: Optional[str] = None,
    return_mask: bool = True,
    return_overlay: bool = False,
) -> Dict[str, Any]:
    """
    异步舌体分割任务

    Args:
        image_data: Base64编码的图像
        image_id: 图像标识符
        return_mask: 是否返回mask
        return_overlay: 是否返回叠加图像

    Returns:
        分割结果字典
    """
    start_time = time.time()

    try:
        # Decode image
        image = decode_base64_image(image_data)

        # Get segmentor
        segmentor = self.segmentor
        if segmentor is None:
            return {
                "success": False,
                "error": "model_not_loaded",
                "message": "Segmentation model not available",
                "image_id": image_id
            }

        # Run segmentation
        result = segmentor.predict(
            image,
            return_mask=return_mask,
            return_overlay=return_overlay
        )

        # Encode results
        mask_base64 = None
        overlay_base64 = None

        if return_mask and 'mask' in result:
            mask_base64 = encode_image_to_base64(result['mask'])

        if return_overlay and 'overlay' in result:
            overlay_base64 = encode_image_to_base64(result['overlay'])

        inference_time = time.time() - start_time

        return {
            "success": True,
            "image_id": image_id,
            "mask": mask_base64,
            "overlay": overlay_base64,
            "tongue_area": int(result.get('tongue_area', 0)),
            "tongue_ratio": float(result.get('tongue_ratio', 0.0)),
            "inference_time_ms": inference_time * 1000,
            "task_id": self.request.id
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"Segment task {self.request.id} timed out")
        raise segment_task.retry(countdown=1, exc=SoftTimeLimitExceeded())

    except Exception as e:
        logger.error(f"Segment task error: {e}", exc_info=True)
        raise segment_task.retry(countdown=2 ** self.request.retries)


# ============================================================================
# 分类任务
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseModelTask,
    name="api_service.worker.tasks.classify_task",
    max_retries=3,
    soft_time_limit=30,
)
def classify_task(
    self,
    image_data: str,
    image_id: Optional[str] = None,
    crop_to_tongue: bool = True,
) -> Dict[str, Any]:
    """
    异步舌象分类任务

    Args:
        image_data: Base64编码的图像
        image_id: 图像标识符
        crop_to_tongue: 是否先分割裁剪

    Returns:
        分类结果字典
    """
    start_time = time.time()

    try:
        # Decode image
        image = decode_base64_image(image_data)

        # Get classifier
        classifier = self.classifier
        if classifier is None:
            return {
                "success": False,
                "error": "model_not_loaded",
                "message": "Classification model not available",
                "image_id": image_id
            }

        # Optionally crop to tongue area first
        if crop_to_tongue:
            segmentor = self.segmentor
            if segmentor:
                seg_result = segmentor.predict(image, return_mask=True)
                mask = seg_result['mask']

                import cv2
                contours, _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    x, y, w, h = cv2.boundingRect(largest_contour)

                    padding = max(w, h) // 5
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(image.shape[1], x + w + padding)
                    y2 = min(image.shape[0], y + h + padding)

                    image = image[y1:y2, x1:x2]

        # Run classification
        result = classifier.predict(image)

        inference_time = time.time() - start_time

        return {
            "success": True,
            "image_id": image_id,
            "classification": result.get('results'),
            "inference_time_ms": inference_time * 1000,
            "task_id": self.request.id
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"Classify task {self.request.id} timed out")
        raise classify_task.retry(countdown=1, exc=SoftTimeLimitExceeded())

    except Exception as e:
        logger.error(f"Classify task error: {e}", exc_info=True)
        raise classify_task.retry(countdown=2 ** self.request.retries)


# ============================================================================
# 诊断任务
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseModelTask,
    name="api_service.worker.tasks.diagnosis_task",
    max_retries=3,
    soft_time_limit=60,
)
def diagnosis_task(
    self,
    image_data: str,
    image_id: Optional[str] = None,
    user_info: Optional[Dict[str, Any]] = None,
    enable_llm_diagnosis: bool = True,
    enable_rule_fallback: bool = True,
    return_mask: bool = False,
    return_overlay: bool = False,
) -> Dict[str, Any]:
    """
    异步端到端诊断任务

    Args:
        image_data: Base64编码的图像
        image_id: 图像标识符
        user_info: 用户信息
        enable_llm_diagnosis: 是否启用LLM诊断
        enable_rule_fallback: 是否启用规则库兜底
        return_mask: 是否返回mask
        return_overlay: 是否返回叠加图像

    Returns:
        诊断结果字典
    """
    total_start = time.time()
    timing = {}

    try:
        # Decode image
        image = decode_base64_image(image_data)

        # Get pipeline
        pipeline = self.pipeline
        if pipeline is None:
            return {
                "success": False,
                "error": "model_not_loaded",
                "message": "Pipeline not available",
                "image_id": image_id
            }

        # Run end-to-end pipeline
        result = pipeline.predict(image, return_intermediates=False)

        if not result.get('success', True):
            return {
                "success": False,
                "error": result.get('error', 'unknown_error'),
                "message": result.get('message', 'Prediction failed'),
                "image_id": image_id
            }

        timing_breakdown = result.get('timing_breakdown', {})

        # Encode mask/overlay if requested
        seg_result = {}
        if return_mask or return_overlay:
            from models.pipeline import TongueSegmentationPredictor
            segmentor = self.segmentor
            if segmentor:
                seg_raw = segmentor.predict(image, return_mask=True, return_overlay=True)

                if return_mask:
                    seg_result['mask'] = encode_image_to_base64(seg_raw.get('mask'))
                if return_overlay:
                    seg_result['overlay'] = encode_image_to_base64(seg_raw.get('overlay'))

                seg_result['tongue_area'] = seg_raw.get('tongue_area', 0)
                seg_result['tongue_ratio'] = seg_raw.get('tongue_ratio', 0.0)

        total_time = (time.time() - total_start) * 1000

        return {
            "success": True,
            "image_id": image_id,
            "segmentation": seg_result if seg_result else None,
            "classification": result.get('classification'),
            "diagnosis": None,  # LLM diagnosis handled separately
            "used_fallback": False,
            "inference_time_ms": total_time,
            "timing_breakdown": timing_breakdown,
            "task_id": self.request.id
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"Diagnosis task {self.request.id} timed out")
        raise diagnosis_task.retry(countdown=1, exc=SoftTimeLimitExceeded())

    except Exception as e:
        logger.error(f"Diagnosis task error: {e}", exc_info=True)
        raise diagnosis_task.retry(countdown=2 ** self.request.retries)


# ============================================================================
# 批量处理任务
# ============================================================================

@celery_app.task(
    bind=True,
    base=BaseModelTask,
    name="api_service.worker.tasks.batch_segment_task",
    max_retries=2,
    soft_time_limit=120,
)
def batch_segment_task(
    self,
    images: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    批量分割任务

    Args:
        images: 图像列表，每个元素包含 {image_id, image_data}

    Returns:
        批量处理结果
    """
    start_time = time.time()
    results = []
    success_count = 0
    failure_count = 0

    try:
        segmentor = self.segmentor
        if segmentor is None:
            return {
                "success": False,
                "error": "model_not_loaded",
                "results": []
            }

        for item in images:
            try:
                image_data = item.get('image_data')
                image_id = item.get('image_id')

                result = segment_task.apply_async(
                    args=[image_data, image_id, True, False]
                )
                results.append({
                    "image_id": image_id,
                    "task_id": result.id,
                    "status": "pending"
                })
                success_count += 1

            except Exception as e:
                logger.error(f"Failed to queue segment task for {item.get('image_id')}: {e}")
                results.append({
                    "image_id": item.get('image_id'),
                    "error": str(e),
                    "status": "failed"
                })
                failure_count += 1

        processing_time = time.time() - start_time

        return {
            "success": True,
            "results": results,
            "total_count": len(images),
            "success_count": success_count,
            "failure_count": failure_count,
            "processing_time_ms": processing_time * 1000,
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Batch segment task error: {e}", exc_info=True)
        raise batch_segment_task.retry(countdown=2 ** self.request.retries)


@celery_app.task(
    bind=True,
    base=BaseModelTask,
    name="api_service.worker.tasks.batch_classify_task",
    max_retries=2,
    soft_time_limit=120,
)
def batch_classify_task(
    self,
    images: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    批量分类任务

    Args:
        images: 图像列表，每个元素包含 {image_id, image_data}

    Returns:
        批量处理结果
    """
    start_time = time.time()
    results = []
    success_count = 0
    failure_count = 0

    try:
        classifier = self.classifier
        if classifier is None:
            return {
                "success": False,
                "error": "model_not_loaded",
                "results": []
            }

        for item in images:
            try:
                image_data = item.get('image_data')
                image_id = item.get('image_id')

                result = classify_task.apply_async(
                    args=[image_data, image_id, True]
                )
                results.append({
                    "image_id": image_id,
                    "task_id": result.id,
                    "status": "pending"
                })
                success_count += 1

            except Exception as e:
                logger.error(f"Failed to queue classify task for {item.get('image_id')}: {e}")
                results.append({
                    "image_id": item.get('image_id'),
                    "error": str(e),
                    "status": "failed"
                })
                failure_count += 1

        processing_time = time.time() - start_time

        return {
            "success": True,
            "results": results,
            "total_count": len(images),
            "success_count": success_count,
            "failure_count": failure_count,
            "processing_time_ms": processing_time * 1000,
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Batch classify task error: {e}", exc_info=True)
        raise batch_classify_task.retry(countdown=2 ** self.request.retries)


# ============================================================================
# LLM诊断任务
# ============================================================================

@celery_app.task(
    bind=True,
    name="api_service.worker.tasks.llm_diagnosis_task",
    max_retries=3,
    soft_time_limit=30,
    rate_limit="10/m",
)
def llm_diagnosis_task(
    self,
    classification_result: Dict[str, Any],
    user_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    LLM诊断任务（调用文心一言API）

    Args:
        classification_result: 分类结果
        user_info: 用户信息

    Returns:
        LLM诊断结果
    """
    start_time = time.time()

    try:
        # TODO: Implement LLM diagnosis using Wenxin API
        # This will be implemented in a separate task

        logger.info(f"LLM diagnosis task {self.request.id} - classification: {classification_result}")

        processing_time = time.time() - start_time

        return {
            "success": True,
            "diagnosis": {
                "syndrome_analysis": {
                    "possible_syndromes": [],
                    "primary_syndrome": None,
                    "syndrome_description": "LLM诊断待实现"
                },
                "health_recommendations": {
                    "dietary": [],
                    "lifestyle": [],
                    "tcm_therapy": [],
                    "medical_consultation": "请咨询专业中医师"
                },
                "disclaimer": {
                    "ai_assistant_only": True,
                    "not_medical_advice": True
                }
            },
            "processing_time_ms": processing_time * 1000,
            "task_id": self.request.id
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"LLM diagnosis task {self.request.id} timed out")
        return {
            "success": False,
            "error": "timeout",
            "message": "LLM diagnosis timed out"
        }

    except Exception as e:
        logger.error(f"LLM diagnosis task error: {e}", exc_info=True)
        raise llm_diagnosis_task.retry(countdown=2 ** self.request.retries)


# ============================================================================
# 维护任务
# ============================================================================

@celery_app.task(
    name="api_service.worker.tasks.cleanup_task",
)
def cleanup_task():
    """
    定期清理过期任务结果

    由Celery Beat定期调用
    """
    try:
        from datetime import datetime, timedelta

        # Log cleanup
        logger.info(f"Running cleanup task at {datetime.now()}")

        # TODO: Implement actual cleanup logic
        # - Delete old task results from Redis
        # - Clean up temporary files
        # - Archive old logs

        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "message": "Cleanup completed"
        }

    except Exception as e:
        logger.error(f"Cleanup task error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
