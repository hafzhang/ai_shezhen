#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API v2 Pydantic Models
AI舌诊智能诊断系统 - API v2 Models
Phase 2: Database & Auth - US-117

This module defines Pydantic models for API v2 endpoints:
- Authentication models (register, login, token, refresh)
- User models (response, update)
- Response wrapper models

Usage:
    from api_service.app.api.v2.models import (
        UserRegister,
        UserLogin,
        TokenResponse,
        RefreshRequest,
    )

    # Validate user registration input
    user_data = UserRegister(
        phone="13800138000",
        password="securepass123",
        nickname="张三"
    )
"""

import re
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Authentication Request Models
# ============================================================================

class UserRegister(BaseModel):
    """
    User registration request model.

    Validates user registration input including phone number validation,
    password requirements, and optional email.

    Attributes:
        phone: Mobile phone number (Chinese format: 11 digits, starts with 1)
        password: User password (min 8 characters, letters + numbers)
        nickname: User display name (optional, defaults to phone number)
        email: User email address (optional)

    Example:
        >>> user = UserRegister(
        ...     phone="13800138000",
        ...     password="abc12345",
        ...     nickname="张三"
        ... )
    """

    phone: str = Field(
        ...,
        description="手机号（11位数字，以1开头）",
        min_length=11,
        max_length=11,
        pattern=r'^1[3-9]\d{9}$'
    )
    password: str = Field(
        ...,
        description="密码（至少8位，包含字母和数字）",
        min_length=8
    )
    nickname: Optional[str] = Field(
        None,
        description="昵称",
        max_length=50
    )
    email: Optional[str] = Field(
        None,
        description="邮箱地址"
    )

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        Validate Chinese mobile phone number format.

        Chinese mobile numbers:
        - Start with 1
        - Second digit is 3-9
        - Total 11 digits

        Args:
            v: Phone number string

        Returns:
            Validated phone number

        Raises:
            ValueError: If phone number format is invalid
        """
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确，请输入11位有效的手机号码')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Validate password strength requirements.

        Password must:
        - Be at least 8 characters long
        - Contain both letters and numbers

        Args:
            v: Password string

        Returns:
            Validated password

        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(v) < 8:
            raise ValueError('密码长度至少为8位')
        if not re.search(r'[A-Za-z]', v):
            raise ValueError('密码必须包含字母')
        if not re.search(r'\d', v):
            raise ValueError('密码必须包含数字')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate email format if provided.

        Args:
            v: Email string or None

        Returns:
            Validated email or None

        Raises:
            ValueError: If email format is invalid
        """
        if v is not None and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('邮箱格式不正确')
        return v


class UserLogin(BaseModel):
    """
    User login request model.

    Validates user login credentials.

    Attributes:
        phone: Mobile phone number (11 digits)
        password: User password

    Example:
        >>> login = UserLogin(phone="13800138000", password="abc12345")
    """

    phone: str = Field(
        ...,
        description="手机号",
        min_length=11,
        max_length=11
    )
    password: str = Field(
        ...,
        description="密码",
        min_length=1
    )


class RefreshRequest(BaseModel):
    """
    Token refresh request model.

    Used to obtain a new access token using a valid refresh token.

    Attributes:
        refresh_token: JWT refresh token string

    Example:
        >>> refresh = RefreshRequest(refresh_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    """

    refresh_token: str = Field(
        ...,
        description="刷新令牌",
        min_length=1
    )


class WeChatLoginRequest(BaseModel):
    """
    WeChat mini-program login request model.

    Used for WeChat mini-program authentication.
    The frontend calls wx.login() to get a code, then sends it to backend.
    Backend exchanges code for openid and session_key via WeChat API.

    Attributes:
        code: WeChat login code from wx.login()
        nickname: User nickname (optional, from wx.getUserInfo())
        avatar_url: User avatar URL (optional, from wx.getUserInfo())

    Example:
        >>> wechat_login = WeChatLoginRequest(code="0x1234567890")
    """

    code: str = Field(
        ...,
        description="微信登录凭证（wx.login()获取）",
        min_length=1
    )
    nickname: Optional[str] = Field(
        None,
        description="用户昵称",
        max_length=50
    )
    avatar_url: Optional[str] = Field(
        None,
        description="用户头像URL"
    )


class DouyinLoginRequest(BaseModel):
    """
    Douyin mini-program login request model.

    Used for Douyin mini-program authentication.
    The frontend calls tt.login() to get a code, then sends it to backend.
    Backend exchanges code for openid via Douyin API.

    Attributes:
        code: Douyin login code from tt.login()
        nickname: User nickname (optional)
        avatar_url: User avatar URL (optional)

    Example:
        >>> douyin_login = DouyinLoginRequest(code="1234567890")
    """

    code: str = Field(
        ...,
        description="抖音登录凭证（tt.login()获取）",
        min_length=1
    )
    nickname: Optional[str] = Field(
        None,
        description="用户昵称",
        max_length=50
    )
    avatar_url: Optional[str] = Field(
        None,
        description="用户头像URL"
    )


# ============================================================================
# Authentication Response Models
# ============================================================================

class UserInfo(BaseModel):
    """
    User information response model.

    Contains basic user profile information returned after login/registration.

    Attributes:
        id: User UUID
        phone: User phone number (optional for mini-program users)
        email: User email (optional)
        nickname: User display name
        avatar_url: Profile image URL (optional)
        openid: OpenID for mini-program (optional)
        openid_type: OpenID provider type ("wechat" or "douyin", optional)

    Example:
        >>> user_info = UserInfo(
        ...     id="123e4567-e89b-12d3-a456-426614174000",
        ...     phone="13800138000",
        ...     nickname="张三"
        ... )
    """

    id: UUID = Field(..., description="用户ID")
    phone: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, description="昵称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    openid: Optional[str] = Field(None, description="OpenID（小程序用户）")
    openid_type: Optional[str] = Field(None, description="OpenID类型（wechat/douyin）")

    model_config = {
        "from_attributes": True  # Enable ORM mode for SQLAlchemy models
    }


class TokenResponse(BaseModel):
    """
    Token response model.

    Returned after successful login or registration.
    Contains access token, refresh token, and user info.

    Attributes:
        access_token: JWT access token (30 minutes validity)
        refresh_token: JWT refresh token (7 days validity)
        token_type: Token type (always "bearer")
        expires_in: Access token expiration time in seconds
        user: User information

    Example:
        >>> tokens = TokenResponse(
        ...     access_token="eyJhbGci...",
        ...     refresh_token="eyJhbGci...",
        ...     token_type="bearer",
        ...     expires_in=1800,
        ...     user=UserInfo(id=..., phone="13800138000", ...)
        ... )
    """

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(default=1800, description="访问令牌过期时间（秒）")
    user: UserInfo = Field(..., description="用户信息")


# ============================================================================
# Unified Response Models
# ============================================================================

class APIResponse(BaseModel):
    """
    Unified API response model for v2 endpoints.

    Provides consistent response structure across all v2 APIs.

    Attributes:
        success: Whether the request was successful
        message: Optional success message
        error: Optional error type/code
        detail: Optional error details

    Example:
        >>> response = APIResponse(success=True, message="操作成功")
    """

    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    error: Optional[str] = Field(None, description="错误类型")
    detail: Optional[str] = Field(None, description="错误详情")


class AuthResponse(APIResponse):
    """
    Authentication response model with optional data field.

    Extends APIResponse to include authentication-related data.

    Attributes:
        data: Optional data payload (e.g., TokenResponse for login/register)

    Example:
        >>> response = AuthResponse(
        ...     success=True,
        ...     message="登录成功",
        ...     data=TokenResponse(...)
        ... )
    """

    data: Optional[dict] = Field(None, description="响应数据")


# ============================================================================
# Response Wrapper Models
# ============================================================================

class RegisterResponse(APIResponse):
    """
    User registration response model.

    Returns tokens and user info after successful registration.

    Attributes:
        access_token: JWT access token
        refresh_token: JWT refresh token
        user: User information

    Example:
        >>> response = RegisterResponse(
        ...     success=True,
        ...     message="注册成功",
        ...     access_token="eyJhbGci...",
        ...     refresh_token="eyJhbGci...",
        ...     user=UserInfo(...)
        ... )
    """

    access_token: Optional[str] = Field(None, description="访问令牌")
    refresh_token: Optional[str] = Field(None, description="刷新令牌")
    user: Optional[UserInfo] = Field(None, description="用户信息")


class LoginResponse(APIResponse):
    """
    User login response model.

    Returns tokens and user info after successful login.

    Attributes:
        access_token: JWT access token
        refresh_token: JWT refresh token
        user: User information

    Example:
        >>> response = LoginResponse(
        ...     success=True,
        ...     message="登录成功",
        ...     access_token="eyJhbGci...",
        ...     refresh_token="eyJhbGci...",
        ...     user=UserInfo(...)
        ... )
    """

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    user: UserInfo = Field(..., description="用户信息")


class RefreshResponse(APIResponse):
    """
    Token refresh response model.

    Returns new access token after successful refresh.

    Attributes:
        access_token: New JWT access token
        expires_in: Access token expiration time in seconds

    Example:
        >>> response = RefreshResponse(
        ...     success=True,
        ...     message="令牌刷新成功",
        ...     access_token="eyJhbGci...",
        ...     expires_in=1800
        ... )
    """

    access_token: str = Field(..., description="新的访问令牌")
    expires_in: int = Field(default=1800, description="访问令牌过期时间（秒）")


class LogoutResponse(APIResponse):
    """
    User logout response model.

    Returns success message after logout.

    Attributes:
        message: Logout success message

    Example:
        >>> response = LogoutResponse(
        ...     success=True,
        ...     message="退出登录成功"
        ... )
    """

    message: str = Field(default="退出登录成功", description="响应消息")


# ============================================================================
# Diagnosis Request/Response Models (US-121)
# ============================================================================

class UserInfoRequest(BaseModel):
    """
    User information for diagnosis request.

    Captures basic user demographics and chief complaint.

    Attributes:
        age: User age (optional)
        gender: User gender (optional)
        chief_complaint: Primary symptom or complaint (optional)

    Example:
        >>> user_info = UserInfoRequest(
        ...     age=35,
        ...     gender="male",
        ...     chief_complaint="最近感觉疲劳"
        ... )
    """

    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")
    gender: Optional[str] = Field(None, description="性别")
    chief_complaint: Optional[str] = Field(None, description="主诉症状")


class DiagnosisRequest(BaseModel):
    """
    Diagnosis request model.

    Contains tongue image and optional user information for diagnosis.

    Attributes:
        image: Base64 encoded tongue image (required)
        user_info: Optional user demographic information
        enable_llm_diagnosis: Whether to enable LLM diagnosis (default: True)
        enable_rule_fallback: Whether to enable rule-based fallback (default: True)

    Example:
        >>> request = DiagnosisRequest(
        ...     image="data:image/png;base64,iVBORw0KG...",
        ...     user_info=UserInfoRequest(age=35, gender="male")
        ... )
    """

    image: str = Field(..., description="Base64编码的舌象图像")
    user_info: Optional[UserInfoRequest] = Field(None, description="用户信息")
    enable_llm_diagnosis: bool = Field(default=True, description="是否启用LLM诊断")
    enable_rule_fallback: bool = Field(default=True, description="是否启用规则库兜底")


class SegmentationResult(BaseModel):
    """
    Segmentation result model.

    Contains tongue segmentation metrics.

    Attributes:
        tongue_area: Tongue area in pixels
        tongue_ratio: Tongue area ratio (0-1)
    """

    tongue_area: int = Field(..., description="舌体区域像素数")
    tongue_ratio: float = Field(..., description="舌体区域占比")


class ClassificationFeature(BaseModel):
    """
    Individual classification feature model.

    Contains prediction, confidence, and description for a single feature.

    Attributes:
        prediction: Predicted class name
        confidence: Confidence score (0-1)
        description: Feature description
    """

    prediction: str = Field(..., description="预测结果")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    description: Optional[str] = Field(None, description="特征描述")


class SpecialFeatures(BaseModel):
    """
    Special features classification model.

    Contains binary feature detection results.

    Attributes:
        red_dots: Red dot detection result
        cracks: Crack detection result
        teeth_marks: Teeth mark detection result
    """

    red_dots: dict = Field(default_factory=dict, description="红点特征")
    cracks: dict = Field(default_factory=dict, description="裂纹特征")
    teeth_marks: dict = Field(default_factory=dict, description="齿痕特征")


class ClassificationResult(BaseModel):
    """
    Complete classification result model.

    Contains all 6-dimension tongue features.

    Attributes:
        tongue_color: Tongue color classification
        coating_color: Coating color classification
        tongue_shape: Tongue shape classification
        coating_quality: Coating quality classification
        special_features: Special features detection
        health_status: Overall health status classification
    """

    tongue_color: ClassificationFeature = Field(..., description="舌色分类")
    coating_color: ClassificationFeature = Field(..., description="苔色分类")
    tongue_shape: ClassificationFeature = Field(..., description="舌形分类")
    coating_quality: ClassificationFeature = Field(..., description="苔质分类")
    special_features: SpecialFeatures = Field(..., description="特殊特征")
    health_status: ClassificationFeature = Field(..., description="健康状态")


class DiagnosisResult(BaseModel):
    """
    LLM diagnosis result model.

    Contains TCM syndrome analysis and recommendations.

    Attributes:
        primary_syndrome: Primary TCM syndrome
        confidence: Syndrome confidence score
        syndrome_analysis: Detailed syndrome analysis
        tcm_theory: TCM theoretical basis (optional)
        health_recommendations: Health recommendations
        risk_alert: Risk warning (optional)
    """

    primary_syndrome: str = Field(..., description="主要证型")
    confidence: float = Field(..., ge=0, le=1, description="置信度")
    syndrome_analysis: str = Field(..., description="证型分析")
    tcm_theory: Optional[str] = Field(None, description="中医理论基础")
    health_recommendations: dict = Field(..., description="健康建议")
    risk_alert: Optional[str] = Field(None, description="风险提示")


class DiagnosisResponse(APIResponse):
    """
    Diagnosis response model.

    Returns complete diagnosis results with database record ID.

    Attributes:
        diagnosis_id: Database record ID (for querying later)
        user_id: User ID (None for anonymous diagnosis)
        segmentation: Segmentation results
        classification: 6-dimension classification results
        diagnosis: TCM syndrome diagnosis
        inference_time_ms: Total inference time in milliseconds
        created_at: Diagnosis creation timestamp

    Example:
        >>> response = DiagnosisResponse(
        ...     success=True,
        ...     diagnosis_id="123e4567-e89b-12d3-a456-426614174000",
        ...     user_id="user-uuid",
        ...     segmentation=SegmentationResult(...),
        ...     classification=ClassificationResult(...),
        ...     diagnosis=DiagnosisResult(...),
        ...     inference_time_ms=1500.0
        ... )
    """

    diagnosis_id: str = Field(..., description="诊断记录ID")
    user_id: Optional[str] = Field(None, description="用户ID（匿名诊断为空）")
    segmentation: SegmentationResult = Field(..., description="分割结果")
    classification: ClassificationResult = Field(..., description="分类结果")
    diagnosis: DiagnosisResult = Field(..., description="诊断结果")
    inference_time_ms: float = Field(..., description="总推理时间（毫秒）")
    created_at: Optional[str] = Field(None, description="诊断时间（ISO 8601）")


# ============================================================================
# Feedback Models (US-127)
# ============================================================================

class FeedbackRequest(BaseModel):
    """
    Feedback submission request model.

    Allows users to provide feedback on diagnosis quality.

    Attributes:
        feedback: Feedback value (1 for helpful, -1 for not helpful)
        comment: Optional comment explaining the feedback

    Example:
        >>> feedback = FeedbackRequest(feedback=1, comment="诊断准确")
    """

    feedback: int = Field(..., ge=-1, le=1, description="反馈值（1为有帮助，-1为无帮助）")
    comment: Optional[str] = Field(None, max_length=500, description="反馈评论")


class FeedbackResponse(APIResponse):
    """
    Feedback submission response model.

    Returns success message after feedback submission.

    Example:
        >>> response = FeedbackResponse(success=True, message="反馈已提交")
    """

    message: str = Field(default="反馈已提交", description="响应消息")


# ============================================================================
# Diagnosis History Models (US-132)
# ============================================================================

class DiagnosisHistoryItem(BaseModel):
    """
    Single diagnosis history item.

    Contains complete diagnosis information for history display.

    Attributes:
        id: Diagnosis record ID
        user_id: User ID (None for anonymous diagnosis)
        tongue_image_id: Associated tongue image ID
        user_info: User demographic information
        features: Classification features
        results: Diagnosis results
        feedback: User feedback (optional)
        feedback_comment: Feedback comment (optional)
        model_version: Model version used
        inference_time_ms: Inference time
        created_at: Diagnosis creation timestamp
    """

    id: str = Field(..., description="诊断记录ID")
    user_id: Optional[str] = Field(None, description="用户ID")
    tongue_image_id: Optional[str] = Field(None, description="舌象图像ID")
    user_info: Optional[Dict[str, Any]] = Field(None, description="用户信息")
    features: Dict[str, Any] = Field(..., description="分类特征")
    results: Dict[str, Any] = Field(..., description="诊断结果")
    feedback: Optional[int] = Field(None, description="用户反馈（1/-1）")
    feedback_comment: Optional[str] = Field(None, description="反馈评论")
    model_version: Optional[str] = Field(None, description="模型版本")
    inference_time_ms: Optional[int] = Field(None, description="推理时间（毫秒）")
    created_at: str = Field(..., description="诊断时间")


class DiagnosisHistoryResponse(APIResponse):
    """
    Single diagnosis history response.

    Returns detailed information for one diagnosis record.

    Attributes:
        diagnosis: Diagnosis history item
    """

    diagnosis: DiagnosisHistoryItem


class DiagnosisListResponse(APIResponse):
    """
    Paginated diagnosis list response.

    Returns list of diagnosis records with pagination info.

    Attributes:
        total: Total number of records
        page: Current page number
        page_size: Records per page
        items: List of diagnosis items
    """

    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页记录数")
    items: List[DiagnosisHistoryItem] = Field(..., description="诊断记录列表")


class SyndromeStatistics(BaseModel):
    """
    Syndrome statistics item.

    Attributes:
        syndrome: Syndrome name
        count: Occurrence count
        percentage: Percentage of total
    """

    syndrome: str = Field(..., description="证型名称")
    count: int = Field(..., description="出现次数")
    percentage: float = Field(..., description="占比")


class FeatureStatistics(BaseModel):
    """
    Feature statistics item.

    Attributes:
        feature_name: Feature name (e.g., "tongue_color")
        feature_value: Feature value (e.g., "淡红舌")
        count: Occurrence count
        percentage: Percentage of total
    """

    feature_name: str = Field(..., description="特征名称")
    feature_value: str = Field(..., description="特征值")
    count: int = Field(..., description="出现次数")
    percentage: float = Field(..., description="占比")


class DiagnosisStatisticsResponse(APIResponse):
    """
    Diagnosis statistics response.

    Returns aggregated statistics about user's diagnosis history.

    Attributes:
        total_diagnoses: Total number of diagnoses
        syndromes: Most common syndromes
        tongue_features: Most common tongue features
        time_distribution: Diagnosis count by date
        avg_inference_time_ms: Average inference time
    """

    total_diagnoses: int = Field(..., description="总诊断次数")
    syndromes: List[SyndromeStatistics] = Field(..., description="常见证型统计")
    tongue_features: List[FeatureStatistics] = Field(..., description="常见舌象特征统计")
    time_distribution: List[Dict[str, Any]] = Field(..., description="时间分布")
    avg_inference_time_ms: Optional[float] = Field(None, description="平均推理时间（毫秒）")


class TrendDataPoint(BaseModel):
    """
    Single trend data point.

    Attributes:
        date: Date string
        value: Value for this date
        label: Optional label
    """

    date: str = Field(..., description="日期")
    value: float = Field(..., description="数值")
    label: Optional[str] = Field(None, description="标签")


class DiagnosisTrendsResponse(APIResponse):
    """
    Diagnosis trends response.

    Returns trend analysis data for visualization.

    Attributes:
        syndrome_trends: Syndrome changes over time
        feature_trends: Feature changes over time
        health_score_trend: Health score trend (optional)
        period: Analysis period (days)
    """

    syndrome_trends: List[TrendDataPoint] = Field(..., description="证型变化趋势")
    feature_trends: Dict[str, List[TrendDataPoint]] = Field(..., description="特征变化趋势")
    health_score_trend: Optional[List[TrendDataPoint]] = Field(None, description="健康评分趋势")
    period: int = Field(..., description="分析周期（天）")


__all__ = [
    # Request models
    "UserRegister",
    "UserLogin",
    "RefreshRequest",
    "UserInfoRequest",
    "DiagnosisRequest",
    "FeedbackRequest",
    # Response models
    "UserInfo",
    "TokenResponse",
    "APIResponse",
    "AuthResponse",
    "RegisterResponse",
    "LoginResponse",
    "RefreshResponse",
    "LogoutResponse",
    "FeedbackResponse",
    # Diagnosis models
    "SegmentationResult",
    "ClassificationFeature",
    "SpecialFeatures",
    "ClassificationResult",
    "DiagnosisResult",
    "DiagnosisResponse",
    # Diagnosis history models (US-132)
    "DiagnosisHistoryItem",
    "DiagnosisHistoryResponse",
    "DiagnosisListResponse",
    "SyndromeStatistics",
    "FeatureStatistics",
    "DiagnosisStatisticsResponse",
    "TrendDataPoint",
    "DiagnosisTrendsResponse",
]
