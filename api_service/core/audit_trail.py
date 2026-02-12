#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
审计追踪模块

Audit trail module for compliance and traceability.
Ensures complete logging of diagnosis workflows with tamper-evident storage.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

from api_service.core.config import settings


# Get audit logger
audit_logger = logging.getLogger("audit")


@dataclass
class AuditEvent:
    """审计事件数据类

    Immutable audit event record for tamper-evidence.
    """
    event_id: str
    timestamp: str
    event_type: str
    user_id: Optional[str]
    session_id: str
    request_id: str
    source_ip: str
    user_agent: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    status: str
    details: Dict[str, Any]
    checksum: str

    def __post_init__(self):
        """Calculate checksum for tamper detection"""
        data_to_hash = self._get_hashable_data()
        self.checksum = hashlib.sha256(data_to_hash.encode('utf-8')).hexdigest()

    def _get_hashable_data(self) -> str:
        """Get data string for hash calculation"""
        return json.dumps({
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'status': self.status,
            'details': self.details
        }, sort_keys=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding checksum"""
        d = asdict(self)
        d.pop('checksum', None)
        return d

    def verify_checksum(self) -> bool:
        """Verify event hasn't been tampered with"""
        expected_checksum = self.checksum
        actual_checksum = hashlib.sha256(self._get_hashable_data().encode('utf-8')).hexdigest()
        return expected_checksum == actual_checksum


class AuditTrailManager:
    """审计追踪管理器

    Manages audit trail with WORM (Write Once Read Many) semantics.
    """

    def __init__(self, log_file_path: str = None):
        """Initialize audit trail manager

        Args:
            log_file_path: Path to audit log file
        """
        self.log_file_path = log_file_path or settings.AUDIT_LOG_PATH
        self._ensure_log_directory()

    def _ensure_log_directory(self):
        """Ensure log directory exists"""
        log_dir = Path(self.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        action: str,
        resource_type: str,
        status: str,
        request_id: str,
        source_ip: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log an audit event

        Args:
            event_type: Type of event (diagnosis, api_access, etc.)
            action: Action performed (create, read, update, delete)
            resource_type: Type of resource (image, diagnosis, etc.)
            status: Status of the event (success, failure)
            request_id: Unique request identifier
            source_ip: Client IP address
            user_id: User identifier (optional)
            session_id: Session identifier (optional)
            resource_id: Resource identifier (optional)
            user_agent: User agent string (optional)
            details: Additional event details (optional)

        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        timestamp = datetime.now().isoformat()

        event = AuditEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type=event_type,
            user_id=user_id,
            session_id=session_id or self._generate_session_id(),
            request_id=request_id,
            source_ip=source_ip,
            user_agent=user_agent,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            details=details or {},
            checksum=""  # Will be set in __post_init__
        )

        # Log to audit logger (JSON format)
        audit_logger.info(json.dumps(event.to_dict(), ensure_ascii=False))

        # Also append to WORM file for tamper-evidence
        self._append_to_worm_log(event)

        return event_id

    def log_diagnosis_workflow(
        self,
        request_id: str,
        source_ip: str,
        image_id: str,
        diagnosis_type: str,
        workflow_steps: List[Dict[str, Any]],
        final_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> str:
        """Log complete diagnosis workflow

        Args:
            request_id: Unique request identifier
            source_ip: Client IP address
            image_id: Image identifier
            diagnosis_type: Type of diagnosis (segment, classify, diagnose)
            workflow_steps: List of workflow steps with timing and status
            final_result: Final diagnosis result (if successful)
            error_message: Error message (if failed)

        Returns:
            Event ID
        """
        details = {
            "image_id": image_id,
            "diagnosis_type": diagnosis_type,
            "workflow_steps": workflow_steps,
            "step_count": len(workflow_steps),
            "total_duration_ms": sum(
                step.get("duration_ms", 0) for step in workflow_steps
            )
        }

        if final_result:
            details["result"] = self._sanitize_result(final_result)

        if error_message:
            details["error"] = error_message

        status = "success" if final_result else "failure"

        return self.log_event(
            event_type="diagnosis_workflow",
            action="execute",
            resource_type="diagnosis",
            resource_id=image_id,
            status=status,
            request_id=request_id,
            source_ip=source_ip,
            details=details
        )

    def log_data_access(
        self,
        request_id: str,
        source_ip: str,
        resource_type: str,
        resource_id: str,
        access_type: str,
        user_id: Optional[str] = None
    ) -> str:
        """Log data access event

        Args:
            request_id: Unique request identifier
            source_ip: Client IP address
            resource_type: Type of resource accessed
            resource_id: Resource identifier
            access_type: Type of access (read, write, delete)
            user_id: User identifier (optional)

        Returns:
            Event ID
        """
        return self.log_event(
            event_type="data_access",
            action=access_type,
            resource_type=resource_type,
            resource_id=resource_id,
            status="success",
            request_id=request_id,
            source_ip=source_ip,
            user_id=user_id,
            details={"access_type": access_type}
        )

    def log_configuration_change(
        self,
        request_id: str,
        source_ip: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        user_id: Optional[str] = None
    ) -> str:
        """Log configuration change

        Args:
            request_id: Unique request identifier
            source_ip: Client IP address
            config_key: Configuration key changed
            old_value: Previous value
            new_value: New value
            user_id: User identifier (optional)

        Returns:
            Event ID
        """
        return self.log_event(
            event_type="configuration_change",
            action="update",
            resource_type="config",
            resource_id=config_key,
            status="success",
            request_id=request_id,
            source_ip=source_ip,
            user_id=user_id,
            details={
                "config_key": config_key,
                "old_value": str(old_value),
                "new_value": str(new_value)
            }
        )

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_bytes = os.urandom(4).hex()
        return f"evt_{timestamp}_{random_bytes}"

    def _generate_session_id(self) -> str:
        """Generate session ID"""
        timestamp = datetime.now().strftime("%Y%m%d")
        random_bytes = os.urandom(8).hex()
        return f"sess_{timestamp}_{random_bytes}"

    def _append_to_worm_log(self, event: AuditEvent):
        """Append event to WORM log file

        WORM (Write Once Read Many) - append only, no modification.
        """
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                # Append hash for tamper-evidence
                log_entry = {
                    **event.to_dict(),
                    'checksum': event.checksum
                }
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            audit_logger.error(f"Failed to write to WORM log: {e}")

    def _sanitize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize result for logging (remove sensitive data)

        Args:
            result: Raw result dictionary

        Returns:
            Sanitized result
        """
        # Remove sensitive fields
        sensitive_keys = ['patient_id', 'personal_info', 'contact']
        sanitized = result.copy()

        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "[REDACTED]"

        return sanitized

    def verify_audit_trail(self) -> Dict[str, Any]:
        """Verify audit trail integrity

        Returns:
            Verification report with tampered events (if any)
        """
        report = {
            "total_events": 0,
            "tampered_events": [],
            "verified": True
        }

        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event_data = json.loads(line)
                        checksum = event_data.pop('checksum', None)

                        # Recalculate checksum
                        data_string = json.dumps(event_data, sort_keys=True)
                        expected_checksum = hashlib.sha256(
                            data_string.encode('utf-8')
                        ).hexdigest()

                        if checksum != expected_checksum:
                            report["tampered_events"].append({
                                "line_number": line_num,
                                "event_id": event_data.get('event_id'),
                                "expected_checksum": expected_checksum,
                                "actual_checksum": checksum
                            })
                            report["verified"] = False

                        report["total_events"] += 1

                    except json.JSONDecodeError:
                        continue

        except FileNotFoundError:
            report["error"] = "Audit log file not found"

        return report


# Global audit trail manager instance
_audit_manager: Optional[AuditTrailManager] = None


def get_audit_manager() -> AuditTrailManager:
    """Get global audit trail manager instance"""
    global _audit_manager
    if _audit_manager is None:
        _audit_manager = AuditTrailManager()
    return _audit_manager


# Convenience functions
def log_diagnosis_workflow(
    request_id: str,
    source_ip: str,
    image_id: str,
    diagnosis_type: str,
    workflow_steps: List[Dict[str, Any]],
    final_result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
) -> str:
    """Log diagnosis workflow event"""
    manager = get_audit_manager()
    return manager.log_diagnosis_workflow(
        request_id=request_id,
        source_ip=source_ip,
        image_id=image_id,
        diagnosis_type=diagnosis_type,
        workflow_steps=workflow_steps,
        final_result=final_result,
        error_message=error_message
    )


def log_data_access(
    request_id: str,
    source_ip: str,
    resource_type: str,
    resource_id: str,
    access_type: str,
    user_id: Optional[str] = None
) -> str:
    """Log data access event"""
    manager = get_audit_manager()
    return manager.log_data_access(
        request_id=request_id,
        source_ip=source_ip,
        resource_type=resource_type,
        resource_id=resource_id,
        access_type=access_type,
        user_id=user_id
    )


def log_configuration_change(
    request_id: str,
    source_ip: str,
    config_key: str,
    old_value: Any,
    new_value: Any,
    user_id: Optional[str] = None
) -> str:
    """Log configuration change event"""
    manager = get_audit_manager()
    return manager.log_configuration_change(
        request_id=request_id,
        source_ip=source_ip,
        config_key=config_key,
        old_value=old_value,
        new_value=new_value,
        user_id=user_id
    )
