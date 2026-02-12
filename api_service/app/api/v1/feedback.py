#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用户反馈收集API

User feedback collection endpoints.
Handles helpful/useful feedback, one-click feedback, and manual appeals.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import uuid
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, Field

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from api_service.core.config import settings
from api_service.core.audit_trail import log_data_access

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/feedback", tags=["Feedback"])

# ============================================================================
# Data Models
# ============================================================================

class FeedbackSubmission(BaseModel):
    """用户反馈提交模型"""
    request_id: str = Field(..., description="关联的诊断请求ID")
    feedback_type: str = Field(..., description="反馈类型: helpful|not_helpful|error|inaccurate")
    diagnosis_id: Optional[str] = Field(None, description="诊断结果ID（如可用）")
    category: str = Field(default="general", description="反馈类别")
    rating: Optional[int] = Field(None, ge=1, le=5, description="用户评分（1-5星）")
    comment: Optional[str] = Field(None, max_length=500, description="用户评论")
    user_agent: Optional[str] = Field(None, description="用户代理（可选）")

class FeedbackResponse(BaseModel):
    """反馈响应模型"""
    feedback_id: str = Field(..., description="反馈ID")
    status: str = Field(..., description="处理状态")
    submitted_at: str = Field(..., description="提交时间")
    message: str = Field(default="Feedback submitted successfully", description="响应消息")

class AppealRequest(BaseModel):
    """人工申诉请求模型"""
    request_id: str = Field(..., description="原始诊断请求ID")
    appeal_reason: str = Field(..., description="申诉原因")
    appeal_type: str = Field(..., description="申诉类型: diagnosis_inaccurate|system_error|other")
    description: str = Field(..., description="详细说明")
    contact_email: Optional[str] = Field(None, description="联系邮箱（可选）")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="附加信息")

class AppealResponse(BaseModel):
    """申诉响应模型"""
    appeal_id: str = Field(..., description="申诉ID")
    status: str = Field(..., description="处理状态")
    ticket_id: str = Field(..., description="工单ID")
    submitted_at: str = Field(..., description="提交时间")
    message: str = Field(default="Appeal submitted successfully", description="响应消息")

# ============================================================================
# Storage (In-memory for demo, use database in production)
# ============================================================================

_feedback_records: Dict[str, Dict[str, Any]] = {}
_appeal_records: Dict[str, Dict[str, Any]] = {}

FEEDBACK_DATA_PATH = Path("data/feedback_records.json")
APPEAL_DATA_PATH = Path("data/appeal_records.json")

def _load_feedback_data():
    """加载反馈记录"""
    if FEEDBACK_DATA_PATH.exists():
        with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_feedback_data():
    """保存反馈记录"""
    FEEDBACK_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(_feedback_records, f, ensure_ascii=False, indent=2)

def _load_appeal_data():
    """加载申诉记录"""
    if APPEAL_DATA_PATH.exists():
        with open(APPEAL_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_appeal_data():
    """保存申诉记录"""
    APPEAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(APPEAL_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(_appeal_records, f, ensure_ascii=False, indent=2)

# Load data on startup
_feedback_records = _load_feedback_data()
_appeal_records = _load_appeal_data()

# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/categories", response_model=Dict[str, Any])
async def get_feedback_categories():
    """
    获取反馈类别列表

    返回可用的反馈类别，用于前端下拉选择。
    """
    categories = {
        "feedback_types": [
            {
                "value": "helpful",
                "label": "诊断结果有帮助",
                "icon": "thumb_up"
            },
            {
                "value": "not_helpful",
                "label": "诊断结果无帮助",
                "icon": "thumb_down"
            },
            {
                "value": "inaccurate",
                "label": "诊断结果不准确",
                "icon": "warning"
            },
            {
                "value": "error",
                "label": "系统错误",
                "icon": "error"
            },
            {
                "value": "feature_request",
                "label": "功能建议",
                "icon": "lightbulb"
            }
        ],
        "appeal_types": [
            {
                "value": "diagnosis_inaccurate",
                "label": "诊断结果不准确",
                "description": "AI诊断结果与实际不符"
            },
            {
                "value": "system_error",
                "label": "系统错误",
                "description": "系统运行异常或崩溃"
            },
            {
                "value": "other",
                "label": "其他原因",
                "description": "其他申诉原因"
            }
        ]
    }
    return categories

@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(
    request: Request,
    submission: FeedbackSubmission
):
    """
    提交用户反馈

    记录用户对诊断结果的反馈，用于改进AI模型。
    """
    client_ip = request.client.host if request.client else None
    user_agent = submission.user_agent or request.headers.get("user-agent")

    # Create feedback record
    feedback_id = f"fb_{uuid.uuid4().hex[:16]}"
    timestamp = datetime.now().isoformat()

    feedback_record = {
        "feedback_id": feedback_id,
        "timestamp": timestamp,
        "request_id": submission.request_id,
        "diagnosis_id": submission.diagnosis_id,
        "feedback_type": submission.feedback_type,
        "category": submission.category,
        "rating": submission.rating,
        "comment": submission.comment,
        "ip_address": client_ip,
        "user_agent": user_agent,
        "status": "pending",
        "processed_at": None,
        "auto_category": None
    }

    # Auto-classify feedback
    if submission.feedback_type in ["helpful", "not_helpful"]:
        feedback_record["auto_category"] = "satisfaction"
    elif submission.feedback_type in ["inaccurate", "error"]:
        feedback_record["auto_category"] = "quality_issue"
    elif submission.feedback_type == "feature_request":
        feedback_record["auto_category"] = "enhancement_request"

    # Store record
    _feedback_records[feedback_id] = feedback_record
    _save_feedback_data()

    # Log data access
    log_data_access(
        request_id=f"feedback_{feedback_id}",
        source_ip=client_ip or "unknown",
        resource_type="feedback_record",
        resource_id=feedback_id,
        access_type="create"
    )

    return FeedbackResponse(
        feedback_id=feedback_id,
        status="pending",
        submitted_at=timestamp,
        message="Feedback submitted successfully"
    )

@router.post("/one-click", response_model=FeedbackResponse)
async def one_click_feedback(
    request: Request,
    request_id: str,
    helpful: bool = True
):
    """
    一键反馈（有帮助/无帮助）

    简化的反馈接口，仅记录正/负面反馈。
    """
    client_ip = request.client.host if request.client else None

    feedback_id = f"oc_{uuid.uuid4().hex[:16]}"
    timestamp = datetime.now().isoformat()

    feedback_record = {
        "feedback_id": feedback_id,
        "timestamp": timestamp,
        "request_id": request_id,
        "feedback_type": "helpful" if helpful else "not_helpful",
        "category": "quick_feedback",
        "rating": 5 if helpful else 1,
        "ip_address": client_ip,
        "status": "pending",
        "processed_at": None,
        "auto_category": "satisfaction"
    }

    _feedback_records[feedback_id] = feedback_record
    _save_feedback_data()

    return FeedbackResponse(
        feedback_id=feedback_id,
        status="pending",
        submitted_at=timestamp,
        message="Feedback recorded successfully"
    )

@router.post("/appeal", response_model=AppealResponse)
async def submit_appeal(
    request: Request,
    appeal: AppealRequest
):
    """
    提交人工申诉

    用户对诊断结果有异议时，可以提交人工申诉。
    """
    client_ip = request.client.host if request.client else None

    appeal_id = f"appeal_{uuid.uuid4().hex[:16]}"
    ticket_id = f"TKT-{int(time.time())}"
    timestamp = datetime.now().isoformat()

    appeal_record = {
        "appeal_id": appeal_id,
        "ticket_id": ticket_id,
        "timestamp": timestamp,
        "request_id": appeal.request_id,
        "appeal_type": appeal.appeal_type,
        "appeal_reason": appeal.appeal_reason,
        "description": appeal.description,
        "contact_email": appeal.contact_email,
        "additional_info": appeal.additional_info,
        "ip_address": client_ip,
        "status": "pending",
        "assigned_to": None,
        "resolved_at": None,
        "resolution": None
    }

    _appeal_records[appeal_id] = appeal_record
    _save_appeal_data()

    # Log data access
    log_data_access(
        request_id=f"appeal_{appeal_id}",
        source_ip=client_ip or "unknown",
        resource_type="appeal_record",
        resource_id=appeal_id,
        access_type="create"
    )

    return AppealResponse(
        appeal_id=appeal_id,
        status="pending",
        ticket_id=ticket_id,
        submitted_at=timestamp,
        message="Appeal submitted successfully"
    )

@router.get("/appeal/{appeal_id}/status", response_model=Dict[str, Any])
async def get_appeal_status(appeal_id: str):
    """
    查询申诉状态

    允许用户查询申诉处理进度。
    """
    if appeal_id not in _appeal_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appeal not found"
        )

    appeal = _appeal_records[appeal_id]

    return {
        "success": True,
        "appeal_id": appeal_id,
        "ticket_id": appeal["ticket_id"],
        "status": appeal["status"],
        "submitted_at": appeal["timestamp"],
        "assigned_to": appeal.get("assigned_to"),
        "resolved_at": appeal.get("resolved_at"),
        "resolution": appeal.get("resolution")
    }

@router.get("/stats/summary", response_model=Dict[str, Any])
async def get_feedback_stats(
    days: int = 30,
    request: Request = None
):
    """
    获取反馈统计

    返回指定天数内的反馈统计摘要（用于仪表板）。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    cutoff_time = datetime.now() - timedelta(days=days)

    # Calculate stats
    total_feedback = 0
    helpful_count = 0
    not_helpful_count = 0
    error_count = 0
    pending_appeals = 0

    for record in _feedback_records.values():
        try:
            record_time = datetime.fromisoformat(record["timestamp"])
            if record_time >= cutoff_time:
                total_feedback += 1
                if record.get("feedback_type") == "helpful":
                    helpful_count += 1
                elif record.get("feedback_type") == "not_helpful":
                    not_helpful_count += 1
                elif record.get("feedback_type") == "error":
                    error_count += 1
        except:
            pass

    pending_appeals = sum(
        1 for a in _appeal_records.values()
        if a.get("status") == "pending"
    )

    # Log data access
    log_data_access(
        request_id=f"stats_{int(time.time())}",
        source_ip=client_ip,
        resource_type="feedback_stats",
        resource_id="summary",
        access_type="read"
    )

    return {
        "success": True,
        "period_days": days,
        "total_feedback": total_feedback,
        "helpful_count": helpful_count,
        "not_helpful_count": not_helpful_count,
        "error_count": error_count,
        "helpful_rate": f"{helpful_count / total_feedback:.2%}" if total_feedback > 0 else "N/A",
        "pending_appeals": pending_appeals,
        "average_rating": "N/A"  # 需要从rating计算
    }

# ============================================================================
# Background Processing (for automation)
# ============================================================================

class FeedbackProcessor:
    """反馈处理器（自动分类和响应）"""

    @staticmethod
    def auto_categorize_feedback():
        """自动分类反馈"""
        # Analyze feedback patterns
        feedback_by_type = {}
        error_patterns = {}

        for record in _feedback_records.values():
            if record.get("status") == "pending":
                feedback_type = record.get("feedback_type", "unknown")
                feedback_by_type[feedback_type] = feedback_by_type.get(feedback_type, 0) + 1

                # Analyze error patterns
                if record.get("comment"):
                    comment = record["comment"].lower()
                    if "error" in comment or "错误" in comment:
                        error_patterns[comment] = error_patterns.get(comment, 0) + 1

        return {
            "feedback_by_type": feedback_by_type,
            "error_patterns": error_patterns,
            "recommendations": FeedbackProcessor._generate_recommendations(feedback_by_type, error_patterns)
        }

    @staticmethod
    def _generate_recommendations(feedback_by_type, error_patterns):
        """生成改进建议"""
        recommendations = []

        # Analyze satisfaction rate
        helpful = feedback_by_type.get("helpful", 0)
        not_helpful = feedback_by_type.get("not_helpful", 0)
        total = helpful + not_helpful

        if total > 0:
            satisfaction_rate = helpful / total
            if satisfaction_rate < 0.6:
                recommendations.append({
                    "priority": "high",
                    "type": "accuracy_improvement",
                    "message": "用户满意度低于60%，建议优化AI模型准确性"
                })

        # Error pattern analysis
        for error_msg, count in sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count >= 3:
                recommendations.append({
                    "priority": "medium",
                    "type": "bug_fix",
                    "message": f"高频错误: '{error_msg}' (出现{count}次)"
                })

        return recommendations

@router.post("/admin/process", response_model=Dict[str, Any])
async def process_feedback():
    """
    处理反馈（管理员功能）

    自动分析和生成反馈处理建议。
    """
    processor = FeedbackProcessor()
    analysis = processor.auto_categorize_feedback()

    return {
        "success": True,
        "analysis": analysis,
        "processed_at": datetime.now().isoformat()
    }
