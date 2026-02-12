#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
End-to-End Pipeline Test Script

Tests the complete tongue diagnosis pipeline with segmentation and classification.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
from pathlib import Path
import time
import argparse
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import cv2
import yaml
from PIL import Image

# Import pipeline components
from models.pipeline.pipeline import EndToEndPipeline, create_pipeline


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Test end-to-end pipeline')
    parser.add_argument('--seg-model', type=str, default=None,
                        help='Path to segmentation model weights')
    parser.add_argument('--clas-model', type=str, default=None,
                        help='Path to classification model weights')
    parser.add_argument('--image', type=str, default=None,
                        help='Single image to test')
    parser.add_argument('--test-dir', type=str, default=None,
                        help='Directory of images for batch testing')
    parser.add_argument('--output-dir', type=str, default='models/pipeline/test_results',
                        help='Output directory for results')
    parser.add_argument('--fp16', action='store_true',
                        help='Use FP16 inference')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to config YAML file')
    parser.add_argument('--num-samples', type=int, default=10,
                        help='Number of samples to test from test directory')
    return parser.parse_args()


def load_config(config_path):
    """Load configuration from YAML file"""
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return None


def test_single_image(pipeline, image_path, output_dir, save_visualization=True):
    """Test pipeline on a single image"""
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(image_path)}")
    print(f"{'='*60}")

    start_time = time.time()

    # Run prediction
    result = pipeline.predict(image_path, return_intermediates=True)

    total_time = time.time() - start_time

    # Print results
    if result.get('success', True):
        print(f"\n--- Segmentation Results ---")
        seg = result['segmentation']
        print(f"Tongue area: {seg['tongue_area']} pixels")
        print(f"Tongue ratio: {seg['tongue_ratio']:.2%}")
        print(f"Seg time: {seg['inference_time']*1000:.1f} ms")

        print(f"\n--- Classification Results ---")
        for head_name, head_result in result.get('classification', {}).items():
            print(f"\n{head_name}:")
            if 'prediction' in head_result:
                pred = head_result['prediction']
                if isinstance(pred, list) and len(pred) > 0:
                    for p in pred[:3]:  # Show top 3
                        print(f"  - {p['name']}: {p['confidence']:.2%}")
                else:
                    print(f"  - No predictions")
            else:
                print(f"  {head_result}")

        print(f"\n--- Timing ---")
        timing = result['timing_breakdown']
        print(f"Segmentation: {timing['segmentation_ms']:.1f} ms")
        print(f"Classification: {timing['classification_ms']:.1f} ms")
        print(f"Total: {timing['total_ms']:.1f} ms")
        print(f"Measured: {total_time*1000:.1f} ms")

        # Check if target met
        if timing['total_ms'] < 500:
            print(f"Status: PASS (< 500ms target)")
        else:
            print(f"Status: FAIL (exceeds 500ms target)")

    else:
        error = result.get('error', 'unknown')
        message = result.get('message', 'No error message')
        print(f"Error: {error}")
        print(f"Message: {message}")

    # Save visualizations
    if save_visualization and result.get('success', True):
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(image_path))[0]

        # Save mask
        if 'mask' in seg:
            mask_path = os.path.join(output_dir, f'{base_name}_mask.png')
            cv2.imwrite(mask_path, seg['mask'])
            print(f"\nSaved mask: {mask_path}")

        # Save overlay
        if 'overlay' in seg:
            overlay = seg['overlay']
            overlay_path = os.path.join(output_dir, f'{base_name}_overlay.png')
            cv2.imwrite(overlay_path, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
            print(f"Saved overlay: {overlay_path}")

    return result


def test_batch(pipeline, test_dir, output_dir, num_samples=10):
    """Test pipeline on batch of images"""
    print(f"\n{'='*60}")
    print(f"Batch Testing: {test_dir}")
    print(f"{'='*60}")

    # Get image files
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
        image_files.extend(Path(test_dir).glob(ext))

    if not image_files:
        print(f"No images found in {test_dir}")
        return

    # Limit samples
    image_files = sorted(image_files)[:num_samples]
    print(f"Found {len(image_files)} images")

    results = []
    total_times = []
    success_count = 0

    for i, img_path in enumerate(image_files, 1):
        print(f"\n[{i}/{len(image_files)}] Testing {os.path.basename(img_path)}")

        result = pipeline.predict(str(img_path), return_intermediates=False)

        if result.get('success', True):
            success_count += 1
            total_times.append(result['inference_time'])
        results.append({
            'image': str(img_path),
            'success': result.get('success', True),
            'time_ms': result.get('inference_time', 0) * 1000
        })

    # Print summary
    print(f"\n{'='*60}")
    print("Batch Test Summary")
    print(f"{'='*60}")
    print(f"Total images: {len(image_files)}")
    print(f"Success: {success_count} ({success_count/len(image_files)*100:.1f}%)")

    if total_times:
        times_ms = [t * 1000 for t in total_times]
        print(f"\nTiming Statistics:")
        print(f"  Min: {min(times_ms):.1f} ms")
        print(f"  Max: {max(times_ms):.1f} ms")
        print(f"  Mean: {np.mean(times_ms):.1f} ms")
        print(f"  P95: {np.percentile(times_ms, 95):.1f} ms")

        if np.mean(times_ms) < 0.5:
            print(f"\nStatus: PASS (mean < 500ms target)")
        else:
            print(f"\nStatus: FAIL (mean exceeds 500ms target)")

    # Save summary report
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, 'batch_test_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_images': len(image_files),
            'success_count': success_count,
            'success_rate': success_count / len(image_files),
            'timing_stats': {
                'min_ms': float(min(times_ms)) if times_ms else None,
                'max_ms': float(max(times_ms)) if times_ms else None,
                'mean_ms': float(np.mean(times_ms)) if times_ms else None,
                'p95_ms': float(np.percentile(times_ms, 95)) if times_ms else None
            },
            'results': results
        }, f, indent=2, ensure_ascii=False)
    print(f"\nSaved report: {report_path}")


def test_formatting(pipeline, test_dir):
    """Test API and LLM formatting"""
    print(f"\n{'='*60}")
    print("Testing Output Formatting")
    print(f"{'='*60}")

    # Get first image
    image_files = list(Path(test_dir).glob('*.jpg'))[:1]
    if not image_files:
        print("No images found for formatting test")
        return

    img_path = str(image_files[0])
    result = pipeline.predict(img_path, return_intermediates=False)

    # Test API format
    api_format = pipeline.format_for_api(result, image_id='test_formatting')
    print("\nAPI Format:")
    print(json.dumps(api_format, indent=2, ensure_ascii=False))

    # Test LLM format
    llm_format = pipeline.format_for_llm(result)
    print("\nLLM Format:")
    print(json.dumps(llm_format, indent=2, ensure_ascii=False))

    # Print timing stats
    stats = pipeline.get_timing_stats()
    print("\nTiming Stats:")
    print(json.dumps(stats, indent=2))


def main():
    """Main test function"""
    # Configure UTF-8 encoding for Windows
    if sys.platform == 'win32':
        import io
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    # Parse arguments
    args = parse_args()

    # Load config
    config = load_config(args.config)

    print("="*60)
    print("End-to-End Pipeline Test")
    print("="*60)
    print(f"Segmentation model: {args.seg_model or 'Not specified (using random weights)'}")
    print(f"Classification model: {args.clas_model or 'Not specified (using random weights)'}")
    print(f"FP16: {args.fp16}")
    print(f"Output directory: {args.output_dir}")
    print("="*60)

    # Create pipeline
    pipeline_kwargs = {
        'seg_model_path': args.seg_model,
        'clas_model_path': args.clas_model,
        'use_fp16': args.fp16
    }

    if config:
        # Apply config overrides
        if 'pipeline' in config:
            pc = config['pipeline']
            if 'seg_input_size' in pc:
                pipeline_kwargs['seg_input_size'] = tuple(pc['seg_input_size'])
            if 'clas_input_size' in pc:
                pipeline_kwargs['clas_input_size'] = tuple(pc['clas_input_size'])
            if 'extract_tongue' in pc:
                pipeline_kwargs['extract_tongue'] = pc['extract_tongue']
            if 'min_tongue_area' in pc:
                pipeline_kwargs['min_tongue_area'] = pc['min_tongue_area']
            if 'device' in pc:
                pipeline_kwargs['device'] = pc['device']

    pipeline = create_pipeline(**pipeline_kwargs)

    # Run tests
    if args.image:
        # Single image test
        test_single_image(pipeline, args.image, args.output_dir)
    elif args.test_dir:
        # Batch test
        test_batch(pipeline, args.test_dir, args.output_dir, args.num_samples)

        # Also test formatting
        test_formatting(pipeline, args.test_dir)
    else:
        # Generate dummy test image
        print("\nNo image specified, generating dummy test image...")
        dummy_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        dummy_path = os.path.join(args.output_dir, 'dummy_test.png')
        os.makedirs(args.output_dir, exist_ok=True)
        cv2.imwrite(dummy_path, dummy_image)
        test_single_image(pipeline, dummy_path, args.output_dir)

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)


if __name__ == "__main__":
    main()
