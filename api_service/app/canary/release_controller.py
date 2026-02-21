"""
Canary Deployment Release Controller

Automates the canary deployment process with automatic monitoring
and rollback capabilities.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class Phase(Enum):
    """Canary deployment phases"""
    INTERNAL = "internal"
    CANARY_5 = "canary_5"
    CANARY_10 = "canary_10"
    CANARY_25 = "canary_25"
    CANARY_50 = "canary_50"
    CANARY_75 = "canary_75"
    CANARY_100 = "canary_100"


@dataclass
class PhaseConfig:
    """Canary phase configuration"""
    phase: Phase
    traffic_percentage: int
    min_duration_hours: int
    success_criteria: Dict[str, str] = field(default_factory=dict)
    rollback_triggers: Dict[str, str] = field(default_factory=dict)

    def get_duration_seconds(self) -> int:
        """Get minimum duration in seconds"""
        return self.min_duration_hours * 3600


# Default canary deployment phases
CANARY_PHASES: List[PhaseConfig] = [
    PhaseConfig(
        phase=Phase.INTERNAL,
        traffic_percentage=0,
        min_duration_hours=24,
        success_criteria={"accuracy": ">0.90", "latency_p95": "<500"},
        rollback_triggers={"error_rate": ">0.05"}
    ),
    PhaseConfig(
        phase=Phase.CANARY_5,
        traffic_percentage=5,
        min_duration_hours=48,
        success_criteria={"accuracy": ">0.90", "latency_p95": "<500"},
        rollback_triggers={"error_rate": ">0.05", "user_satisfaction": "<0.80"}
    ),
    PhaseConfig(
        phase=Phase.CANARY_10,
        traffic_percentage=10,
        min_duration_hours=48,
        success_criteria={"accuracy": ">0.90", "latency_p95": "<500"},
        rollback_triggers={"error_rate": ">0.03", "user_satisfaction": "<0.85"}
    ),
    PhaseConfig(
        phase=Phase.CANARY_25,
        traffic_percentage=25,
        min_duration_hours=72,
        success_criteria={"accuracy": ">0.91", "latency_p95": "<480"},
        rollback_triggers={"error_rate": ">0.02", "user_satisfaction": "<0.88"}
    ),
    PhaseConfig(
        phase=Phase.CANARY_50,
        traffic_percentage=50,
        min_duration_hours=72,
        success_criteria={"accuracy": ">0.91", "latency_p95": "<480"},
        rollback_triggers={"error_rate": ">0.015", "user_satisfaction": "<0.90"}
    ),
    PhaseConfig(
        phase=Phase.CANARY_75,
        traffic_percentage=75,
        min_duration_hours=96,
        success_criteria={"accuracy": ">0.92", "latency_p95": "<450"},
        rollback_triggers={"error_rate": ">0.01", "user_satisfaction": "<0.92"}
    ),
    PhaseConfig(
        phase=Phase.CANARY_100,
        traffic_percentage=100,
        min_duration_hours=168,
        success_criteria={"accuracy": ">0.92", "latency_p95": "<450"},
        rollback_triggers={"error_rate": ">0.01", "user_satisfaction": "<0.92"}
    ),
]


@dataclass
class ReleaseStatus:
    """Release status information"""
    version: str
    current_phase: Phase
    phase_start_time: datetime
    is_running: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    total_phases: int = 7
    completed_phases: int = 0


class ReleaseController:
    """
    Canary deployment release controller

    Manages automated canary deployment with monitoring and rollback.
    """

    def __init__(
        self,
        phases: List[PhaseConfig] = None,
        check_interval_seconds: int = 300
    ):
        """
        Initialize release controller

        Args:
            phases: List of phase configurations
            check_interval_seconds: Interval between metric checks
        """
        self.phases = phases or CANARY_PHASES
        self.check_interval_seconds = check_interval_seconds
        self.current_phase_index = 0
        self.phase_start_time: Optional[datetime] = None
        self.is_running = False
        self.current_model_version: Optional[str] = None
        self.previous_model_version: Optional[str] = None

    async def start_release(
        self,
        new_model_version: str,
        previous_model_version: Optional[str] = None
    ) -> ReleaseStatus:
        """
        Start canary release process

        Args:
            new_model_version: New model version to deploy
            previous_model_version: Previous version for rollback

        Returns:
            Initial release status
        """
        logger.info(f"Starting canary release for model: {new_model_version}")

        self.current_model_version = new_model_version
        self.previous_model_version = previous_model_version
        self.is_running = True
        self.current_phase_index = 0
        self.phase_start_time = datetime.now()

        # Enter first phase
        await self._enter_phase(new_model_version)

        # Return initial status
        return self.get_status()

    async def _enter_phase(self, model_version: str):
        """Enter current phase and update traffic"""
        phase = self.phases[self.current_phase_index]
        phase_name = phase.phase.value

        logger.info(
            f"Entering phase: {phase_name}, "
            f"traffic: {phase.traffic_percentage}%"
        )

        # Update traffic allocation
        await self._update_traffic_split(model_version, phase.traffic_percentage)

    async def _update_traffic_split(self, model_version: str, percentage: int):
        """
        Update traffic split between versions

        Args:
            model_version: New model version
            percentage: Traffic percentage for new version
        """
        # This would integrate with load balancer/proxy
        logger.info(
            f"Setting traffic: {percentage}% to {model_version}, "
            f"{100-percentage}% to previous version"
        )
        # Implementation would update Nginx/Envoy/HAProxy config

    async def monitor_and_advance(self) -> Optional[ReleaseStatus]:
        """
        Monitor current phase and advance if criteria met

        Returns:
            Updated status or None if no change
        """
        if not self.is_running:
            return None

        phase = self.phases[self.current_phase_index]
        elapsed = datetime.now() - self.phase_start_time

        # Check minimum duration
        if elapsed < timedelta(seconds=phase.get_duration_seconds()):
            logger.debug(
                f"Phase minimum duration not met: "
                f"{elapsed} / {phase.min_duration_hours}h"
            )
            return self.get_status()

        # Collect current metrics
        metrics = await self._collect_metrics()

        # Check rollback triggers
        if self._should_rollback(phase, metrics):
            logger.warning("Rollback triggers met, initiating rollback...")
            await self.rollback()
            return self.get_status()

        # Check success criteria
        if self._meets_success_criteria(phase, metrics):
            logger.info("Phase success criteria met, advancing...")
            self.current_phase_index += 1
            self.completed_phases += 1

            if self.current_phase_index >= len(self.phases):
                logger.info("All phases completed successfully!")
                self.is_running = False
            else:
                self.phase_start_time = datetime.now()
                await self._enter_phase(self.current_model_version)

        return self.get_status()

    async def _collect_metrics(self) -> Dict[str, float]:
        """
        Collect current metrics from monitoring system

        Returns:
            Dictionary of metric values
        """
        # In production, this would query Prometheus
        return {
            "accuracy": 0.92,
            "latency_p95": 450,
            "error_rate": 0.01,
            "user_satisfaction": 0.93
        }

    def _should_rollback(self, phase: PhaseConfig, metrics: Dict[str, float]) -> bool:
        """Check if rollback should be triggered"""
        for metric, trigger in phase.rollback_triggers.items():
            value = metrics.get(metric)
            if value is None:
                continue

            op, threshold = trigger[0], float(trigger[1:])

            if op == ">" and value > threshold:
                logger.warning(
                    f"Rollback trigger: {metric}={value:.3f} {trigger}"
                )
                return True
            elif op == "<" and value < threshold:
                logger.warning(
                    f"Rollback trigger: {metric}={value:.3f} {trigger}"
                )
                return True

        return False

    def _meets_success_criteria(self, phase: PhaseConfig, metrics: Dict[str, float]) -> bool:
        """Check if success criteria are met"""
        for metric, criterion in phase.success_criteria.items():
            value = metrics.get(metric)
            if value is None:
                logger.debug(f"Metric {metric} not available yet")
                return False

            op, threshold = criterion[0], float(criterion[1:])

            if op == ">" and value <= threshold:
                logger.debug(
                    f"Success criteria not met: {metric}={value:.3f} {criterion}"
                )
                return False
            elif op == "<" and value >= threshold:
                logger.debug(
                    f"Success criteria not met: {metric}={value:.3f} {criterion}"
                )
                return False

        return True

    async def rollback(self, reason: str = "Manual rollback") -> bool:
        """
        Rollback to previous version

        Args:
            reason: Reason for rollback

        Returns:
            True if rollback successful
        """
        logger.warning(f"Initiating rollback: {reason}")

        if self.previous_model_version:
            # Switch all traffic to previous version
            await self._update_traffic_split(self.previous_model_version, 100)
            logger.info(f"Rolled back to {self.previous_model_version}")
        else:
            logger.error("No previous version available for rollback")
            return False

        self.is_running = False
        return True

    def get_status(self) -> ReleaseStatus:
        """Get current release status"""
        return ReleaseStatus(
            version=self.current_model_version or "unknown",
            current_phase=self.phases[self.current_phase_index].phase,
            phase_start_time=self.phase_start_time or datetime.now(),
            is_running=self.is_running,
            total_phases=len(self.phases),
            completed_phases=self.current_phase_index
        )

    def stop(self):
        """Stop the release process"""
        logger.info("Stopping release process")
        self.is_running = False


# Global controller instance
_global_controller: Optional[ReleaseController] = None


def get_controller() -> ReleaseController:
    """Get global release controller instance"""
    global _global_controller
    if _global_controller is None:
        _global_controller = ReleaseController()
    return _global_controller


async def start_canary_release(
    model_version: str,
    previous_version: Optional[str] = None
) -> ReleaseStatus:
    """
    Start a new canary release

    Args:
        model_version: New model version
        previous_version: Previous version for rollback

    Returns:
        Release status
    """
    controller = get_controller()
    return await controller.start_release(model_version, previous_version)


async def rollback_release(reason: str = "Manual rollback") -> bool:
    """
    Rollback current release

    Args:
        reason: Reason for rollback

    Returns:
        True if successful
    """
    controller = get_controller()
    return await controller.rollback(reason)


def get_current_phase() -> Optional[Phase]:
    """Get current deployment phase"""
    controller = get_controller()
    status = controller.get_status()
    return status.current_phase
