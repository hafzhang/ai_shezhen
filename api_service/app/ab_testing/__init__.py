"""
A/B Testing Traffic Router Module

This module provides traffic routing functionality for A/B testing
different model versions.
"""

from .traffic_router import (
    TrafficRouter,
    ExperimentConfig,
    ModelVersion,
    DEFAULT_EXPERIMENT,
    assign_user_to_group,
    get_model_for_user,
)

__all__ = [
    "TrafficRouter",
    "ExperimentConfig",
    "ModelVersion",
    "DEFAULT_EXPERIMENT",
    "assign_user_to_group",
    "get_model_for_user",
]
