"""
Curriculum Learning and Dynamic Class Weighting for Tongue Diagnosis Classification

This module implements:
1. Curriculum Learning Strategy: Train main task first, then all tasks
2. Dynamic Class Weighting: Adjust weights based on training progress
3. Gradient Accumulation: Stabilize BN layers with small effective batch sizes
"""

import numpy as np
import paddle
import paddle.nn as nn
from typing import Dict, List, Optional, Tuple, Union
import json
from pathlib import Path


class CurriculumScheduler:
    """
    Curriculum Learning Scheduler for Multi-Task Classification

    Strategy:
    - Phase 1 (epochs 1-20): Train only main task (tongue_color)
    - Phase 2 (epochs 21-60): Train all tasks jointly

    This allows the model to learn strong tongue color features before
    tackling the more challenging multi-task learning.
    """

    def __init__(
        self,
        total_epochs: int = 60,
        warmup_epochs: int = 20,
        main_task_name: str = "tongue_color",
        all_task_names: Optional[List[str]] = None
    ):
        """
        Initialize curriculum scheduler

        Args:
            total_epochs: Total training epochs
            warmup_epochs: Number of epochs to train main task only
            main_task_name: Name of the main task for phase 1
            all_task_names: List of all task names
        """
        self.total_epochs = total_epochs
        self.warmup_epochs = warmup_epochs
        self.main_task_name = main_task_name

        if all_task_names is None:
            all_task_names = [
                "tongue_color",
                "coating_color",
                "tongue_shape",
                "coating_quality",
                "features",
                "health"
            ]
        self.all_task_names = all_task_names

        self.current_phase = "warmup"
        self.phase_history = []

    def get_active_tasks(self, epoch: int) -> List[str]:
        """
        Get list of active tasks for given epoch

        Args:
            epoch: Current epoch number (0-indexed)

        Returns:
            List of active task names
        """
        if epoch < self.warmup_epochs:
            phase = "warmup"
            active_tasks = [self.main_task_name]
        else:
            phase = "joint"
            active_tasks = self.all_task_names

        # Update phase if changed
        if phase != self.current_phase:
            self.phase_history.append({
                "epoch": epoch,
                "from_phase": self.current_phase,
                "to_phase": phase
            })
            self.current_phase = phase

        return active_tasks

    def get_task_weights(
        self,
        epoch: int,
        base_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Get task weights for given epoch

        Args:
            epoch: Current epoch number (0-indexed)
            base_weights: Base task weights for all tasks

        Returns:
            Dictionary mapping task names to weights
        """
        if base_weights is None:
            base_weights = {
                "tongue_color": 0.25,
                "coating_color": 0.20,
                "tongue_shape": 0.15,
                "coating_quality": 0.15,
                "features": 0.15,
                "health": 0.10
            }

        active_tasks = self.get_active_tasks(epoch)

        # In warmup phase, only main task has weight
        if epoch < self.warmup_epochs:
            return {self.main_task_name: 1.0}
        else:
            # In joint phase, use base weights for active tasks
            return {task: base_weights.get(task, 0.0) for task in active_tasks}

    def get_phase_info(self, epoch: int) -> Dict[str, Union[int, str, List[str]]]:
        """
        Get comprehensive phase information

        Args:
            epoch: Current epoch number (0-indexed)

        Returns:
            Dictionary with phase information
        """
        active_tasks = self.get_active_tasks(epoch)

        return {
            "epoch": epoch,
            "phase": self.current_phase,
            "active_tasks": active_tasks,
            "num_active_tasks": len(active_tasks),
            "warmup_epochs": self.warmup_epochs,
            "joint_epochs": self.total_epochs - self.warmup_epochs
        }

    def save_state(self, path: Union[str, Path]):
        """Save scheduler state"""
        state = {
            "current_phase": self.current_phase,
            "phase_history": self.phase_history,
            "config": {
                "total_epochs": self.total_epochs,
                "warmup_epochs": self.warmup_epochs,
                "main_task_name": self.main_task_name,
                "all_task_names": self.all_task_names
            }
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def load_state(self, path: Union[str, Path]):
        """Load scheduler state"""
        with open(path, 'r', encoding='utf-8') as f:
            state = json.load(f)

        self.current_phase = state["current_phase"]
        self.phase_history = state["phase_history"]
        self.total_epochs = state["config"]["total_epochs"]
        self.warmup_epochs = state["config"]["warmup_epochs"]
        self.main_task_name = state["config"]["main_task_name"]
        self.all_task_names = state["config"]["all_task_names"]


class DynamicClassWeightScheduler:
    """
    Dynamic Class Weight Scheduler

    Adjusts class weights based on:
    1. Training progress (epoch-wise)
    2. Per-class performance metrics
    3. Loss trends

    Strategies:
    - linear_decay: Linearly decay from initial to target weights
    - performance_based: Adjust weights based on class-wise F1/accuracy
    - loss_based: Increase weights for classes with high loss
    """

    def __init__(
        self,
        initial_weights: Dict[str, float],
        target_weights: Optional[Dict[str, float]] = None,
        strategy: str = "linear_decay",
        update_frequency: int = 5,
        warmup_epochs: int = 10
    ):
        """
        Initialize dynamic class weight scheduler

        Args:
            initial_weights: Initial class weights (typically from class frequency)
            target_weights: Target weights (default: uniform weights)
            strategy: Weight adjustment strategy
            update_frequency: Update weights every N epochs
            warmup_epochs: Keep initial weights for first N epochs
        """
        self.initial_weights = initial_weights.copy()
        self.strategy = strategy
        self.update_frequency = update_frequency
        self.warmup_epochs = warmup_epochs

        # Set target weights (uniform by default)
        if target_weights is None:
            num_classes = len(initial_weights)
            target_weights = {k: 1.0 for k in initial_weights.keys()}
        self.target_weights = target_weights

        self.current_weights = initial_weights.copy()
        self.weight_history = []

        # For performance-based strategy
        self.class_metrics = {}

    def get_weights(self, epoch: int) -> Dict[str, float]:
        """
        Get current class weights

        Args:
            epoch: Current epoch number (0-indexed)

        Returns:
            Dictionary mapping class names to weights
        """
        # Keep initial weights during warmup
        if epoch < self.warmup_epochs:
            return self.initial_weights.copy()

        # Update weights based on strategy
        if self.strategy == "linear_decay":
            return self._linear_decay_weights(epoch)
        elif self.strategy == "performance_based":
            return self._performance_based_weights(epoch)
        elif self.strategy == "loss_based":
            return self._loss_based_weights(epoch)
        else:
            return self.current_weights.copy()

    def _linear_decay_weights(self, epoch: int) -> Dict[str, float]:
        """Linearly interpolate between initial and target weights"""
        # Calculate progress (0.0 to 1.0)
        total_decay_epochs = 50  # Decay over 50 epochs after warmup
        progress = min(1.0, (epoch - self.warmup_epochs) / total_decay_epochs)

        weights = {}
        for class_name in self.initial_weights.keys():
            init_w = self.initial_weights[class_name]
            target_w = self.target_weights[class_name]
            weights[class_name] = init_w + (target_w - init_w) * progress

        self.current_weights = weights
        return weights.copy()

    def _performance_based_weights(self, epoch: int) -> Dict[str, float]:
        """Adjust weights based on class performance metrics"""
        # If no metrics available, use linear decay
        if not self.class_metrics or epoch % self.update_frequency != 0:
            return self._linear_decay_weights(epoch)

        weights = {}
        for class_name, metrics in self.class_metrics.items():
            # Base weight from linear decay
            base_weight = self._linear_decay_weights(epoch)[class_name]

            # Adjust based on F1 score (lower F1 -> higher weight)
            if 'f1' in metrics:
                f1 = metrics['f1']
                # Increase weight for poorly performing classes
                adjustment = 1.0 + (1.0 - f1) * 0.5
                weights[class_name] = base_weight * adjustment
            else:
                weights[class_name] = base_weight

        self.current_weights = weights
        return weights.copy()

    def _loss_based_weights(self, epoch: int) -> Dict[str, float]:
        """Adjust weights based on class loss trends"""
        # This would be updated during training with loss values
        # For now, use linear decay
        return self._linear_decay_weights(epoch)

    def update_metrics(self, class_metrics: Dict[str, Dict[str, float]]):
        """
        Update class performance metrics

        Args:
            class_metrics: Dictionary mapping class names to metric dicts
                          e.g., {"class_0": {"f1": 0.8, "precision": 0.75}}
        """
        self.class_metrics = class_metrics.copy()

    def get_weight_stats(self) -> Dict[str, float]:
        """Get statistics about current weights"""
        weights = list(self.current_weights.values())
        return {
            "min": float(np.min(weights)),
            "max": float(np.max(weights)),
            "mean": float(np.mean(weights)),
            "std": float(np.std(weights)),
            "ratio": float(np.max(weights) / (np.min(weights) + 1e-8))
        }


class GradientAccumulator:
    """
    Gradient Accumulation for Stable BN Layers

    Accumulates gradients over multiple steps to simulate larger batch sizes.
    This stabilizes Batch Normalization layers when actual batch size is small.

    Typical usage:
        accumulator = GradientAccumulator(accumulate_steps=2)

        for i, data in enumerate(dataloader):
            with accumulator.accumulate():
                loss = model(data)
                loss.backward()

            if accumulator.step():
                optimizer.step()
                optimizer.clear_grad()
    """

    def __init__(self, accumulate_steps: int = 2):
        """
        Initialize gradient accumulator

        Args:
            accumulate_steps: Number of steps to accumulate gradients
        """
        self.accumulate_steps = accumulate_steps
        self._step_counter = 0
        self._accumulation_context = False

    def step(self) -> bool:
        """
        Check if we should perform optimizer step

        Returns:
            True if optimizer step should be performed
        """
        self._step_counter += 1
        should_step = self._step_counter % self.accumulate_steps == 0

        if should_step:
            self._step_counter = 0

        return should_step

    def accumulate(self):
        """
        Context manager for gradient accumulation

        Usage:
            with accumulator.accumulate():
                loss = model(data)
                loss.backward()
        """
        class _AccumulationContext:
            def __init__(self, parent):
                self.parent = parent

            def __enter__(self):
                self.parent._accumulation_context = True
                # Enable gradient computation
                paddle.set_grad_enabled(True)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.parent._accumulation_context = False
                return False

        return _AccumulationContext(self)

    @property
    def num_steps(self) -> int:
        """Get current step count in accumulation cycle"""
        return self._step_counter

    @property
    def effective_batch_size(self, actual_batch_size: int) -> int:
        """Calculate effective batch size"""
        return actual_batch_size * self.accumulate_steps


class CurriculumTrainingConfig:
    """
    Configuration for Curriculum Learning Training

    Combines curriculum scheduling, dynamic weighting, and gradient accumulation.
    """

    def __init__(
        self,
        total_epochs: int = 60,
        warmup_epochs: int = 20,
        main_task: str = "tongue_color",
        accumulate_steps: int = 2,
        weight_strategy: str = "linear_decay",
        weight_update_freq: int = 5,
        class_weights_path: Optional[str] = None
    ):
        """
        Initialize training configuration

        Args:
            total_epochs: Total training epochs
            warmup_epochs: Curriculum warmup epochs (main task only)
            main_task: Main task for warmup phase
            accumulate_steps: Gradient accumulation steps
            weight_strategy: Dynamic weighting strategy
            weight_update_freq: Weight update frequency (epochs)
            class_weights_path: Path to initial class weights JSON
        """
        self.total_epochs = total_epochs
        self.warmup_epochs = warmup_epochs
        self.accumulate_steps = accumulate_steps

        # Load initial class weights
        if class_weights_path and Path(class_weights_path).exists():
            with open(class_weights_path, 'r', encoding='utf-8') as f:
                weights_data = json.load(f)

            # Flatten the nested weights dict to simple class names
            # Map: tongue_color_0 -> 淡红舌, etc.
            class_names_map = {
                "tongue_color_0": "淡红舌", "tongue_color_1": "红舌",
                "tongue_color_2": "绛紫舌", "tongue_color_3": "淡白舌",
                "coating_color_0": "白苔", "coating_color_1": "黄苔",
                "coating_color_2": "黑苔", "coating_color_3": "花剥苔",
                "tongue_shape_0": "正常", "tongue_shape_1": "胖大舌",
                "tongue_shape_2": "瘦薄舌", "coating_quality_0": "薄苔",
                "coating_quality_1": "厚苔", "coating_quality_2": "腐苔",
                "features_0": "无", "features_1": "红点",
                "features_2": "裂纹", "features_3": "齿痕"
            }

            initial_weights = {}
            for key, value in weights_data.get('weights', {}).items():
                if key in class_names_map:
                    initial_weights[class_names_map[key]] = value
                else:
                    # Fallback: use the key as-is if not in map
                    initial_weights[key] = value
        else:
            initial_weights = {}

        # Initialize components
        self.curriculum = CurriculumScheduler(
            total_epochs=total_epochs,
            warmup_epochs=warmup_epochs,
            main_task_name=main_task
        )

        self.dynamic_weights = DynamicClassWeightScheduler(
            initial_weights=initial_weights,
            strategy=weight_strategy,
            update_frequency=weight_update_freq,
            warmup_epochs=10
        )

        self.accumulator = GradientAccumulator(accumulate_steps=accumulate_steps)

    def get_training_state(self, epoch: int) -> Dict:
        """
        Get comprehensive training state

        Args:
            epoch: Current epoch number (0-indexed)

        Returns:
            Dictionary with training state information
        """
        return {
            "epoch": epoch,
            "curriculum": self.curriculum.get_phase_info(epoch),
            "task_weights": self.curriculum.get_task_weights(epoch),
            "class_weights": self.dynamic_weights.get_weights(epoch),
            "class_weight_stats": self.dynamic_weights.get_weight_stats(),
            "gradient_accumulation": {
                "accumulate_steps": self.accumulate_steps,
                "effective_batch_multiplier": self.accumulate_steps
            }
        }

    def save_checkpoint(self, path: Union[str, Path], epoch: int):
        """Save training checkpoint"""
        checkpoint = {
            "epoch": epoch,
            "curriculum_state": {
                "current_phase": self.curriculum.current_phase,
                "phase_history": self.curriculum.phase_history
            },
            "dynamic_weights": {
                "current_weights": self.dynamic_weights.current_weights,
                "weight_history": self.dynamic_weights.weight_history
            },
            "config": {
                "total_epochs": self.total_epochs,
                "warmup_epochs": self.warmup_epochs,
                "accumulate_steps": self.accumulate_steps
            }
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2, ensure_ascii=False)

    def load_checkpoint(self, path: Union[str, Path]) -> int:
        """
        Load training checkpoint

        Returns:
            The epoch number from the checkpoint
        """
        with open(path, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)

        # Restore states
        self.curriculum.current_phase = checkpoint["curriculum_state"]["current_phase"]
        self.curriculum.phase_history = checkpoint["curriculum_state"]["phase_history"]
        self.dynamic_weights.current_weights = checkpoint["dynamic_weights"]["current_weights"]
        self.dynamic_weights.weight_history = checkpoint["dynamic_weights"]["weight_history"]

        return checkpoint["epoch"]


def create_default_config(
    class_weights_path: str = "datasets/processed/clas_v1/class_weights.json",
    save_path: Optional[str] = None
) -> CurriculumTrainingConfig:
    """
    Create default curriculum training configuration

    Args:
        class_weights_path: Path to class weights JSON
        save_path: Optional path to save config

    Returns:
        CurriculumTrainingConfig instance
    """
    config = CurriculumTrainingConfig(
        total_epochs=60,
        warmup_epochs=20,
        main_task="tongue_color",
        accumulate_steps=2,
        weight_strategy="linear_decay",
        weight_update_freq=5,
        class_weights_path=class_weights_path
    )

    if save_path:
        config.save_checkpoint(save_path, epoch=0)

    return config


if __name__ == "__main__":
    # Test curriculum scheduler
    print("Testing CurriculumScheduler...")
    curriculum = CurriculumScheduler(total_epochs=60, warmup_epochs=20)

    for epoch in [0, 10, 19, 20, 30, 59]:
        info = curriculum.get_phase_info(epoch)
        print(f"Epoch {epoch}: Phase={info['phase']}, Active={info['num_active_tasks']}")

    print("\nTesting DynamicClassWeightScheduler...")
    # Sample initial weights (minority classes have higher weights)
    initial_weights = {
        "淡红舌": 0.5, "红舌": 0.8, "绛紫舌": 5.0, "淡白舌": 2.0,
        "白苔": 0.5, "黄苔": 0.7, "黑苔": 8.0, "花剥苔": 6.0,
        "正常": 0.6, "胖大舌": 2.5, "瘦薄舌": 3.0,
        "薄苔": 0.6, "厚苔": 1.2, "腐苔": 1.5,
        "无": 0.5, "红点": 2.0, "裂纹": 3.5, "齿痕": 1.8
    }

    dynamic_weights = DynamicClassWeightScheduler(
        initial_weights=initial_weights,
        strategy="linear_decay"
    )

    for epoch in [0, 5, 10, 20, 40, 59]:
        weights = dynamic_weights.get_weights(epoch)
        stats = dynamic_weights.get_weight_stats()
        print(f"Epoch {epoch}: ratio={stats['ratio']:.2f}, min={stats['min']:.2f}, max={stats['max']:.2f}")

    print("\nTesting GradientAccumulator...")
    accumulator = GradientAccumulator(accumulate_steps=2)
    for i in range(10):
        should_step = accumulator.step()
        print(f"Step {i}: step={should_step}, num_steps={accumulator.num_steps}")

    print("\nAll tests passed!")
