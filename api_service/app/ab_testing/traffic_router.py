"""
A/B Testing Traffic Router

Implements consistent user-to-group assignment for A/B testing.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ModelVersion(Enum):
    """Model version enumeration for A/B testing groups"""
    CONTROL = "control"      # Control group (current version)
    TREATMENT = "treatment"  # Treatment group (new version)


@dataclass
class ExperimentConfig:
    """A/B testing experiment configuration"""
    experiment_id: str
    name: str
    description: str
    traffic_split: Dict[ModelVersion, float] = field(default_factory=lambda: {
        ModelVersion.CONTROL: 0.5,
        ModelVersion.TREATMENT: 0.5
    })
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    min_sample_size: int = 1000
    metrics: List[str] = field(default_factory=lambda: ["accuracy", "latency_p95", "user_satisfaction"])
    status: str = "running"  # running, paused, completed

    def __post_init__(self):
        """Validate traffic split sums to 1.0"""
        total = sum(self.traffic_split.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Traffic split must sum to 1.0, got {total}")


@dataclass
class UserAssignment:
    """User assignment record"""
    user_id: str
    group: ModelVersion
    experiment_id: str
    assigned_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TrafficRouter:
    """
    Traffic router for A/B testing

    Ensures consistent user-to-group assignment using hash-based routing.
    """

    def __init__(self, config: ExperimentConfig):
        """
        Initialize traffic router

        Args:
            config: Experiment configuration
        """
        self.config = config
        self._assignments: Dict[str, UserAssignment] = {}

    def assign_group(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> ModelVersion:
        """
        Assign user to an experiment group

        Uses consistent hashing to ensure the same user always
        gets assigned to the same group.

        Args:
            user_id: User identifier
            session_id: Optional session identifier for session-based assignment

        Returns:
            Assigned model version group
        """
        # Check if already assigned
        if user_id in self._assignments:
            assignment = self._assignments[user_id]
            if assignment.experiment_id == self.config.experiment_id:
                return assignment.group

        # Compute hash-based assignment
        key = f"{self.config.experiment_id}:{user_id}"
        if session_id:
            key += f":{session_id}"

        # Hash and normalize to 0-100 range
        hash_value = int(hashlib.sha256(key.encode()).hexdigest(), 16) % 100

        # Assign based on traffic split
        threshold = 0
        assigned_group = ModelVersion.CONTROL

        for version, split in sorted(
            self.config.traffic_split.items(),
            key=lambda x: x[0].value
        ):
            threshold += split * 100
            if hash_value < threshold:
                assigned_group = version
                break

        # Record assignment
        self._assignments[user_id] = UserAssignment(
            user_id=user_id,
            group=assigned_group,
            experiment_id=self.config.experiment_id
        )

        logger.debug(
            f"Assigned user {user_id} to {assigned_group.value} "
            f"(hash: {hash_value})"
        )

        return assigned_group

    def get_group(self, user_id: str) -> Optional[ModelVersion]:
        """
        Get existing group assignment for user

        Args:
            user_id: User identifier

        Returns:
            Assigned group or None if not assigned
        """
        assignment = self._assignments.get(user_id)
        return assignment.group if assignment else None

    def get_model_path(self, version: ModelVersion) -> str:
        """
        Get model file path for version

        Args:
            version: Model version

        Returns:
            Path to model files
        """
        version_map = {
            ModelVersion.CONTROL: {
                "segment": "/app/models/deploy/segment_fp16",
                "classify": "/app/models/deploy/classify_fp16"
            },
            ModelVersion.TREATMENT: {
                "segment": "/app/models/deploy/segment_v2_fp16",
                "classify": "/app/models/deploy/classify_v2_fp16"
            }
        }
        return version_map.get(version, version_map[ModelVersion.CONTROL])

    def get_stats(self) -> Dict[str, Any]:
        """
        Get experiment statistics

        Returns:
            Statistics dictionary
        """
        group_counts = {ModelVersion.CONTROL: 0, ModelVersion.TREATMENT: 0}
        for assignment in self._assignments.values():
            if assignment.experiment_id == self.config.experiment_id:
                group_counts[assignment.group] += 1

        total = sum(group_counts.values())
        percentages = {
            k.value: (v / total * 100 if total > 0 else 0)
            for k, v in group_counts.items()
        }

        return {
            "experiment_id": self.config.experiment_id,
            "status": self.config.status,
            "total_assignments": total,
            "group_counts": {k.value: v for k, v in group_counts.items()},
            "group_percentages": percentages,
            "target_percentages": {k.value: v * 100 for k, v in self.config.traffic_split.items()},
            "min_sample_size": self.config.min_sample_size,
            "sample_size_reached": total >= self.config.min_sample_size
        }


# Default experiment configuration
DEFAULT_EXPERIMENT = ExperimentConfig(
    experiment_id="exp_001",
    name="Segmentation Model V2 Test",
    description="Testing new segmentation model with improved boundary detection",
    traffic_split={
        ModelVersion.CONTROL: 0.5,
        ModelVersion.TREATMENT: 0.5
    }
)


# Global router instance
_global_router: Optional[TrafficRouter] = None


def get_router() -> TrafficRouter:
    """Get global traffic router instance"""
    global _global_router
    if _global_router is None:
        _global_router = TrafficRouter(DEFAULT_EXPERIMENT)
    return _global_router


def assign_user_to_group(
    user_id: str,
    session_id: Optional[str] = None
) -> ModelVersion:
    """
    Convenience function to assign user to group

    Args:
        user_id: User identifier
        session_id: Optional session identifier

    Returns:
        Assigned model version
    """
    router = get_router()
    return router.assign_group(user_id, session_id)


def get_model_for_user(
    user_id: str,
    model_type: str = "segment"
) -> str:
    """
    Get model path for user

    Args:
        user_id: User identifier
        model_type: Type of model (segment/classify)

    Returns:
        Path to model files
    """
    router = get_router()
    group = router.assign_group(user_id)
    paths = router.get_model_path(group)
    return paths.get(model_type, paths["segment"])
