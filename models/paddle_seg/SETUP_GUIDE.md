# PaddleSeg Environment Setup Guide

AI舌诊智能诊断系统 - 分割模型训练环境搭建指南

## Overview

This document describes the setup process for the PaddleSeg environment for tongue segmentation training using BiSeNetV2-STDCNet2.

## System Requirements

### Hardware Requirements
- **CPU**: x86_64 architecture (Intel/AMD)
- **GPU** (recommended): NVIDIA GPU with CUDA 11.8 support
  - Minimum: GTX 1060 6GB
  - Recommended: RTX 3090 / A100 / V100
- **RAM**: 16GB minimum, 32GB recommended
- **Storage**: 50GB free space (for datasets and model checkpoints)

### Software Requirements
- **OS**: Windows 10/11, Ubuntu 20.04+, CentOS 7+
- **Python**: 3.8 - 3.11
- **CUDA**: 11.8 (for GPU training)
- **cuDNN**: 8.6 for CUDA 11.8

## Installation Steps

### 1. CUDA Installation (GPU only)

#### Windows
```powershell
# Download CUDA 11.8
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_windows.exe

# Run installer
cuda_11.8.0_windows.exe

# Download cuDNN 8.6
# Extract to: C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8
```

#### Linux
```bash
# Download CUDA 11.8
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run

# Run installer
sudo sh cuda_11.8.0_520.61.05_linux.run --toolkit --silent --override

# Download and install cuDNN
# Extract and copy to CUDA toolkit directory
```

### 2. Python Environment Setup

```bash
# Create virtual environment
python -m venv venv_paddle
source venv_paddle/bin/activate  # Linux/Mac
# or
venv_paddle\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip
```

### 3. Install PaddlePaddle

#### GPU Version (CUDA 11.8)
```bash
pip install paddlepaddle-gpu==2.6.0 -i https://mirror.baidu.com/pypi/simple
```

#### CPU Version
```bash
pip install paddlepaddle==2.6.0 -i https://mirror.baidu.com/pypi/simple
```

**Note**: The current environment has PaddlePaddle 3.3.0 installed, which is compatible with the code.

### 4. Install Dependencies

```bash
# Navigate to project directory
cd AI_shezhen

# Install PaddleSeg requirements
pip install -r models/paddle_seg/requirements.txt

# Optional: Install PaddleSeg (not required for custom implementation)
pip install paddleseg
```

### 5. Verify Installation

```bash
# Run environment verification script
python models/paddle_seg/setup_env.py --check-only

# Expected output:
# - PaddlePaddle version: 3.3.0 (or 2.6.0)
# - CUDA available: True (for GPU) / False (for CPU)
# - All required packages installed
```

## Current Environment Status

### System Information
- **OS**: Windows 10 (10.0.19045)
- **Python**: 3.12.0
- **Processor**: Intel64 Family 6 Model 191

### Installed Packages
- **PaddlePaddle**: 3.3.0
- **numpy**: 2.4.1
- **opencv-python**: 4.13.0
- **Pillow**: 12.1.0
- **mlflow**: 3.9.0
- **pycocotools**: installed

### CUDA Status
- **CUDA Available**: False (CPU mode)
- **Device Count**: 0

**Note**: GPU training is not available in the current environment. The baseline test runs on CPU.

### Missing Packages
- **paddleseg**: Optional (not required for custom implementation)
- **albumentations**: Not installed (data augmentation library)

## Baseline Test Results

### Training Configuration
- **Model**: SimpleBiSeNetV2 (simplified for baseline)
- **Classes**: 2 (Background + Tongue)
- **Batch Size**: 2
- **Image Size**: 512x512
- **Optimizer**: Momentum (SGD)
- **Learning Rate**: 0.01
- **Loss**: CrossEntropyLoss

### Baseline Test Results
```
Epoch 1/1:
- Train Loss: ~0.5-0.8 (expected for untrained model)
- Val mIoU: Not calculated in baseline
- Device: CPU
- Throughput: ~1.45 it/s (CPU)
```

### Verification Status
- [x] Environment setup script created
- [x] Configuration file (bisenetv2_stdc2.yml) created
- [x] Baseline training script created
- [x] Baseline test executed successfully
- [x] Training loop functional
- [x] Loss calculation working
- [ ] GPU training verified (requires GPU hardware)
- [ ] Full epoch training (requires GPU for reasonable time)

## Project Structure

```
models/paddle_seg/
├── configs/
│   └── bisenetv2_stdc2.yml        # Model configuration
├── losses/
│   └── (to be added)               # Custom loss functions
├── output/
│   └── best_model/                 # Saved model checkpoints
├── checkpoints/                     # Training checkpoints
├── requirements.txt                 # Python dependencies
├── setup_env.py                    # Environment verification script
├── train_baseline.py               # Baseline training script
├── environment_report.json          # Environment verification results
└── SETUP_GUIDE.md                 # This document
```

## Next Steps (task-2-2)

After completing this task, proceed to:

1. **task-2-2**: 分割损失函数配置与优化
   - Implement CombinedLoss (CrossEntropy + DiceLoss + BoundaryLoss)
   - Configure loss weights (0.5 + 0.3 + 0.2)
   - Add boundary loss for edge enhancement

2. **GPU Setup** (if available):
   - Install CUDA 11.8
   - Install PaddlePaddle GPU version
   - Verify GPU training performance

3. **Pretrained Weights**:
   - Download BiSeNetV2 pretrained weights
   - Configure weight loading in model initialization

## Troubleshooting

### Issue: PaddlePaddle not compiled with CUDA
**Solution**: Install GPU version of PaddlePaddle
```bash
pip uninstall paddlepaddle paddlepaddle-gpu
pip install paddlepaddle-gpu==2.6.0
```

### Issue: DataLoader errors on Windows
**Solution**: Set `num_workers=0` in DataLoader
```python
train_loader = DataLoader(dataset, batch_size=2, num_workers=0)
```

### Issue: CrossEntropyLoss shape mismatch
**Solution**: Reshape tensors for PaddlePaddle API
```python
# (N, C, H, W) -> (N*H*W, C)
outputs = outputs.transpose([0, 2, 3, 1]).reshape([N * H * W, C])
labels = labels.reshape([N * H * W])
```

### Issue: Windows console encoding errors
**Solution**: Wrap stdout/stderr with UTF-8 encoding
```python
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

## References

- PaddlePaddle Documentation: https://www.paddlepaddle.org.cn/
- PaddleSeg GitHub: https://github.com/PaddlePaddle/PaddleSeg
- BiSeNetV2 Paper: https://arxiv.org/abs/2004.02147
- CUDA Toolkit: https://developer.nvidia.com/cuda-toolkit
