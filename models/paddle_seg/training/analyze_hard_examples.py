#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Hard Example Analysis and Visualization Tool

Analyzes hard examples from training to understand:
- Which samples are consistently difficult
- Common patterns in hard examples
- Improvement after retraining

task-2-4: 难例挖掘与重训练

Usage:
    # Analyze hard examples from a training run
    python -m models.paddle_seg.training.analyze_hard_examples \
        --mining-dir models/paddle_seg/output/hard_mining \
        --train-data datasets/processed/seg_v1/train

    # Generate comparison report
    python -m models.paddle_seg.training.analyze_hard_examples \
        --mining-dir models/paddle_seg/output/hard_mining \
        --train-data datasets/processed/seg_v1/train \
        --compare-epochs 5,10,20,30,40,50
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import argparse
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HardExampleAnalyzer:
    """Analyzer for hard example mining results."""

    def __init__(self, mining_dir: str, train_data_dir: str):
        """
        Initialize analyzer.

        Args:
            mining_dir: Directory containing hard example mining results
            train_data_dir: Directory containing training images and masks
        """
        self.mining_dir = Path(mining_dir)
        self.train_data_dir = Path(train_data_dir)
        self.images_dir = self.train_data_dir / 'images'
        self.masks_dir = self.train_data_dir / 'masks'

        # Load mining data
        self.hard_examples_by_epoch = {}
        self.mining_statistics = {}
        self._load_mining_data()

    def _load_mining_data(self):
        """Load hard example data from JSON files."""
        # Load statistics
        stats_file = self.mining_dir / 'mining_statistics.json'
        if stats_file.exists():
            with open(stats_file, 'r') as f:
                self.mining_statistics = json.load(f)
            logger.info(f"Loaded mining statistics from {stats_file}")

        # Load hard examples per epoch
        for epoch_file in sorted(self.mining_dir.glob('hard_examples_epoch_*.json')):
            with open(epoch_file, 'r') as f:
                data = json.load(f)
                epoch = data['epoch']
                self.hard_examples_by_epoch[epoch] = data['hard_indices']
            logger.info(f"Loaded {len(data['hard_indices'])} hard examples from epoch {epoch}")

    def get_persistent_hard_examples(self, min_occurrences: int = 3) -> Dict[int, int]:
        """
        Get samples that are consistently selected as hard.

        Args:
            min_occurrences: Minimum number of times a sample must be selected

        Returns:
            Dictionary mapping sample index to number of selections
        """
        from collections import Counter

        all_hard_indices = []
        for indices in self.hard_examples_by_epoch.values():
            all_hard_indices.extend(indices)

        counter = Counter(all_hard_indices)
        persistent = {idx: count for idx, count in counter.items()
                      if count >= min_occurrences}

        logger.info(f"Found {len(persistent)} persistent hard examples "
                   f"(selected >= {min_occurrences} times)")

        return persistent

    def get_trending_hard_examples(self, window_size: int = 5) -> Dict[int, str]:
        """
        Identify hard examples with specific trends.

        Args:
            window_size: Number of recent epochs to consider

        Returns:
            Dictionary mapping sample index to trend type
        """
        sorted_epochs = sorted(self.hard_examples_by_epoch.keys())
        if len(sorted_epochs) < window_size:
            return {}

        recent_epochs = sorted_epochs[-window_size:]
        trends = {}

        # Track occurrence frequency in recent epochs
        for idx in range(10000):  # Assume max 10k samples
            recent_count = sum(
                1 for epoch in recent_epochs
                if idx in self.hard_examples_by_epoch[epoch]
            )

            if recent_count >= window_size - 1:
                trends[idx] = 'persistent'
            elif recent_count >= window_size // 2:
                trends[idx] = 'emerging'

        return trends

    def generate_statistics_report(self) -> str:
        """Generate a comprehensive statistics report."""
        lines = [
            "=" * 80,
            "HARD EXAMPLE MINING ANALYSIS REPORT",
            "=" * 80,
            "",
            f"Mining Directory: {self.mining_dir}",
            f"Training Data: {self.train_data_dir}",
            "",
            "-" * 80,
            "MINING STATISTICS",
            "-" * 80,
        ]

        if self.mining_statistics:
            for key, value in self.mining_statistics.items():
                if key == 'most_common_hard_samples':
                    lines.append(f"\nMost Common Hard Samples (Top 20):")
                    for item in value[:20]:
                        idx = item['index']
                        count = item['times_selected']
                        lines.append(f"  Sample {idx:5d}: Selected {count:2d} times")
                else:
                    lines.append(f"{key}: {value}")

        lines.extend([
            "",
            "-" * 80,
            "EPOCH-BY-EPOCH SUMMARY",
            "-" * 80,
        ])

        sorted_epochs = sorted(self.hard_examples_by_epoch.keys())
        for epoch in sorted_epochs:
            hard_indices = self.hard_examples_by_epoch[epoch]
            num_hard = len(hard_indices)
            lines.append(f"Epoch {epoch:4d}: {num_hard:4d} hard samples")

        lines.extend([
            "",
            "-" * 80,
            "PERSISTENT HARD EXAMPLES",
            "-" * 80,
        ])

        persistent = self.get_persistent_hard_examples(min_occurrences=3)
        sorted_persistent = sorted(persistent.items(), key=lambda x: x[1], reverse=True)

        lines.append(f"Found {len(sorted_persistent)} samples selected 3+ times:\n")
        for idx, count in sorted_persistent[:50]:
            lines.append(f"  Sample {idx:5d}: Selected {count:2d} times")

        if len(sorted_persistent) > 50:
            lines.append(f"  ... and {len(sorted_persistent) - 50} more")

        lines.extend([
            "",
            "-" * 80,
            "IMPROVEMENT ANALYSIS",
            "-" * 80,
        ])

        # Analyze if hard examples are improving over epochs
        if len(sorted_epochs) >= 2:
            first_half = sorted_epochs[:len(sorted_epochs)//2]
            second_half = sorted_epochs[len(sorted_epochs)//2:]

            first_hard = set()
            for epoch in first_half:
                first_hard.update(self.hard_examples_by_epoch.get(epoch, []))

            second_hard = set()
            for epoch in second_half:
                second_hard.update(self.hard_examples_by_epoch.get(epoch, []))

            # Calculate overlap
            overlap = len(first_hard & second_hard)
            unique_first = len(first_hard - second_hard)
            unique_second = len(second_hard - first_hard)

            lines.extend([
                f"First half (epochs 1-{sorted_epochs[len(sorted_epochs)//2]}): {len(first_hard)} unique samples",
                f"Second half (epochs {sorted_epochs[len(sorted_epochs)//2+1]}-{sorted_epochs[-1]}): {len(second_hard)} unique samples",
                f"Overlap: {overlap} samples ({overlap/max(len(first_hard), 1)*100:.1f}%)",
                f"Resolved in first half: {unique_first} samples",
                f"New hard examples in second half: {unique_second} samples",
            ])

            # Interpretation
            if overlap < len(first_hard) * 0.3:
                lines.append("\nInterpretation: Good! Most hard examples were resolved in early training.")
            elif overlap < len(first_hard) * 0.6:
                lines.append("\nInterpretation: Moderate. Some hard examples persist.")
            else:
                lines.append("\nInterpretation: Concern. Many hard examples remain difficult.")

        lines.extend(["", "=" * 80])

        return "\n".join(lines)

    def save_visualization(
        self,
        output_path: str,
        num_samples: int = 50,
        show_predictions: bool = False
    ):
        """
        Generate comprehensive visualization of hard examples.

        Args:
            output_path: Path to save visualization
            num_samples: Number of hard examples to visualize
            show_predictions: Whether to show prediction masks (if available)
        """
        # Get most persistent hard examples
        persistent = self.get_persistent_hard_examples(min_occurrences=2)
        sorted_persistent = sorted(persistent.items(), key=lambda x: x[1], reverse=True)

        # Get image and mask file names
        image_files = sorted([f for f in os.listdir(self.images_dir)
                            if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        num_viz = min(num_samples, len(sorted_persistent))

        # Create figure with grid layout
        samples_per_row = 5
        num_rows = (num_viz + samples_per_row - 1) // samples_per_row
        fig = plt.figure(figsize=(samples_per_row * 4, num_rows * 3))
        gs = GridSpec(num_rows, samples_per_row, figure=fig, hspace=0.3, wspace=0.2)

        for i, (idx, count) in enumerate(sorted_persistent[:num_viz]):
            row = i // samples_per_row
            col = i % samples_per_row

            # Get image and mask paths
            if idx < len(image_files):
                img_name = image_files[idx]
                mask_name = img_name.rsplit('.', 1)[0] + '.png'

                img_path = self.images_dir / img_name
                mask_path = self.masks_dir / mask_name

                try:
                    # Load image and mask
                    image = Image.open(img_path)
                    mask = Image.open(mask_path)

                    # Create subplot
                    ax = fig.add_subplot(gs[row, col])

                    # Create overlay
                    img_array = np.array(image)
                    mask_array = np.array(mask)

                    # Resize to match
                    if img_array.shape[:2] != mask_array.shape:
                        mask_array = np.array(mask.resize(img_array.shape[:2][::-1]))

                    # Display image
                    ax.imshow(img_array)

                    # Overlay mask
                    mask_overlay = np.zeros((*mask_array.shape, 4), dtype=np.uint8)
                    mask_overlay[:, :, 0] = 255  # Red
                    mask_overlay[:, :, 3] = (mask_array > 127).astype(np.uint8) * 100  # Alpha
                    ax.imshow(mask_overlay)

                    ax.set_title(f"#{idx}: {count}x", fontsize=10)
                    ax.axis('off')

                except Exception as e:
                    logger.warning(f"Could not load sample {idx}: {e}")
                    ax = fig.add_subplot(gs[row, col])
                    ax.text(0.5, 0.5, f"Sample {idx}\nError: {str(e)[:20]}",
                           ha='center', va='center')
                    ax.axis('off')

        # Add legend
        legend_patches = [
            mpatches.Patch(color='red', alpha=0.4, label='Tongue Mask'),
        ]
        fig.legend(handles=legend_patches, loc='upper center',
                 bbox_to_anchor=(0.5, 0.99), ncol=2)

        plt.suptitle(f"Most Persistent Hard Examples (Top {num_viz})",
                    fontsize=14, y=0.995)

        plt.savefig(output_path, dpi=100, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved visualization to {output_path}")

    def export_hard_example_list(
        self,
        output_path: str,
        min_occurrences: int = 2
    ):
        """
        Export list of hard examples to CSV for manual review.

        Args:
            output_path: Path to save CSV
            min_occurrences: Minimum occurrences to include
        """
        persistent = self.get_persistent_hard_examples(min_occurrences=min_occurrences)
        sorted_persistent = sorted(persistent.items(), key=lambda x: x[1], reverse=True)

        # Get image file names
        image_files = sorted([f for f in os.listdir(self.images_dir)
                            if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("sample_index,times_selected,filename\n")
            for idx, count in sorted_persistent:
                if idx < len(image_files):
                    f.write(f"{idx},{count},{image_files[idx]}\n")

        logger.info(f"Exported {len(sorted_persistent)} hard examples to {output_path}")

    def generate_comparison_report(
        self,
        epochs: List[int],
        output_path: str
    ):
        """
        Generate comparison report across multiple epochs.

        Args:
            epochs: List of epoch numbers to compare
            output_path: Path to save report
        """
        lines = [
            "=" * 80,
            "HARD EXAMPLE COMPARISON ACROSS EPOCHS",
            "=" * 80,
            "",
            f"Comparing epochs: {epochs}",
            "",
            "-" * 80,
        ]

        # Get hard examples for each epoch
        epoch_hard_sets = {}
        for epoch in epochs:
            if epoch in self.hard_examples_by_epoch:
                epoch_hard_sets[epoch] = set(self.hard_examples_by_epoch[epoch])

        # Generate comparison matrix
        lines.append("\nOverlap Matrix (number of common hard examples):\n")

        header = "Epoch".rjust(8)
        for e1 in epochs:
            header += f" | {e1:5d}"
        lines.append(header)
        lines.append("-" * (8 + len(epochs) * 8))

        for e1 in epochs:
            row = f"{e1:7d} "
            for e2 in epochs:
                if e1 in epoch_hard_sets and e2 in epoch_hard_sets:
                    overlap = len(epoch_hard_sets[e1] & epoch_hard_sets[e2])
                    pct = overlap / max(len(epoch_hard_sets[e1]), 1) * 100
                    row += f" | {overlap:4d} "
                else:
                    row += f" |  --  "
            lines.append(row)

        # Analysis
        lines.extend([
            "",
            "-" * 80,
            "ANALYSIS",
            "-" * 80,
        ])

        if len(epochs) >= 2:
            first = epochs[0]
            last = epochs[-1]

            if first in epoch_hard_sets and last in epoch_hard_sets:
                first_set = epoch_hard_sets[first]
                last_set = epoch_hard_sets[last]

                overlap = len(first_set & last_set)
                new_hard = len(last_set - first_set)
                resolved = len(first_set - last_set)

                lines.extend([
                    f"From Epoch {first} to {last}:",
                    f"  Overlap (still hard): {overlap} samples",
                    f"  Newly hard: {new_hard} samples",
                    f"  Resolved (no longer hard): {resolved} samples",
                    "",
                ])

                if resolved > overlap:
                    lines.append("Interpretation: Good progress! Many hard examples were resolved.")
                elif resolved > 0:
                    lines.append("Interpretation: Moderate progress. Some resolution occurred.")
                else:
                    lines.append("Interpretation: Limited progress. Hard examples persist.")

        lines.append("")
        lines.append("=" * 80)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        logger.info(f"Saved comparison report to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Hard Example Analysis Tool")
    parser.add_argument("--mining-dir", type=str, required=True,
                       help="Directory containing hard example mining results")
    parser.add_argument("--train-data", type=str, required=True,
                       help="Directory containing training images and masks")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory for reports (default: mining_dir)")
    parser.add_argument("--num-samples", type=int, default=50,
                       help="Number of samples to visualize")
    parser.add_argument("--min-occurrences", type=int, default=2,
                       help="Minimum occurrences for persistent hard examples")
    parser.add_argument("--compare-epochs", type=str, default=None,
                       help="Comma-separated list of epochs to compare")

    args = parser.parse_args()

    # Setup output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(args.mining_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create analyzer
    analyzer = HardExampleAnalyzer(args.mining_dir, args.train_data)

    # Generate statistics report
    stats_report = analyzer.generate_statistics_report()
    stats_path = output_dir / 'analysis_report.txt'
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write(stats_report)
    print(f"\n{stats_report}")
    print(f"\nSaved report to {stats_path}")

    # Generate visualization
    viz_path = output_dir / 'hard_examples_visualization.png'
    analyzer.save_visualization(str(viz_path), num_samples=args.num_samples)

    # Export hard example list
    csv_path = output_dir / 'hard_examples_list.csv'
    analyzer.export_hard_example_list(str(csv_path), min_occurrences=args.min_occurrences)

    # Generate comparison report if requested
    if args.compare_epochs:
        epochs = [int(e.strip()) for e in args.compare_epochs.split(',')]
        compare_path = output_dir / 'epoch_comparison_report.txt'
        analyzer.generate_comparison_report(epochs, str(compare_path))

    print("\nAnalysis complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
