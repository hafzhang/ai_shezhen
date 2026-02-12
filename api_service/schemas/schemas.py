#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API请求和响应模型定义

Pydantic models for API request validation and response serialization.

Author: Ralph Agent
Date: 2026-02-12
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================================================
# 通用响应模型
# ============================================================================

class APIResponse(BaseModel):
    """通用API响应"""
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    error: Optional[str] = Field(None, description="错误类型")
    detail: Optional[str] = Field(None, description="错误详情")


class HealthResponse(BaseModel):
    """健康检查响应"""
    success: bool = Field(..., description="服务是否健康")
    status: str = Field(..., description="服务状态: healthy/degraded")
    models: Dict[str, bool] = Field(..., description="模型加载状态")
    api_version: str = Field(..., description="API版本")


# ============================================================================
# 分割相关模型
# ============================================================================

class SegmentRequest(BaseModel):
    """舌体分割请求"""
    image: str = Field(..., description="图像数据 (base64编码)", min_length=1)
    image_id: Optional[str] = Field(None, description="图像标识符")
    return_overlay: bool = Field(False, description="是否返回分割叠加图像")
    return_mask: bool = Field(True, description="是否返回分割mask")


class SegmentResult(BaseModel):
    """分割结果"""
    mask: Optional[str] = Field(None, description="分割mask (base64编码)")
    overlay: Optional[str] = Field(None, description="分割叠加图像 (base64编码)")
    tongue_area: int = Field(..., description="舌体区域像素数")
    tongue_ratio: float = Field(..., description="舌体区域占比")
    inference_time_ms: float = Field(..., description="推理耗时 (毫秒)")


class SegmentResponse(APIResponse):
    """舌体分割响应"""
    image_id: Optional[str] = Field(None, description="图像标识符")
    result: Optional[SegmentResult] = Field(None, description="分割结果")


# ============================================================================
# 分类相关模型
# ============================================================================

class ClassificationHeadResult(BaseModel):
    """单个分类头的预测结果"""
    prediction: str = Field(..., description="预测类别")
    confidence: float = Field(..., description="置信度", ge=0.0, le=1.0)
    description: str = Field(..., description="类别描述")

    @validator('confidence')
    def round_confidence(cls, v):
        return round(v, 4)


class SpecialFeaturesResult(BaseModel):
    """特殊特征结果"""
    red_dots: Dict[str, Any] = Field(..., description="红点特征")
    cracks: Dict[str, Any] = Field(..., description="裂纹特征")
    teeth_marks: Dict[str, Any] = Field(..., description="齿痕特征")


class ClassificationResult(BaseModel):
    """分类结果"""
    tongue_color: ClassificationHeadResult = Field(..., description="舌色")
    coating_color: ClassificationHeadResult = Field(..., description="苔色")
    tongue_shape: ClassificationHeadResult = Field(..., description="舌形")
    coating_quality: ClassificationHeadResult = Field(..., description="苔质")
    special_features: SpecialFeaturesResult = Field(..., description="特殊特征")
    health_status: ClassificationHeadResult = Field(..., description="健康状态")


class ClassifyRequest(BaseModel):
    """舌象分类请求"""
    image: str = Field(..., description="图像数据 (base64编码)")
    image_id: Optional[str] = Field(None, description="图像标识符")
    crop_to_tongue: bool = Field(
        True,
        description="是否先进行分割裁剪再分类"
    )


class ClassifyResponse(APIResponse):
    """舌象分类响应"""
    image_id: Optional[str] = Field(None, description="图像标识符")
    result: Optional[ClassificationResult] = Field(None, description="分类结果")
    inference_time_ms: float = Field(..., description="推理耗时 (毫秒)")


# ============================================================================
# 诊断相关模型
# ============================================================================

class UserInfo(BaseModel):
    """用户信息"""
    age: Optional[int] = Field(None, description="年龄", ge=0, le=150)
    gender: Optional[str] = Field(None, description="性别")
    symptoms: List[str] = Field(default_factory=list, description="症状列表")
    medical_history: List[str] = Field(default_factory=list, description="既往病史")
    chief_complaint: Optional[str] = Field(None, description="主诉")


class DiagnosisRequest(BaseModel):
    """完整诊断请求"""
    image: str = Field(..., description="图像数据 (base64编码)")
    image_id: Optional[str] = Field(None, description="图像标识符")
    user_info: Optional[UserInfo] = Field(None, description="用户信息")
    enable_llm_diagnosis: bool = Field(
        True,
        description="是否启用LLM诊断 (文心一言)"
    )
    enable_rule_fallback: bool = Field(
        True,
        description="是否启用本地规则库兜底"
    )


class SyndromeInfo(BaseModel):
    """证型信息"""
    name: str = Field(..., description="证型名称")
    confidence: float = Field(..., description="置信度")
    evidence: str = Field(..., description="辨证依据")
    tcm_theory: str = Field(..., description="中医理论")


class SyndromeAnalysis(BaseModel):
    """证型分析"""
    possible_syndromes: List[SyndromeInfo] = Field(..., description="可能证型列表")
    primary_syndrome: Optional[str] = Field(None, description="主要证型")
    secondary_syndromes: List[str] = Field(
        default_factory=list,
        description="次要证型列表"
    )
    syndrome_description: str = Field(..., description="证型描述")


class AnomalyDetection(BaseModel):
    """异常检测结果"""
    detected: bool = Field(..., description="是否检测到异常")
    reason: Optional[str] = Field(None, description="异常原因")
    recommendations: List[str] = Field(
        default_factory=list,
        description="处理建议"
    )


class HealthRecommendations(BaseModel):
    """健康建议"""
    dietary: List[str] = Field(default_factory=list, description="饮食建议")
    lifestyle: List[str] = Field(default_factory=list, description="生活建议")
    tcm_therapy: List[str] = Field(default_factory=list, description="中医理疗建议")
    medical_consultation: str = Field(..., description="就医建议")


class ConfidenceAnalysis(BaseModel):
    """置信度分析"""
    overall_confidence: float = Field(..., description="整体置信度")
    confidence_breakdown: Dict[str, float] = Field(..., description="各阶段置信度")
    uncertainty_factors: List[str] = Field(
        default_factory=list,
        description="不确定性因素"
    )


class Disclaimer(BaseModel):
    """免责声明"""
    ai_assistant_only: bool = Field(..., description="仅AI辅助")
    not_medical_advice: bool = Field(..., description="非医疗建议")
    consult_doctor_reminder: bool = Field(..., description="建议就医提醒")
    emergency_warning: Optional[str] = Field(None, description="紧急情况警告")


class LDiagnosisResult(BaseModel):
    """LLM诊断结果"""
    syndrome_analysis: SyndromeAnalysis = Field(..., description="证型分析")
    anomaly_detection: AnomalyDetection = Field(..., description="异常检测")
    health_recommendations: HealthRecommendations = Field(..., description="健康建议")
    confidence_analysis: ConfidenceAnalysis = Field(..., description="置信度分析")
    disclaimer: Disclaimer = Field(..., description="免责声明")


class DiagnosisResponse(APIResponse):
    """完整诊断响应"""
    image_id: Optional[str] = Field(None, description="图像标识符")
    segmentation: Optional[SegmentResult] = Field(None, description="分割结果")
    classification: Optional[ClassificationResult] = Field(None, description="分类结果")
    diagnosis: Optional[LDiagnosisResult] = Field(None, description="LLM诊断结果")
    used_fallback: bool = Field(False, description="是否使用了兜底方案")
    inference_time_ms: float = Field(..., description="推理耗时 (毫秒)")
    timing_breakdown: Optional[Dict[str, float]] = Field(
        None,
        description="各阶段耗时明细"
    )


# ============================================================================
# 批量处理模型
# ============================================================================

class BatchRequest(BaseModel):
    """批量处理请求"""
    images: List[str] = Field(..., description="图像列表 (base64编码)")
    operation: str = Field(..., description="操作类型: segment/classify")


class BatchResponse(APIResponse):
    """批量处理响应"""
    results: List[Dict[str, Any]] = Field(..., description="处理结果列表")
    total_count: int = Field(..., description="总数")
    success_count: int = Field(..., description="成功数")
    failure_count: int = Field(..., description="失败数")


# ============================================================================
# 错误响应模型
# ============================================================================

class ErrorResponse(APIResponse):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    detail: Optional[str] = Field(None, description="错误详情")
    validation_errors: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="验证错误列表"
    )


# ============================================================================
# 模型验证枚举
# ============================================================================

class ModelType(str, Enum):
    """模型类型"""
    SEGMENTATION = "segmentation"
    CLASSIFICATION = "classification"
    END_TO_END = "end_to_end"


class DiagnosisType(str, Enum):
    """诊断类型"""
    BASIC = "basic"
    FULL = "full"
    EXPERT = "expert"
