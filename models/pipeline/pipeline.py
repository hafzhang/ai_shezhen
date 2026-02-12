#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
End-to-End Pipeline for Tongue Diagnosis

Combines segmentation and classification models for complete tongue diagnosis workflow.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Union, List
import numpy as np
from PIL import Image
import cv2
import time
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models.pipeline.segmentation import TongueSegmentationPredictor
from models.pipeline.classification import TongueClassificationPredictor


class EndToEndPipeline:
    """End-to-end pipeline for tongue diagnosis

    Workflow:
    1. Segmentation: Extract tongue region from input image
    2. Classification: Predict tongue features from segmented region
    3. Formatting: Structure output for downstream use (API/LLM)

    Args:
        seg_model_path: Path to segmentation model weights
        clas_model_path: Path to classification model weights
        seg_input_size: Input size for segmentation (default: 512x512)
        clas_input_size: Input size for classification (default: 224x224)
        use_fp16: Whether to use FP16 inference
        device: Device to run inference on ('cpu' or 'gpu')
        extract_tongue: Whether to crop tongue region before classification
        min_tongue_area: Minimum tongue area (pixels) to proceed to classification
    """

    def __init__(
        self,
        seg_model_path: Optional[str] = None,
        clas_model_path: Optional[str] = None,
        seg_input_size: tuple = (512, 512),
        clas_input_size: tuple = (224, 224),
        use_fp16: bool = False,
        device: str = 'cpu',
        extract_tongue: bool = True,
        min_tongue_area: int = 5000
    ):
        self.seg_input_size = seg_input_size
        self.clas_input_size = clas_input_size
        self.use_fp16 = use_fp16
        self.device = device
        self.extract_tongue = extract_tongue
        self.min_tongue_area = min_tongue_area

        # Initialize segmentation predictor
        self.segmentor = TongueSegmentationPredictor(
            model_path=seg_model_path,
            input_size=seg_input_size,
            use_fp16=use_fp16,
            device=device
        )

        # Initialize classification predictor
        self.classifier = TongueClassificationPredictor(
            model_path=clas_model_path,
            input_size=clas_input_size,
            use_fp16=use_fp16,
            device=device
        )

        # Timing statistics
        self.timing = {
            'segmentation': [],
            'classification': [],
            'total': []
        }

    def predict(
        self,
        image: Union[str, np.ndarray, Image.Image],
        return_intermediates: bool = False
    ) -> Dict[str, Any]:
        """Run end-to-end prediction on an image

        Args:
            image: Input image (path, numpy array, or PIL Image)
            return_intermediates: Whether to return intermediate results

        Returns:
            Dictionary with complete diagnosis results
        """
        total_start = time.time()

        # Step 1: Segmentation
        seg_start = time.time()
        seg_result = self.segmentor.predict(
            image,
            return_mask=True,
            return_overlay=True
        )
        seg_time = time.time() - seg_start
        self.timing['segmentation'].append(seg_time)

        # Check segmentation quality
        mask = seg_result['mask']
        tongue_pixels = np.sum(mask == 255)

        if tongue_pixels < self.min_tongue_area:
            # Tongue not found or too small
            return {
                'success': False,
                'error': 'tongue_not_found',
                'message': f'Tongue area ({tongue_pixels} pixels) below minimum ({self.min_tongue_area})',
                'segmentation_result': seg_result
            }

        # Step 2: Extract tongue region (optional)
        if self.extract_tongue:
            clas_start = time.time()

            # Load original image for cropping
            if isinstance(image, str):
                orig_img = cv2.imread(image)
            elif isinstance(image, np.ndarray):
                orig_img = image.copy()
            else:
                orig_img = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)

            # Find bounding box of tongue region
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)

                # Add padding (20%)
                padding = max(w, h) // 5
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(orig_img.shape[1], x + w + padding)
                y2 = min(orig_img.shape[0], y + h + padding)

                # Crop tongue region
                tongue_crop = orig_img[y1:y2, x1:x2]

                # Classification on cropped region
                clas_result = self.classifier.predict(tongue_crop)
            else:
                # Fallback: use original image
                clas_result = self.classifier.predict(image)

            clas_time = time.time() - clas_start
        else:
            # Classification on full image
            clas_start = time.time()
            clas_result = self.classifier.predict(image)
            clas_time = time.time() - clas_start

        self.timing['classification'].append(clas_time)
        total_time = time.time() - total_start
        self.timing['total'].append(total_time)

        # Step 3: Format results
        result = {
            'success': True,
            'segmentation': {
                'mask': mask,
                'overlay': seg_result['overlay'],
                'tongue_area': int(tongue_pixels),
                'tongue_ratio': float(tongue_pixels) / (mask.shape[0] * mask.shape[1]),
                'inference_time': seg_time
            },
            'classification': clas_result['results'],
            'inference_time': total_time,
            'timing_breakdown': {
                'segmentation_ms': seg_time * 1000,
                'classification_ms': clas_time * 1000,
                'total_ms': total_time * 1000
            }
        }

        if return_intermediates:
            result['intermediates'] = {
                'segmentation_raw': seg_result,
                'classification_raw': clas_result
            }

        return result

    def predict_batch(
        self,
        images: List[Union[str, np.ndarray, Image.Image]],
        batch_size: int = 4
    ) -> List[Dict[str, Any]]:
        """Run end-to-end prediction on batch of images

        Args:
            images: List of image paths/arrays
            batch_size: Batch size for processing

        Returns:
            List of prediction results
        """
        results = []

        for image in images:
            result = self.predict(image, return_intermediates=False)
            results.append(result)

        return results

    def format_for_api(
        self,
        prediction_result: Dict[str, Any],
        image_id: str = None
    ) -> Dict[str, Any]:
        """Format prediction result for API response

        Args:
            prediction_result: Result from predict()
            image_id: Optional image identifier

        Returns:
            API-formatted response
        """
        if not prediction_result.get('success', True):
            return {
                'success': False,
                'image_id': image_id,
                'error': prediction_result.get('error', 'unknown_error'),
                'message': prediction_result.get('message', 'Prediction failed')
            }

        # Format classification results
        classification = prediction_result['classification']

        # Build API response
        api_response = {
            'success': True,
            'image_id': image_id,
            'inference_time_ms': prediction_result['timing_breakdown']['total_ms'],
            'diagnosis': {
                'tongue_color': self._format_head_result(classification.get('tongue_color', {})),
                'coating_color': self._format_head_result(classification.get('coating_color', {})),
                'tongue_shape': self._format_head_result(classification.get('tongue_shape', {})),
                'coating_quality': self._format_head_result(classification.get('coating_quality', {})),
                'special_features': self._format_features_result(classification.get('features', {})),
                'health_status': self._format_head_result(classification.get('health', {}))
            },
            'segmentation_info': {
                'tongue_area': prediction_result['segmentation']['tongue_area'],
                'tongue_ratio': prediction_result['segmentation']['tongue_ratio']
            }
        }

        return api_response

    def _format_head_result(self, head_result: Dict) -> Dict[str, Any]:
        """Format single-label head result for API

        Args:
            head_result: Head result dictionary

        Returns:
            Formatted result with prediction and confidence
        """
        if not head_result or 'prediction' not in head_result:
            return {
                'prediction': None,
                'confidence': 0.0,
                'description': 'N/A'
            }

        prediction = head_result['prediction']
        if isinstance(prediction, list) and len(prediction) > 0:
            top = prediction[0]
            return {
                'prediction': top['name'],
                'confidence': round(top['confidence'], 4),
                'description': head_result.get('description', '')
            }

        return {
            'prediction': None,
            'confidence': 0.0,
            'description': 'N/A'
        }

    def _format_features_result(self, features_result: Dict) -> Dict[str, Dict]:
        """Format multi-label features result for API

        Args:
            features_result: Features head result dictionary

        Returns:
            Formatted result with each feature
        """
        features = {
            'red_dots': {'present': False, 'confidence': 0.0},
            'cracks': {'present': False, 'confidence': 0.0},
            'teeth_marks': {'present': False, 'confidence': 0.0}
        }

        if not features_result or 'prediction' not in features_result:
            return features

        predictions = features_result['prediction']
        if isinstance(predictions, list):
            for pred in predictions:
                name = pred.get('name', '')
                conf = pred.get('confidence', 0.0)

                if '红点' in name:
                    features['red_dots'] = {'present': True, 'confidence': round(conf, 4)}
                elif '裂纹' in name:
                    features['cracks'] = {'present': True, 'confidence': round(conf, 4)}
                elif '齿痕' in name:
                    features['teeth_marks'] = {'present': True, 'confidence': round(conf, 4)}

        return features

    def format_for_llm(
        self,
        prediction_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format prediction result for LLM prompt

        Args:
            prediction_result: Result from predict()

        Returns:
            LLM-formatted dictionary for user prompt template
        """
        if not prediction_result.get('success', True):
            return {
                'error': prediction_result.get('error', 'unknown_error'),
                'message': prediction_result.get('message', 'Prediction failed')
            }

        # Use classifier's formatting
        classification_input = {
            'results': prediction_result['classification']
        }
        llm_format = self.classifier.format_for_prompt(classification_input)

        # Add segmentation info
        llm_format['tongue_area'] = prediction_result['segmentation']['tongue_area']
        llm_format['tongue_ratio'] = prediction_result['segmentation']['tongue_ratio']

        return llm_format

    def get_timing_stats(self) -> Dict[str, Any]:
        """Get timing statistics

        Returns:
            Dictionary with min, max, mean timings for each stage
        """
        stats = {}

        for stage, timings in self.timing.items():
            if timings:
                stats[stage] = {
                    'min_ms': min(timings) * 1000,
                    'max_ms': max(timings) * 1000,
                    'mean_ms': np.mean(timings) * 1000,
                    'std_ms': np.std(timings) * 1000,
                    'count': len(timings)
                }

        return stats

    def reset_timing(self):
        """Reset timing statistics"""
        self.timing = {
            'segmentation': [],
            'classification': [],
            'total': []
        }


def create_pipeline(
    seg_model_path: str = None,
    clas_model_path: str = None,
    use_fp16: bool = False
) -> EndToEndPipeline:
    """Factory function to create end-to-end pipeline

    Args:
        seg_model_path: Path to segmentation model weights
        clas_model_path: Path to classification model weights
        use_fp16: Whether to use FP16 inference

    Returns:
        EndToEndPipeline instance
    """
    return EndToEndPipeline(
        seg_model_path=seg_model_path,
        clas_model_path=clas_model_path,
        use_fp16=use_fp16
    )


if __name__ == "__main__":
    # Test end-to-end pipeline
    import sys

    if sys.platform == 'win32':
        import io
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Testing End-to-End Pipeline...")

    # Create pipeline (without model weights for testing)
    pipeline = EndToEndPipeline()

    print(f"Pipeline created:")
    print(f"  Segmentator: {type(pipeline.segmentor.model).__name__}")
    print(f"  Classifier: {type(pipeline.classifier.model).__name__}")
    print(f"  Seg input size: {pipeline.seg_input_size}")
    print(f"  Clas input size: {pipeline.clas_input_size}")
    print(f"  Device: {pipeline.device}")

    # Test with dummy image
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    print("\nRunning test prediction...")
    result = pipeline.predict(test_image, return_intermediates=True)

    print(f"\nPrediction result:")
    print(f"  Success: {result.get('success', False)}")
    print(f"  Tongue area: {result.get('segmentation', {}).get('tongue_area', 'N/A')} pixels")
    print(f"  Inference time: {result.get('inference_time', 0) * 1000:.1f} ms")

    timing = result.get('timing_breakdown', {})
    print(f"  Segmentation: {timing.get('segmentation_ms', 0):.1f} ms")
    print(f"  Classification: {timing.get('classification_ms', 0):.1f} ms")

    # Test API formatting
    api_format = pipeline.format_for_api(result, image_id='test_001')
    print(f"\nAPI format keys: {list(api_format.keys())}")

    # Test LLM formatting
    llm_format = pipeline.format_for_llm(result)
    print(f"LLM format keys: {list(llm_format.keys())}")

    print("\nEnd-to-end pipeline test completed!")
