#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tongue Classification Predictor

Wraps the multi-head classification model for inference with preprocessing and postprocessing.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union, List
import numpy as np
from PIL import Image
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import paddle
import paddle.nn as nn
import paddle.nn.functional as F

# Import classification models
from models.paddle_clas.models.pphgnetv2 import PP_HGNetV2_B4
from models.paddle_clas.models.multi_head import (
    MultiHeadTongueModel,
    DEFAULT_HEAD_CONFIGS,
    HeadConfig
)


class TongueClassificationPredictor:
    """Tongue classification predictor for inference

    Handles:
    - Model loading
    - Image preprocessing
    - Multi-head classification inference
    - Post-processing (confidence formatting, result structuring)

    Args:
        model_path: Path to model weights (.pdparams)
        backbone_class: Backbone model class (default: PP_HGNetV2_B4)
        head_configs: Configuration for each head
        input_size: Input image size (H, W) for inference
        use_fp16: Whether to use FP16 inference
        device: Device to run inference on ('cpu' or 'gpu')
        sigmoid_threshold: Threshold for multi-label predictions
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        backbone_class: nn.Layer = PP_HGNetV2_B4,
        head_configs: Dict[str, HeadConfig] = None,
        input_size: Tuple[int, int] = (224, 224),
        use_fp16: bool = False,
        device: str = 'cpu',
        sigmoid_threshold: float = 0.5
    ):
        self.input_size = input_size
        self.use_fp16 = use_fp16
        self.device = device
        self.sigmoid_threshold = sigmoid_threshold

        # Use default head configs if not provided
        if head_configs is None:
            head_configs = DEFAULT_HEAD_CONFIGS

        self.head_configs = head_configs

        # Initialize backbone (without classifier for ImageNet)
        self.backbone = backbone_class(num_classes=0)

        # Create multi-head model
        self.model = MultiHeadTongueModel(
            backbone=self.backbone,
            head_configs=head_configs,
            dropout=0.0,  # No dropout for inference
            feature_dim=864  # PP-HGNetV2-B4 feature dim
        )
        self.model.eval()

        # ImageNet normalization
        self.mean = np.array([0.485, 0.456, 0.406])
        self.std = np.array([0.229, 0.224, 0.225])

        # Load weights if provided
        if model_path and os.path.exists(model_path):
            self.load_weights(model_path)

        # Configure device
        if device == 'gpu' and paddle.is_compiled_with_cuda():
            place = paddle.CUDAPlace(0)
        else:
            place = paddle.CPUPlace()

        self.model = self.model.to(place)

        # AMP decorator for FP16
        if use_fp16:
            self.model = paddle.amp.decorate(self.model, level='O1')

    def load_weights(self, model_path: str) -> bool:
        """Load model weights from file

        Args:
            model_path: Path to model weights

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load state dict
            state_dict = paddle.load(model_path)

            # Handle FP16 weights (convert to FP32)
            if any(isinstance(v, np.ndarray) and v.dtype == np.float16 for v in state_dict.values()):
                print("Converting FP16 weights to FP32...")
                for key, value in state_dict.items():
                    if isinstance(value, np.ndarray) and value.dtype == np.float16:
                        state_dict[key] = value.astype(np.float32)

            # Handle INT8 weights (NPZ format)
            if model_path.endswith('.npz'):
                print("Loading INT8 quantized model...")
                # Extract weights from NPZ
                with np.load(model_path) as npz_file:
                    # NPZ may have different structure
                    # Convert to compatible format
                    for key in npz_file.files:
                        state_dict[key] = npz_file[key]

            # Set state dict
            load_result = self.model.set_state_dict(state_dict)
            print(f"Loaded classification model from: {model_path}")
            print(f"Missing keys: {len(load_result[0])}, Unexpected keys: {len(load_result[1])}")
            return True

        except Exception as e:
            print(f"Error loading classification model: {e}")
            return False

    def preprocess(
        self,
        image: Union[str, np.ndarray, Image.Image]
    ) -> paddle.Tensor:
        """Preprocess image for classification

        Args:
            image: Input image (path, numpy array, or PIL Image)

        Returns:
            Preprocessed tensor (1, 3, H, W)
        """
        # Load image
        if isinstance(image, str):
            img = Image.open(image).convert('RGB')
        elif isinstance(image, np.ndarray):
            # Handle both BGR (OpenCV) and RGB
            if len(image.shape) == 3 and image.shape[2] == 3:
                # Assume BGR if max is in first channel (common in OpenCV)
                if image[:, :, 2].max() > image[:, :, 0].max():
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(image)
        else:
            img = image.convert('RGB')

        # Resize to input size
        img = img.resize((self.input_size[1], self.input_size[0]), Image.BILINEAR)

        # Convert to numpy array
        img_array = np.array(img).astype('float32') / 255.0

        # Normalize with ImageNet stats
        img_array = (img_array - self.mean) / self.std

        # Convert to tensor: (H, W, C) -> (C, H, W) -> (1, C, H, W)
        img_tensor = paddle.to_tensor(img_array).transpose([2, 0, 1]).unsqueeze(0)

        return img_tensor

    def postprocess(
        self,
        predictions: List[paddle.Tensor],
        head_names: List[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Postprocess classification predictions

        Args:
            predictions: List of output tensors from each head
            head_names: Names of heads

        Returns:
            Dictionary with structured results per head
        """
        if head_names is None:
            head_names = list(self.head_configs.keys())

        results = {}

        for pred, head_name in zip(predictions, head_names):
            if head_name not in self.head_configs:
                continue

            config = self.head_configs[head_name]

            # Convert to numpy
            logits = pred.squeeze(0).numpy()  # Remove batch dim

            # Apply softmax or sigmoid
            if config.multi_label:
                probs = F.sigmoid(pred).squeeze(0).numpy()
            else:
                probs = F.softmax(pred, axis=1).squeeze(0).numpy()

            # Get prediction and confidence
            if config.multi_label:
                # Multi-label: apply threshold
                binary_preds = (probs >= self.sigmoid_threshold).astype(int)
                present_indices = np.where(binary_preds == 1)[0]

                predictions_list = []
                for idx in present_indices:
                    if idx < len(config.class_names):
                        predictions_list.append({
                            'name': config.class_names[idx],
                            'confidence': float(probs[idx])
                        })
            else:
                # Single-label: get argmax
                pred_idx = np.argmax(probs)
                predictions_list = [{
                    'name': config.class_names[pred_idx],
                    'confidence': float(probs[pred_idx])
                }]

            results[head_name] = {
                'prediction': predictions_list,
                'all_probabilities': {
                    config.class_names[i]: float(probs[i])
                    for i in range(min(len(config.class_names), len(probs)))
                },
                'description': config.description
            }

        return results

    def predict(
        self,
        image: Union[str, np.ndarray, Image.Image],
        return_raw: bool = False
    ) -> Dict[str, Any]:
        """Run classification inference on an image

        Args:
            image: Input image
            return_raw: Whether to return raw logits

        Returns:
            Dictionary with prediction results
        """
        with paddle.no_grad():
            # Preprocess
            input_tensor = self.preprocess(image)

            # Inference
            outputs = self.model(input_tensor)

            # Postprocess
            results = self.postprocess(outputs)

            result = {
                'results': results,
                'original_size': getattr(self, 'original_size', self.input_size),
            }

            # Add raw outputs if requested
            if return_raw:
                result['raw_outputs'] = [o.numpy() for o in outputs]

            return result

    def format_for_prompt(
        self,
        prediction_result: Dict[str, Any],
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """Format prediction result for LLM prompt

        Args:
            prediction_result: Result from predict()
            confidence_threshold: Minimum confidence for including features

        Returns:
            Dictionary formatted for user prompt template
        """
        results = prediction_result['results']
        formatted = {}

        # Process each head
        for head_name, head_result in results.items():
            config = self.head_configs[head_name]

            if config.multi_label:
                # Multi-label: collect all features above threshold
                present_features = [
                    p['name'] for p in head_result['prediction']
                    if p['confidence'] >= confidence_threshold
                ]

                if head_name == 'features':
                    # Special handling for features head
                    formatted['red_dots'] = any(
                        '红点' in p['name'] for p in head_result['prediction']
                        if p['confidence'] >= 0.3
                    )
                    formatted['cracks'] = any(
                        '裂纹' in p['name'] for p in head_result['prediction']
                        if p['confidence'] >= 0.3
                    )
                    formatted['teeth_marks'] = any(
                        '齿痕' in p['name'] for p in head_result['prediction']
                        if p['confidence'] >= 0.3
                    )
                else:
                    formatted[head_name] = present_features
            else:
                # Single-label: get top prediction
                top_pred = head_result['prediction'][0]
                formatted[head_name] = {
                    'prediction': top_pred['name'],
                    'confidence': top_pred['confidence']
                }

        # Add descriptions
        for head_name, head_result in results.items():
            if head_name not in formatted:
                continue
            if isinstance(formatted[head_name], dict):
                pred = formatted[head_name]['prediction']
                # Find description
                for name, desc in [
                    ('淡红舌', '气血调和，颜色适中'),
                    ('红舌', '热盛，颜色深红'),
                    ('绛紫舌', '热盛血瘀，颜色紫暗'),
                    ('淡白舌', '气血两虚，颜色淡白'),
                    ('白苔', '表证或寒证'),
                    ('黄苔', '里证或热证'),
                    ('黑苔', '里寒或肾虚'),
                    ('花剥苔', '胃阴不足或肝肾阴虚'),
                    ('正常', '舌形适中，气血调和'),
                    ('胖大舌', '脾虚湿盛，舌体胖大'),
                    ('瘦薄舌', '气血两虚，舌体瘦薄'),
                    ('薄苔', '胃气充盈或表证'),
                    ('厚苔', '里证湿盛或食积'),
                    ('腐苔', '湿热困脾，苔质腻浊'),
                    ('不健康', '存在病理特征'),
                    ('健康舌', '舌象正常无异常'),
                ]:
                    if pred == name:
                        formatted[head_name]['description'] = desc
                        break

        return formatted

    def batch_predict(
        self,
        images: list,
        batch_size: int = 8
    ) -> list:
        """Run classification on batch of images

        Args:
            images: List of image paths/arrays
            batch_size: Batch size for inference

        Returns:
            List of prediction results
        """
        results = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]

            # Preprocess batch
            batch_tensors = paddle.concat([self.preprocess(img) for img in batch])

            # Inference
            with paddle.no_grad():
                batch_outputs = self.model(batch_tensors)

            # Split batch outputs and postprocess each
            for j in range(batch_outputs[0].shape[0]):
                single_outputs = [output[j:j+1] for output in batch_outputs]
                result = self.postprocess(single_outputs)
                results.append({'results': result})

        return results


def create_classification_predictor(
    model_path: str = None,
    use_fp16: bool = False
) -> TongueClassificationPredictor:
    """Factory function to create classification predictor

    Args:
        model_path: Path to model weights
        use_fp16: Whether to use FP16 inference

    Returns:
        TongueClassificationPredictor instance
    """
    return TongueClassificationPredictor(
        model_path=model_path,
        use_fp16=use_fp16
    )


if __name__ == "__main__":
    # Test classification predictor
    import sys

    if sys.platform == 'win32':
        import io
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Testing Tongue Classification Predictor...")

    # Create predictor (without weights for testing)
    predictor = TongueClassificationPredictor()

    print(f"Model created: {type(predictor.model).__name__}")
    print(f"Number of heads: {len(predictor.head_configs)}")
    print(f"Input size: {predictor.input_size}")
    print(f"Device: {predictor.device}")

    head_names = list(predictor.head_configs.keys())
    for name, config in predictor.head_configs.items():
        print(f"  - {name}: {config.num_classes} classes ({config.description})")

    # Test preprocess
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    tensor = predictor.preprocess(test_image)
    print(f"\nPreprocess test:")
    print(f"Input shape: {test_image.shape}")
    print(f"Output tensor shape: {tensor.shape}")

    # Test inference
    result = predictor.predict(test_image)
    print(f"\nInference test:")
    print(f"Number of heads in result: {len(result['results'])}")

    print("\nClassification predictor test completed!")
