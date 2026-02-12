#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API配置模块

Configuration settings for the tongue diagnosis API service.
Uses pydantic-settings for environment variable loading.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Project information
    PROJECT_NAME: str = "AI舌诊智能诊断系统"
    PROJECT_DESCRIPTION: str = """
    基于PaddlePaddle本地推理 + 文心大模型云端诊断的舌诊AI系统

    ## 功能特点
    - **舌体分割**: 使用BiSeNetV2模型进行精确的舌体区域提取
    - **特征分类**: 使用PP-HGNetV2-B4模型进行多维度舌象特征识别
    - **中医诊断**: 集成文心一言大模型提供专业中医辨证分析
    - **本地规则库**: 支持离线兜底诊断，保障服务可用性

    ## 技术栈
    - 深度学习框架: PaddlePaddle 2.6+
    - API框架: FastAPI
    - 异步任务: Celery + Redis
    - 模型量化: FP16/INT8
    """

    # API Configuration
    API_V1_STR: str = "/api/v1"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ENABLE_API_DOCS: bool = True

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000"
    ]

    # Model Configuration
    SEGMENT_MODEL_PATH: str = "models/deploy/segment_fp16/model_fp16.pdparams"
    CLASSIFY_MODEL_PATH: str = "models/deploy/classify_fp16/model_fp16.pdparams"
    USE_FP16: bool = True
    INFERENCE_DEVICE: str = "cpu"
    INFERENCE_BATCH_SIZE: int = 1

    # Model Input Sizes
    SEGMENT_INPUT_SIZE: int = 512
    CLASSIFY_INPUT_SIZE: int = 224
    MIN_TONGUE_AREA: int = 5000

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    MODELS_DIR: Path = Path("models")
    API_SERVICE_DIR: Path = Path("api_service")
    PROMPTS_DIR: Path = API_SERVICE_DIR / "prompts"

    # Prompt Configuration
    SYSTEM_PROMPT_PATH: Path = PROMPTS_DIR / "system_prompt.txt"
    FEW_SHOT_EXAMPLES_PATH: Path = PROMPTS_DIR / "few_shot_examples.json"
    USER_PROMPT_TEMPLATE_PATH: Path = PROMPTS_DIR / "user_prompt_template.py"

    # Wenxin API Configuration
    BAIDU_API_KEY: Optional[str] = None
    BAIDU_SECRET_KEY: Optional[str] = None
    WENXIN_MODEL: str = "ERNIE-Speed"
    WENXIN_API_BASE: str = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop"
    API_CALL_TIMEOUT: int = 10

    # Rule-based fallback
    ENABLE_RULE_BASED_FALLBACK: bool = True
    RULE_BASED_CONFIG_PATH: str = "api_service/config/rule_based_config.json"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 20

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_WORKER_CONCURRENCY: int = 4
    CELERY_TASK_TIMEOUT: int = 30
    CELERY_TASK_MAX_RETRIES: int = 3

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/api_service.log"
    ENABLE_AUDIT_LOG: bool = True
    AUDIT_LOG_PATH: str = "logs/audit.log"

    # Security and Rate Limiting (task-4-8)
    RATE_LIMIT_PER_SECOND: int = 100
    RATE_LIMIT_BURST: int = 100
    ENABLE_RATE_LIMIT: bool = True
    ENABLE_API_KEY_AUTH: bool = False

    # Circuit Breaker Configuration (task-4-8)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = 2
    CIRCUIT_BREAKER_TIMEOUT: int = 60
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = 3
    ENABLE_CIRCUIT_BREAKER: bool = True

    # Retry Configuration (task-4-8)
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 10.0
    RETRY_ENABLE_JITTER: bool = True
    ENABLE_RETRY: bool = True

    # Data Retention
    DATA_RETENTION_DAYS: int = 180

    # ELK Stack Configuration (task-5-3)
    ELASTICSEARCH_HOSTS: str = "http://localhost:9200"
    ELASTICSEARCH_USER: str = "elastic"
    ELASTICSEARCH_PASSWORD: str = "changeme"
    ELASTICSEARCH_SSL: bool = False
    ELASTICSEARCH_VERIFY_SSL: bool = True
    ENABLE_ELK_LOGGING: bool = False  # Set to true to enable ELK
    ELK_ENVIRONMENT: str = "production"

    # Monitoring
    ENABLE_PROMETHEUS: bool = True
    PROMETHEUS_MULTIPROC_DIR: str = "prometheus_multiproc_dir"
    ENABLE_MLFLOW: bool = False
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    ENABLE_COST_MONITORING: bool = True
    MONTHLY_BUDGET_ALERT: float = 1000.0
    DAILY_MAX_REQUESTS: int = 1000

    # Performance Optimization (task-5-1)
    ENABLE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 86400  # 24 hours
    CACHE_TARGET_HIT_RATE: float = 0.50

    # Development
    DEBUG: bool = False
    MOCK_MODE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def get_model_paths(self) -> dict:
        """Get absolute model paths"""
        base = self.BASE_DIR
        return {
            "segment": str(base / self.SEGMENT_MODEL_PATH),
            "classify": str(base / self.CLASSIFY_MODEL_PATH),
            "system_prompt": str(base / self.SYSTEM_PROMPT_PATH),
            "few_shot": str(base / self.FEW_SHOT_EXAMPLES_PATH),
        }

    def get_redis_url(self, db: Optional[int] = None) -> str:
        """Get Redis connection URL"""
        pwd_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        db_num = db if db is not None else self.REDIS_DB
        return f"redis://{pwd_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{db_num}"


# Global settings instance
settings = Settings()
