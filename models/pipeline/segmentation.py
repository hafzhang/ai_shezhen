#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tongue Segmentation Predictor

Wraps the segmentation model for inference with preprocessing and postprocessing.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union
import numpy as np
from PIL import Image
import cv2

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import paddle
import paddle.nn as nn
import paddle.nn.functional as F

# Import BiSeNetV2 model
from models.paddle_seg.models.bisenetv2 import BiSeNetV2


class TongueSegmentationPredictor:
    """Tongue segmentation predictor for inference

    Handles:
    - Model loading
    - Image preprocessing
    - Segmentation inference
    - Post-processing (mask refinement)

    Args:
        model_path: Path to model weights (.pdparams)
        model_class: Model class (default: BiSeNetV2)
        num_classes: Number of segmentation classes (default: 2)
        input_size: Input image size (H, W) for inference
        use_fp16: Whether to use FP16 inference
        device: Device to run inference on ('cpu' or 'gpu')
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_class: nn.Layer = BiSeNetV2,
        num_classes: int = 2,
        input_size: Tuple[int, int] = (512, 512),
        use_fp16: bool = False,
        device: str = 'cpu'
    ):
        self.num_classes = num_classes
        self.input_size = input_size
        self.use_fp16 = use_fp16
        self.device = device

        # Initialize model
        self.model = model_class(num_classes=num_classes, in_channels=3)
        self.model.eval()

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
                for key, value in state_dict.items():
                    if isinstance(value, np.ndarray) and value.dtype == np.float16:
                        state_dict[key] = value.astype(np.float32)

            # Set state dict
            load_result = self.model.set_state_dict(state_dict)
            print(f"Loaded segmentation model from: {model_path}")
            print(f"Missing keys: {len(load_result[0])}, Unexpected keys: {len(load_result[1])}")
            return True

        except Exception as e:
            print(f"Error loading segmentation model: {e}")
            return False

    def preprocess(
        self,
        image: Union[str, np.ndarray, Image.Image]
    ) -> paddle.Tensor:
        """Preprocess image for segmentation

        Args:
            image: Input image (path, numpy array, or PIL Image)

        Returns:
            Preprocessed tensor (1, 3, H, W)
        """
        # Load image
        if isinstance(image, str):
            img = Image.open(image).convert('RGB')
        elif isinstance(image, np.ndarray):
            img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        else:
            img = image.convert('RGB')

        # Store original size for post-processing
        self.original_size = img.size[::-1]  # (H, W)

        # Resize to input size
        img = img.resize((self.input_size[1], self.input_size[0]), Image.BILINEAR)

        # Convert to numpy array
        img_array = np.array(img).astype('float32')

        # Normalize to [0, 1]
        img_array = img_array / 255.0

        # ImageNet normalization (optional, depends on training)
        # mean = np.array([0.485, 0.456, 0.406])
        # std = np.array([0.229, 0.224, 0.225])
        # img_array = (img_array - mean) / std

        # Convert to tensor: (H, W, C) -> (C, H, W) -> (1, C, H, W)
        img_tensor = paddle.to_tensor(img_array).transpose([2, 0, 1]).unsqueeze(0)

        return img_tensor

    def postprocess(
        self,
        output: paddle.Tensor,
        original_size: Optional[Tuple[int, int]] = None
    ) -> np.ndarray:
        """Postprocess segmentation output

        Args:
            output: Model output (1, num_classes, H, W)
            original_size: Original image size (H, W) for resizing

        Returns:
            Binary mask (H, W) with values 0 (background) or 255 (tongue)
        """
        # Get predictions
        if output.shape[1] == 2:
            # Binary segmentation: take class 1 (tongue)
            preds = paddle.argmax(output, axis=1).squeeze(0).numpy()
        else:
            # Multi-class: take class with highest probability
            preds = paddle.argmax(output, axis=1).squeeze(0).numpy()

        # Convert to binary mask: tongue=255, background=0
        mask = (preds * 255).astype(np.uint8)

        # Resize to original size if provided
        if original_size is not None:
            mask = cv2.resize(mask, (original_size[1], original_size[0]),
                             interpolation=cv2.INTER_NEAREST)

        return mask

    def predict(
        self,
        image: Union[str, np.ndarray, Image.Image],
        return_mask: bool = True,
        return_overlay: bool = False
    ) -> Dict[str, Any]:
        """Run segmentation inference on an image

        Args:
            image: Input image
            return_mask: Whether to return the binary mask
            return_overlay: Whether to return overlay image

        Returns:
            Dictionary with prediction results
        """
        with paddle.no_grad():
            # Preprocess
            input_tensor = self.preprocess(image)

            # Inference
            output = self.model(input_tensor)

            # Postprocess
            original_size = getattr(self, 'original_size', self.input_size)
            mask = self.postprocess(output, original_size)

            result = {
                'mask': mask if return_mask else None,
                'original_size': original_size,
                'output_size': mask.shape,
            }

            # Create overlay if requested
            if return_overlay:
                # Load original image for overlay
                if isinstance(image, str):
                    orig_img = cv2.imread(image)
                    orig_img = cv2.cvtColor(orig_img, cv2.COLOR_BGR2RGB)
                elif isinstance(image, np.ndarray):
                    orig_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                else:
                    orig_img = np.array(image.convert('RGB'))

                # Resize original image to mask size
                orig_img = cv2.resize(orig_img, (mask.shape[1], mask.shape[0]))

                # Create overlay: red semi-transparent
                overlay = orig_img.copy()
                overlay[mask == 255] = [255, 0, 0]  # Red for tongue
                result['overlay'] = overlay
                result['original_image'] = orig_img

            return result

    def extract_tongue_region(
        self,
        image: Union[str, np.ndarray, Image.Image],
        padding: int = 10,
        min_area: int = 1000
    ) -> Optional[np.ndarray]:
        """Extract tongue region from image using segmentation mask

        Args:
            image: Input image
            padding: Padding around tongue region
            min_area: Minimum area threshold (filters noise)

        Returns:
            Cropped tongue image, or None if tongue not found
        """
        # Get segmentation
        result = self.predict(image, return_mask=True, return_overlay=False)
        mask = result['mask']

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Find largest contour (should be tongue)
        largest_contour = max(contours, key=cv2.contourArea)

        # Check minimum area
        area = cv2.contourArea(largest_contour)
        if area < min_area:
            return None

        # Get bounding box with padding
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Load original image
        if isinstance(image, str):
            img = cv2.imread(image)
        elif isinstance(image, np.ndarray):
            img = image.copy()
        else:
            img = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)

        H, W = img.shape[:2]

        # Add padding (with boundary check)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(W, x + w + padding)
        y2 = min(H, y + h + padding)

        # Crop tongue region
        tongue_crop = img[y1:y2, x1:x2]

        return tongue_crop

    def batch_predict(
        self,
        images: list,
        batch_size: int = 4
    ) -> list:
        """Run segmentation on batch of images

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
                batch_output = self.model(batch_tensors)

            # Postprocess each image in batch
            for j, output in enumerate(batch_output):
                output_single = output.unsqueeze(0)  # Add batch dimension
                original_size = getattr(self, 'original_size', self.input_size)
                mask = self.postprocess(output_single, original_size)
                results.append({'mask': mask})

        return results


def create_segmentation_predictor(
    model_path: str = None,
    use_fp16: bool = False
) -> TongueSegmentationPredictor:
    """Factory function to create segmentation predictor

    Args:
        model_path: Path to model weights
        use_fp16: Whether to use FP16 inference

    Returns:
        TongueSegmentationPredictor instance
    """
    return TongueSegmentationPredictor(
        model_path=model_path,
        use_fp16=use_fp16
    )


if __name__ == "__main__":
    # Test segmentation predictor
    import sys

    if sys.platform == 'win32':
        import io
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    print("Testing Tongue Segmentation Predictor...")

    # Create predictor (without weights for testing)
    predictor = TongueSegmentationPredictor()

    print(f"Model created: {type(predictor.model).__name__}")
    print(f"Number of classes: {predictor.num_classes}")
    print(f"Input size: {predictor.input_size}")
    print(f"Device: {predictor.device}")

    # Test preprocess
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    tensor = predictor.preprocess(test_image)
    print(f"\nPreprocess test:")
    print(f"Input shape: {test_image.shape}")
    print(f"Output tensor shape: {tensor.shape}")

    # Test inference
    result = predictor.predict(test_image, return_mask=True, return_overlay=True)
    print(f"\nInference test:")
    print(f"Mask shape: {result['mask'].shape}")
    print(f"Mask unique values: {np.unique(result['mask'])}")
    print(f"Overlay shape: {result['overlay'].shape}")

    print("\nSegmentation predictor test completed!")
