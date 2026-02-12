#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志配置模块

Logging configuration for the API service.
Sets up structured logging with file and console handlers.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime


def setup_logging(log_level: str = None, log_file: str = None):
    """Setup logging configuration

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
    """
    from api_service.core.config import settings

    level = log_level or settings.LOG_LEVEL
    log_path = log_file or settings.LOG_FILE_PATH

    # Create logs directory if it doesn't exist
    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create audit log directory
    if settings.ENABLE_AUDIT_LOG:
        audit_dir = Path(settings.AUDIT_LOG_PATH).parent
        audit_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler with UTF-8 encoding for Windows
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console formatter
    console_format = "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s"
    console_date_format = "%Y-%m-%d %H:%M:%S"
    console_formatter = logging.Formatter(
        console_format,
        datefmt=console_date_format
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # File logs all levels

    # File formatter with more details
    file_format = "[%(asctime)s] %(levelname)-8s [%(name)s:%(funcName)s:%(lineno)d] %(message)s"
    file_date_format = "%Y-%m-%d %H:%M:%S"
    file_formatter = logging.Formatter(
        file_format,
        datefmt=file_date_format
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Audit log handler (separate file for audit trail)
    if settings.ENABLE_AUDIT_LOG:
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.propagate = False  # Don't propagate to root logger

        audit_handler = TimedRotatingFileHandler(
            settings.AUDIT_LOG_PATH,
            when='midnight',
            interval=1,
            backupCount=180,  # Keep 180 days
            encoding='utf-8'
        )
        audit_handler.suffix = "%Y-%m-%d"

        # Audit formatter (structured for parsing)
        audit_format = '{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
        audit_formatter = logging.Formatter(
            audit_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        audit_handler.setFormatter(audit_formatter)
        audit_logger.addHandler(audit_logger)


def get_audit_logger() -> logging.Logger:
    """Get the audit logger

    Returns:
        Audit logger instance
    """
    return logging.getLogger("audit")


def log_api_request(
    method: str,
    path: str,
    client_ip: str,
    user_agent: str = None
):
    """Log API request to audit log

    Args:
        method: HTTP method
        path: Request path
        client_ip: Client IP address
        user_agent: User agent string
    """
    audit_logger = get_audit_logger()
    message = f"API_REQUEST method={method} path={path} client_ip={client_ip}"
    if user_agent:
        message += f" user_agent={user_agent}"
    audit_logger.info(message)


def log_api_response(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float
):
    """Log API response to audit log

    Args:
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
    """
    audit_logger = get_audit_logger()
    audit_logger.info(
        f"API_RESPONSE method={method} path={path} "
        f"status={status_code} duration_ms={duration_ms:.2f}"
    )


def log_diagnosis_request(
    image_id: str,
    diagnosis_type: str,
    success: bool,
    model_latency_ms: float = None,
    llm_latency_ms: float = None
):
    """Log diagnosis request for analytics

    Args:
        image_id: Image identifier
        diagnosis_type: Type of diagnosis (segment/classify/diagnosis)
        success: Whether the request was successful
        model_latency_ms: Model inference latency
        llm_latency_ms: LLM API latency (for diagnosis endpoint)
    """
    audit_logger = get_audit_logger()
    message = (
        f"DIAGNOSIS image_id={image_id} type={diagnosis_type} "
        f"success={success}"
    )
    if model_latency_ms is not None:
        message += f" model_latency_ms={model_latency_ms:.2f}"
    if llm_latency_ms is not None:
        message += f" llm_latency_ms={llm_latency_ms:.2f}"

    if success:
        audit_logger.info(message)
    else:
        audit_logger.warning(message)


def log_error(
    error_type: str,
    message: str,
    details: dict = None
):
    """Log error to audit log

    Args:
        error_type: Type of error
        message: Error message
        details: Additional error details
    """
    audit_logger = get_audit_logger()
    details_str = ""
    if details:
        details_str = " " + " ".join(f"{k}={v}" for k, v in details.items())
    audit_logger.error(f"ERROR type={error_type} message={message}{details_str}")


class AuditContext:
    """Context manager for audit logging"""

    def __init__(self, operation: str, **kwargs):
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
        self.audit_logger = get_audit_logger()

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        if exc_type is None:
            self.audit_logger.info(
                f"OPERATION operation={self.operation} "
                f"duration_ms={duration_ms:.2f} "
                + " ".join(f"{k}={v}" for k, v in self.kwargs.items())
            )
        else:
            self.audit_logger.error(
                f"OPERATION_FAILED operation={self.operation} "
                f"duration_ms={duration_ms:.2f} "
                f"error={exc_type.__name__} message={exc_val}"
            )
        return False  # Don't suppress exceptions
