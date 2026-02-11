#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模型评估脚本

评估分割和分类模型的性能

Usage:
    python evaluate.py --task segmentation --checkpoint checkpoints/segmentation/best.pdparams
    python evaluate.py --task classification --checkpoint checkpoints/classification/best.pdparams
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from typing import Dict, List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import yaml
import numpy as np
import paddle
from paddle.io import DataLoader
from tqdm import tqdm

from src.data.dataset import TongueSegmentationDataset, TongueClassificationDataset
from src.models.segmentation import BiSeNetV2
from src.models.classification import MultiHeadClassificationModel, PP_HGNetV2_B4
from src.evaluation.metrics import (
    SegmentationMetrics, ClassificationMetrics, ImbalanceMetrics,
    compute_inference_time
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """加载YAML配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_model(checkpoint_path: str, config: dict, task: str):
    """加载模型"""
    if task == "segmentation":
        model = BiSeNetV2(
            num_classes=config['segmentation']['model']['num_classes'],
            in_channels=config['segmentation']['model']['in_channels']
        )
    else:  # classification
        backbone = PP_HGNetV2_B4(num_classes=1000, pretrained=None)
        head_configs = {
            k: {"num_classes": v["num_classes"], "names": v.get("names", [])}
            for k, v in config['classification']['multi_head'].items()
        }
        model = MultiHeadClassificationModel(
            backbone=backbone,
            head_configs=head_configs,
            dropout=config['classification']['model'].get('dropout', 0.2)
        )

    # 加载权重
    state_dict = paddle.load(checkpoint_path)
    if "model_state_dict" in state_dict:
        model.set_state_dict(state_dict["model_state_dict"])
    else:
        model.set_state_dict(state_dict)

    logger.info(f"Model loaded from {checkpoint_path}")
    return model


def evaluate_segmentation(config: dict, checkpoint_path: str):
    """评估分割模型"""
    logger.info("=" * 60)
    logger.info("Evaluating Segmentation Model")
    logger.info("=" * 60)

    # 加载模型
    model = load_model(checkpoint_path, config, "segmentation")
    model.eval()

    # 创建数据集
    base_path = config['dataset']['base_path']
    val_ann = os.path.join(base_path, config['dataset']['val']['annotations'])
    val_img_dir = os.path.dirname(val_ann)

    val_dataset = TongueSegmentationDataset(
        annotation_file=val_ann,
        image_dir=val_img_dir,
        image_size=tuple(config['dataset']['image_size']),
        is_training=False
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config['segmentation']['training']['batch_size'],
        shuffle=False,
        num_workers=4
    )

    # 创建评估器
    seg_metrics = SegmentationMetrics(
        num_classes=config['segmentation']['model']['num_classes']
    )

    # 评估
    all_preds = []
    all_targets = []

    logger.info("Running inference...")
    with paddle.no_grad():
        for batch in tqdm(val_loader, desc="Evaluating"):
            if isinstance(batch, (tuple, list)):
                data, target = batch
            else:
                data = batch[0]
                target = batch[1]

            output = model(data)
            if isinstance(output, dict):
                pred = output["out"]
            else:
                pred = output

            all_preds.append(pred)
            all_targets.append(target)

    # 合并结果
    all_preds = paddle.concat(all_preds, axis=0)
    all_targets = paddle.concat(all_targets, axis=0)

    # 计算指标
    logger.info("Computing metrics...")
    metrics = seg_metrics.compute(all_preds, all_targets)
    boundary_metrics = seg_metrics.compute_boundary_metrics(all_preds, all_targets)

    # 计算推理时间
    logger.info("Measuring inference time...")
    time_metrics = compute_inference_time(
        model,
        input_shape=(1, 3, 512, 512),
        use_gpu=paddle.is_compiled_with_cuda()
    )

    # 合并所有指标
    all_metrics = {**metrics, **boundary_metrics, **time_metrics}

    # 打印结果
    logger.info("\n" + "=" * 60)
    logger.info("Segmentation Evaluation Results")
    logger.info("=" * 60)
    for key, value in all_metrics.items():
        logger.info(f"{key}: {value:.4f}")

    # 保存结果
    output_dir = Path(config['output']['reports'])
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "segmentation_evaluation.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(all_metrics, f, indent=2)
    logger.info(f"\nResults saved to {results_path}")

    return all_metrics


def evaluate_classification(config: dict, checkpoint_path: str):
    """评估分类模型"""
    logger.info("=" * 60)
    logger.info("Evaluating Classification Model")
    logger.info("=" * 60)

    # 加载模型
    model = load_model(checkpoint_path, config, "classification")
    model.eval()

    # 创建数据集
    base_path = config['dataset']['base_path']
    val_ann = os.path.join(base_path, config['dataset']['val']['annotations'])
    val_img_dir = os.path.dirname(val_ann)

    val_dataset = TongueClassificationDataset(
        annotation_file=val_ann,
        image_dir=val_img_dir,
        image_size=tuple(config['dataset']['image_size']),
        is_training=False,
        use_multi_label=True
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=config['classification']['training']['batch_size'],
        shuffle=False,
        num_workers=4
    )

    # 获取类别名称
    class_names = []
    for head_name, head_config in config['classification']['multi_head'].items():
        for class_name in head_config.get('names', []):
            class_names.append(f"{head_name}_{class_name}")

    # 创建评估器
    cls_metrics = ClassificationMetrics(
        num_classes=len(class_names),
        class_names=class_names
    )

    # 创建不平衡评估器
    imbalance_metrics = ImbalanceMetrics(
        class_counts={},  # 可以从配置中加载
        threshold_ratio=0.2
    )

    # 评估
    all_preds = {k: [] for k in config['classification']['multi_head'].keys()}
    all_targets = {k: [] for k in config['classification']['multi_head'].keys()}

    logger.info("Running inference...")
    with paddle.no_grad():
        for batch in tqdm(val_loader, desc="Evaluating"):
            if isinstance(batch, (tuple, list)):
                data, target = batch
            else:
                data = batch[0]
                target = batch[1]

            output = model(data)

            for head_name in output.keys():
                all_preds[head_name].append(output[head_name])
                all_targets[head_name].append(target[head_name])

    # 合并结果并计算指标
    logger.info("Computing metrics...")
    head_metrics = {}

    for head_name in all_preds.keys():
        pred = paddle.concat(all_preds[head_name], axis=0)
        target = paddle.concat(all_targets[head_name], axis=0)

        head_class_names = [
            f"{head_name}_{name}"
            for name in config['classification']['multi_head'][head_name].get('names', [])
        ]

        head_cls_metrics = ClassificationMetrics(
            num_classes=pred.shape[1],
            class_names=head_class_names
        )

        head_result = head_cls_metrics.compute(pred, target)
        head_metrics[head_name] = head_result

    # 计算全局指标
    global_metrics = {
        "macro_f1": np.mean([m["macro_f1"] for m in head_metrics.values()]),
        "mAP": np.mean([m["mAP"] for m in head_metrics.values()]),
        "macro_precision": np.mean([m["macro_precision"] for m in head_metrics.values()]),
        "macro_recall": np.mean([m["macro_recall"] for m in head_metrics.values()])
    }

    # 计算推理时间
    logger.info("Measuring inference time...")
    time_metrics = compute_inference_time(
        model,
        input_shape=(1, 3, 512, 512),
        use_gpu=paddle.is_compiled_with_cuda()
    )

    # 合并所有指标
    all_metrics = {**global_metrics, **time_metrics}
    for head_name, head_result in head_metrics.items():
        for k, v in head_result.items():
            all_metrics[f"{head_name}_{k}"] = v

    # 打印结果
    logger.info("\n" + "=" * 60)
    logger.info("Classification Evaluation Results")
    logger.info("=" * 60)
    logger.info(f"Global Metrics:")
    logger.info(f"  Macro F1: {global_metrics['macro_f1']:.4f}")
    logger.info(f"  mAP: {global_metrics['mAP']:.4f}")
    logger.info(f"  Macro Precision: {global_metrics['macro_precision']:.4f}")
    logger.info(f"  Macro Recall: {global_metrics['macro_recall']:.4f}")
    logger.info(f"\nPer-Head Metrics:")
    for head_name, head_result in head_metrics.items():
        logger.info(f"  {head_name}:")
        logger.info(f"    F1: {head_result['macro_f1']:.4f}, "
                   f"AP: {head_result['mAP']:.4f}")

    # 保存结果
    output_dir = Path(config['output']['reports'])
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / "classification_evaluation.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(all_metrics, f, indent=2)
    logger.info(f"\nResults saved to {results_path}")

    return all_metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained models")
    parser.add_argument("--task", type=str, required=True,
                       choices=["segmentation", "classification"],
                       help="Task to evaluate")
    parser.add_argument("--checkpoint", type=str, required=True,
                       help="Path to model checkpoint")
    parser.add_argument("--config", type=str, default="configs/experiment_config.yaml",
                       help="Path to config file")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 评估
    if args.task == "segmentation":
        evaluate_segmentation(config, args.checkpoint)
    else:
        evaluate_classification(config, args.checkpoint)


if __name__ == "__main__":
    main()
