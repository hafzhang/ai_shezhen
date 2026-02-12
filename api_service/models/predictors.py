#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模型预测器包装类

Wrapper classes for ML model predictors used by the API service.

Author: Ralph Agent
Date: 2026-02-12
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
from PIL import Image
import cv2
import logging

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class SegmentationPredictorWrapper:
    """分割模型预测器包装类

    Wraps TongueSegmentationPredictor for API use.
    """

    def __init__(
        self,
        model_path: str,
        input_size: tuple = (512, 512),
        use_fp16: bool = False,
        device: str = 'cpu'
    ):
        """Initialize segmentation predictor wrapper

        Args:
            model_path: Path to model weights
            input_size: Input image size
            use_fp16: Whether to use FP16 inference
            device: Device to run on
        """
        from models.pipeline.segmentation import TongueSegmentationPredictor

        self.predictor = TongueSegmentationPredictor(
            model_path=model_path,
            input_size=input_size,
            use_fp16=use_fp16,
            device=device
        )
        self.input_size = input_size

    def predict(
        self,
        image: np.ndarray,
        return_mask: bool = True,
        return_overlay: bool = False
    ) -> Dict[str, Any]:
        """Run segmentation prediction

        Args:
            image: Input image (BGR numpy array)
            return_mask: Whether to return mask
            return_overlay: Whether to return overlay image

        Returns:
            Dictionary with prediction results
        """
        return self.predictor.predict(
            image,
            return_mask=return_mask,
            return_overlay=return_overlay
        )


class ClassificationPredictorWrapper:
    """分类模型预测器包装类

    Wraps TongueClassificationPredictor for API use.
    """

    def __init__(
        self,
        model_path: str,
        input_size: tuple = (224, 224),
        use_fp16: bool = False,
        device: str = 'cpu'
    ):
        """Initialize classification predictor wrapper

        Args:
            model_path: Path to model weights
            input_size: Input image size
            use_fp16: Whether to use FP16 inference
            device: Device to run on
        """
        from models.pipeline.classification import TongueClassificationPredictor

        self.predictor = TongueClassificationPredictor(
            model_path=model_path,
            input_size=input_size,
            use_fp16=use_fp16,
            device=device
        )
        self.input_size = input_size

    def predict(self, image: np.ndarray) -> Dict[str, Any]:
        """Run classification prediction

        Args:
            image: Input image (BGR numpy array)

        Returns:
            Dictionary with prediction results
        """
        return self.predictor.predict(image)


class PipelineWrapper:
    """端到端Pipeline包装类

    Wraps EndToEndPipeline for API use.
    """

    def __init__(
        self,
        seg_model_path: str,
        clas_model_path: str,
        use_fp16: bool = False,
        device: str = 'cpu'
    ):
        """Initialize pipeline wrapper

        Args:
            seg_model_path: Path to segmentation model
            clas_model_path: Path to classification model
            use_fp16: Whether to use FP16 inference
            device: Device to run on
        """
        from models.pipeline.pipeline import EndToEndPipeline

        self.pipeline = EndToEndPipeline(
            seg_model_path=seg_model_path,
            clas_model_path=clas_model_path,
            use_fp16=use_fp16,
            device=device
        )

    def predict(
        self,
        image: np.ndarray,
        return_intermediates: bool = False
    ) -> Dict[str, Any]:
        """Run end-to-end prediction

        Args:
            image: Input image (BGR numpy array)
            return_intermediates: Whether to return intermediate results

        Returns:
            Dictionary with complete prediction results
        """
        return self.pipeline.predict(
            image,
            return_intermediates=return_intermediates
        )

    def format_for_api(
        self,
        prediction_result: Dict[str, Any],
        image_id: str = None
    ) -> Dict[str, Any]:
        """Format prediction for API response

        Args:
            prediction_result: Result from predict()
            image_id: Optional image identifier

        Returns:
            API-formatted response
        """
        return self.pipeline.format_for_api(prediction_result, image_id)


def create_predictors(settings) -> tuple:
    """Factory function to create all predictor instances

    Args:
        settings: Application settings object

    Returns:
        Tuple of (segmentor, classifier, pipeline)
    """
    base_dir = settings.BASE_DIR
    seg_path = str(base_dir / settings.SEGMENT_MODEL_PATH)
    clas_path = str(base_dir / settings.CLASSIFY_MODEL_PATH)

    segmentor = None
    classifier = None
    pipeline = None

    # Check if model files exist
    if Path(seg_path).exists():
        try:
            segmentor = SegmentationPredictorWrapper(
                model_path=seg_path,
                input_size=(settings.SEGMENT_INPUT_SIZE, settings.SEGMENT_INPUT_SIZE),
                use_fp16=settings.USE_FP16,
                device=settings.INFERENCE_DEVICE
            )
            logger.info("Segmentation predictor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize segmentation predictor: {e}")

    if Path(clas_path).exists():
        try:
            classifier = ClassificationPredictorWrapper(
                model_path=clas_path,
                input_size=(settings.CLASSIFY_INPUT_SIZE, settings.CLASSIFY_INPUT_SIZE),
                use_fp16=settings.USE_FP16,
                device=settings.INFERENCE_DEVICE
            )
            logger.info("Classification predictor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize classification predictor: {e}")

    if segmentor and classifier:
        try:
            pipeline = PipelineWrapper(
                seg_model_path=seg_path,
                clas_model_path=clas_path,
                use_fp16=settings.USE_FP16,
                device=settings.INFERENCE_DEVICE
            )
            logger.info("End-to-end pipeline initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")

    return segmentor, classifier, pipeline
