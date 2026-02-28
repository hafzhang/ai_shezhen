#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG向量知识库配置
RAG Vector Knowledge Base Configuration
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List, Optional
import os


class RAGSettings(BaseSettings):
    """RAG向量知识库配置"""

    # 向量数据库配置
    VECTOR_DB_TYPE: str = "chroma"  # chroma, faiss, pinecone
    VECTOR_DB_PATH: str = "api_service/data/vector_db"
    COLLECTION_NAME: str = "tcm_knowledge_base"

    # 嵌入模型配置
    EMBEDDING_MODEL: str = "text-embedding-ada-002"  # OpenAI
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_DEVICE: str = "cpu"  # cpu, cuda

    # 本地嵌入模型 (替代OpenAI)
    LOCAL_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # 文档处理配置
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    MAX_DOCUMENTS: int = 1000

    # RAG配置
    TOP_K_RESULTS: int = 5
    MIN_SIMILARITY_SCORE: float = 0.6
    RAG_CONTEXT_WINDOW: int = 4096

    # LLM配置
    RAG_LLM_PROVIDER: str = "zhipu"  # zhipu, openai, anthropic
    RAG_LLM_MODEL: str = "glm-4-plus"
    RAG_LLM_TEMPERATURE: float = 0.3
    RAG_LLM_MAX_TOKENS: int = 4000

    # 知识库类型
    KNOWLEDGE_TYPES: List[str] = [
        "tcm_theory",      # 中医理论
        "tongue_diagnosis", # 舌诊理论
        "syndrome_analysis", # 证型分析
        "health_guidance",  # 健康指导
        "case_studies",     # 案例研究
        "herbal_medicine"   # 草药知识
    ]

    # PDF报告配置
    PDF_REPORT_PATH: str = "api_service/data/reports"
    PDF_TEMPLATE_PATH: str = "api_service/templates/reports"
    PDF_FONT_PATH: str = "api_service/assets/fonts"

    # 模型配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# 全局配置实例
rag_settings = RAGSettings()


def get_vector_db_path() -> Path:
    """获取向量数据库路径"""
    path = Path(rag_settings.VECTOR_DB_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_report_path() -> Path:
    """获取PDF报告路径"""
    path = Path(rag_settings.PDF_REPORT_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_template_path() -> Path:
    """获取PDF模板路径"""
    path = Path(rag_settings.PDF_TEMPLATE_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_font_path() -> Path:
    """获取字体路径"""
    path = Path(rag_settings.PDF_FONT_PATH)
    path.mkdir(parents=True, exist_ok=True)
    return path