#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PaddleSeg Environment Setup and Verification Script

This script sets up and verifies the PaddleSeg environment for tongue segmentation.
It checks CUDA availability, PaddlePaddle installation, and runs a baseline test.

Usage:
    python setup_env.py [--check-only] [--download-weights] [--run-baseline]

Requirements:
    - CUDA 11.8 (if using GPU)
    - PaddlePaddle 2.6.0
    - PaddleSeg (optional, can use custom implementation)
"""

import os
import sys
import json
import platform
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any

# Fix Windows console encoding for Chinese characters and Unicode symbols
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SystemInfo:
    """Collect and display system information"""

    @staticmethod
    def get_os_info() -> Dict[str, str]:
        """Get operating system information"""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }

    @staticmethod
    def get_python_info() -> Dict[str, str]:
        """Get Python environment information"""
        return {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "python_executable": sys.executable
        }

    @staticmethod
    def check_cuda() -> Dict[str, Any]:
        """Check CUDA availability and information"""
        cuda_info = {
            "available": False,
            "version": None,
            "device_count": 0,
            "devices": []
        }

        try:
            import paddle
            cuda_info["available"] = paddle.is_compiled_with_cuda()
            if cuda_info["available"]:
                # Get CUDA version from Paddle
                cuda_info["version"] = paddle.device.cuda.device_count()

                # Get device count
                cuda_info["device_count"] = paddle.device.cuda.device_count()

                # Get device properties for each GPU
                for i in range(cuda_info["device_count"]):
                    props = paddle.device.cuda.get_device_properties(i)
                    cuda_info["devices"].append({
                        "id": i,
                        "name": props.name,
                        "total_memory": props.total_memory / (1024**3),  # GB
                        "major": props.major,
                        "minor": props.minor
                    })
        except ImportError:
            logger.warning("PaddlePaddle not installed")
        except Exception as e:
            logger.warning(f"Error checking CUDA: {e}")

        return cuda_info


class PackageChecker:
    """Check and verify package installations"""

    def __init__(self):
        self.packages = {
            "paddle": "2.6.0",
            "paddleseg": None,  # Optional
            "numpy": "1.24.0",
            "opencv-python": "4.8.0",
            "Pillow": "10.0.0",
            "albumentations": "1.3.0",
            "mlflow": "2.8.0",
            "pycocotools": "2.0.6"
        }
        self.installed = {}
        self.missing = []
        self.version_mismatch = []

    def check_all(self) -> bool:
        """Check all required packages"""
        all_ok = True

        for package, min_version in self.packages.items():
            try:
                # Try to import the package
                if package == "opencv-python":
                    import cv2
                    module = cv2
                    name = "opencv-python"
                elif package == "PIL" or package == "Pillow":
                    import PIL
                    module = PIL
                    name = "Pillow"
                else:
                    module = __import__(package)
                    name = package

                # Get version
                version = getattr(module, '__version__', 'unknown')
                self.installed[name] = version

                # Check version if specified
                if min_version and version != 'unknown':
                    if self._compare_versions(version, min_version) < 0:
                        self.version_mismatch.append({
                            "package": name,
                            "installed": version,
                            "required": min_version
                        })
                        all_ok = False
                        logger.warning(f"{name} version {version} < required {min_version}")
                    else:
                        logger.info(f"✓ {name} {version}")
                else:
                    logger.info(f"✓ {name} {version}")

            except ImportError:
                self.missing.append(package)
                all_ok = False
                logger.error(f"✗ {package} not installed")

        return all_ok

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare version strings. Returns -1, 0, or 1"""
        v1_parts = [int(x) for x in v1.split('.')[:3]]
        v2_parts = [int(x) for x in v2.split('.')[:3]]

        for a, b in zip(v1_parts, v2_parts):
            if a < b:
                return -1
            elif a > b:
                return 1
        return 0


class PaddleSegVerifier:
    """Verify PaddleSeg installation and configuration"""

    def __init__(self):
        self.paddle_available = False
        self.model_ready = False

    def verify_paddle(self) -> bool:
        """Verify PaddlePaddle installation"""
        try:
            import paddle

            logger.info(f"PaddlePaddle version: {paddle.__version__}")
            logger.info(f"PaddlePaddle commit: {paddle.version.commit}")

            # Check CUDA
            if paddle.is_compiled_with_cuda():
                logger.info("✓ PaddlePaddle compiled with CUDA")
                device_count = paddle.device.cuda.device_count()
                logger.info(f"  Available CUDA devices: {device_count}")
                for i in range(device_count):
                    props = paddle.device.cuda.get_device_properties(i)
                    logger.info(f"    GPU {i}: {props.name} ({props.total_memory / (1024**3):.1f} GB)")
            else:
                logger.info("✗ PaddlePaddle NOT compiled with CUDA (CPU only)")

            self.paddle_available = True
            return True

        except ImportError as e:
            logger.error(f"PaddlePaddle not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verifying PaddlePaddle: {e}")
            return False

    def verify_config(self, config_path: str) -> bool:
        """Verify configuration file exists and is valid"""
        if not os.path.exists(config_path):
            logger.error(f"Configuration file not found: {config_path}")
            return False

        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ Configuration file loaded: {config_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False

    def verify_dataset(self, dataset_config: dict) -> bool:
        """Verify dataset paths exist"""
        all_exist = True

        for split in ['train', 'val', 'test']:
            if split not in dataset_config:
                continue

            images_path = dataset_config[split].get('images', '')
            masks_path = dataset_config[split].get('masks', '')

            if images_path and os.path.exists(images_path):
                num_images = len([f for f in os.listdir(images_path) if not f.startswith('.')])
                logger.info(f"✓ {split} images: {images_path} ({num_images} images)")
            else:
                logger.warning(f"✗ {split} images not found: {images_path}")
                all_exist = False

            if masks_path and os.path.exists(masks_path):
                num_masks = len([f for f in os.listdir(masks_path) if not f.startswith('.')])
                logger.info(f"✓ {split} masks: {masks_path} ({num_masks} masks)")
            else:
                logger.warning(f"✗ {split} masks not found: {masks_path}")
                all_exist = False

        return all_exist


class BaselineTester:
    """Run baseline test with a simple model"""

    def __init__(self, config: dict):
        self.config = config
        self.results = {}

    def create_test_model(self):
        """Create a simple test model"""
        import paddle
        import paddle.nn as nn

        class SimpleSegmentationNet(nn.Layer):
            def __init__(self, num_classes=2):
                super().__init__()
                # Simple encoder-decoder
                self.encoder = nn.Sequential(
                    nn.Conv2D(3, 32, 3, stride=2, padding=1),
                    nn.BatchNorm(32),
                    nn.ReLU(),
                    nn.Conv2D(32, 64, 3, stride=2, padding=1),
                    nn.BatchNorm(64),
                    nn.ReLU(),
                    nn.Conv2D(64, 128, 3, stride=2, padding=1),
                    nn.BatchNorm(128),
                    nn.ReLU(),
                )

                self.decoder = nn.Sequential(
                    nn.Conv2DTranspose(128, 64, 3, stride=2, padding=1, output_padding=1),
                    nn.BatchNorm(64),
                    nn.ReLU(),
                    nn.Conv2DTranspose(64, 32, 3, stride=2, padding=1, output_padding=1),
                    nn.BatchNorm(32),
                    nn.ReLU(),
                    nn.Conv2DTranspose(32, num_classes, 3, stride=2, padding=1, output_padding=1),
                )

            def forward(self, x):
                x = self.encoder(x)
                x = self.decoder(x)
                return x

        return SimpleSegmentationNet(num_classes=self.config['model']['num_classes'])

    def run_inference_test(self) -> bool:
        """Run a simple inference test"""
        try:
            import paddle
            import numpy as np

            logger.info("Running baseline inference test...")

            # Create model
            model = self.create_test_model()
            model.eval()

            # Create dummy input
            batch_size = 2
            height, width = 512, 512
            x = paddle.randn([batch_size, 3, height, width])

            # Run inference
            with paddle.no_grad():
                output = model(x)

            # Check output shape
            expected_shape = [batch_size, self.config['model']['num_classes'], height, width]
            if list(output.shape) == expected_shape:
                logger.info(f"✓ Inference test passed. Output shape: {output.shape}")
                self.results['inference'] = {
                    'status': 'success',
                    'input_shape': list(x.shape),
                    'output_shape': list(output.shape)
                }
                return True
            else:
                logger.error(f"✗ Output shape mismatch. Expected {expected_shape}, got {list(output.shape)}")
                return False

        except Exception as e:
            logger.error(f"✗ Inference test failed: {e}")
            self.results['inference'] = {'status': 'failed', 'error': str(e)}
            return False

    def run_training_step_test(self) -> bool:
        """Run a single training step"""
        try:
            import paddle
            import numpy as np

            logger.info("Running baseline training step test...")

            # Create model and optimizer
            model = self.create_test_model()
            model.train()

            optimizer = paddle.optimizer.SGD(
                parameters=model.parameters(),
                learning_rate=0.01
            )

            # Loss function
            criterion = paddle.nn.CrossEntropyLoss()

            # Create dummy data
            batch_size = 2
            height, width = 512, 512
            x = paddle.randn([batch_size, 3, height, width])
            y = paddle.randint(0, self.config['model']['num_classes'], [batch_size, 1, height, width])

            # Training step
            output = model(x)
            loss = criterion(output, y.squeeze(1))

            loss.backward()
            optimizer.step()
            optimizer.clear_grad()

            logger.info(f"✓ Training step test passed. Loss: {loss.item():.4f}")
            self.results['training_step'] = {
                'status': 'success',
                'loss': float(loss.item())
            }
            return True

        except Exception as e:
            logger.error(f"✗ Training step test failed: {e}")
            self.results['training_step'] = {'status': 'failed', 'error': str(e)}
            return False


def generate_report(env_info: Dict, checker: PackageChecker,
                   verifier: PaddleSegVerifier, tester: BaselineTester) -> str:
    """Generate environment verification report"""

    report = {
        "timestamp": datetime.now().isoformat(),
        "status": "success" if all([
            not checker.missing,
            not checker.version_mismatch,
            verifier.paddle_available
        ]) else "failed",
        "system": SystemInfo.get_os_info(),
        "python": SystemInfo.get_python_info(),
        "packages": {
            "installed": checker.installed,
            "missing": checker.missing,
            "version_mismatch": checker.version_mismatch
        },
        "cuda": SystemInfo.check_cuda(),
        "paddle": {
            "available": verifier.paddle_available,
            "version": checker.installed.get("paddle", "unknown")
        },
        "tests": tester.results
    }

    return json.dumps(report, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="PaddleSeg Environment Setup and Verification")
    parser.add_argument("--check-only", action="store_true", help="Only check environment, don't run tests")
    parser.add_argument("--download-weights", action="store_true", help="Download pretrained weights")
    parser.add_argument("--run-baseline", action="store_true", help="Run baseline test")
    parser.add_argument("--config", type=str, default="models/paddle_seg/configs/bisenetv2_stdc2.yml",
                       help="Path to configuration file")
    parser.add_argument("--output", type=str, default="models/paddle_seg/environment_report.json",
                       help="Path to save environment report")

    args = parser.parse_args()

    # Print header
    logger.info("=" * 60)
    logger.info("PaddleSeg Environment Setup and Verification")
    logger.info("=" * 60)

    # Get system info
    logger.info("\n[1] System Information")
    logger.info("-" * 40)
    os_info = SystemInfo.get_os_info()
    for key, value in os_info.items():
        logger.info(f"{key}: {value}")

    python_info = SystemInfo.get_python_info()
    for key, value in python_info.items():
        logger.info(f"{key}: {value}")

    # Check CUDA
    logger.info("\n[2] CUDA Information")
    logger.info("-" * 40)
    cuda_info = SystemInfo.check_cuda()
    if cuda_info["available"]:
        logger.info(f"✓ CUDA is available")
        if cuda_info["devices"]:
            for device in cuda_info["devices"]:
                logger.info(f"  GPU {device['id']}: {device['name']} ({device['total_memory']:.1f} GB)")
    else:
        logger.info("✗ CUDA is NOT available (CPU mode)")

    # Check packages
    logger.info("\n[3] Package Verification")
    logger.info("-" * 40)
    checker = PackageChecker()
    packages_ok = checker.check_all()

    if not packages_ok:
        logger.error("\nSome required packages are missing or have version mismatch:")
        logger.info("\nTo install missing packages, run:")
        logger.info(f"  pip install -r models/paddle_seg/requirements.txt")

    # Verify PaddlePaddle
    logger.info("\n[4] PaddlePaddle Verification")
    logger.info("-" * 40)
    verifier = PaddleSegVerifier()
    paddle_ok = verifier.verify_paddle()

    if not args.check_only and paddle_ok:
        # Load config
        import yaml
        logger.info("\n[5] Configuration Verification")
        logger.info("-" * 40)
        if os.path.exists(args.config):
            with open(args.config, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"✓ Configuration loaded from {args.config}")

            # Verify dataset
            dataset_ok = verifier.verify_dataset(config.get('dataset', {}))
        else:
            logger.error(f"✗ Configuration file not found: {args.config}")
            config = {}
            dataset_ok = False

    # Download pretrained weights if requested
    if args.download_weights and paddle_ok:
        logger.info("\n[6] Downloading Pretrained Weights")
        logger.info("-" * 40)
        logger.info("Pretrained weights download not yet implemented")
        logger.info("Please download manually from:")
        logger.info("https://bj.bcebos.com/paddleseg/dygraph_v2.0/bisenetv2_cityscapes_1024x1024_160k/model.pdparams")

    # Run baseline test if requested
    tester = BaselineTester(config if 'config' in dir() else {'model': {'num_classes': 2}})
    if args.run_baseline and paddle_ok:
        logger.info("\n[7] Baseline Tests")
        logger.info("-" * 40)
        inference_ok = tester.run_inference_test()
        training_ok = tester.run_training_step_test()
        baseline_ok = inference_ok and training_ok
    else:
        baseline_ok = None

    # Generate report
    report = generate_report(os_info, checker, verifier, tester)

    # Save report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    logger.info(f"\n[8] Environment report saved to: {args.output}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    all_ok = packages_ok and paddle_ok

    if all_ok:
        logger.info("✓ Environment setup complete!")
        if baseline_ok is False:
            logger.info("✗ Baseline tests failed - please check errors above")
        elif baseline_ok is True:
            logger.info("✓ All tests passed!")
        else:
            logger.info("Run with --run-baseline to execute baseline tests")
    else:
        logger.info("✗ Environment setup incomplete")
        if not packages_ok:
            logger.info("  - Some packages are missing or have version mismatch")
        if not paddle_ok:
            logger.info("  - PaddlePaddle verification failed")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
