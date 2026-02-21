"""
Canary Deployment Module

Provides automated canary deployment and rollback functionality.
"""

from .release_controller import (
    ReleaseController,
    PhaseConfig,
    Phase,
    CANARY_PHASES,
    start_canary_release,
    rollback_release,
    get_current_phase,
)

__all__ = [
    "ReleaseController",
    "PhaseConfig",
    "Phase",
    "CANARY_PHASES",
    "start_canary_release",
    "rollback_release",
    "get_current_phase",
]
