#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
成本监控与优化API

Cost monitoring and optimization endpoints.
Tracks API costs, generates budget alerts, and provides optimization recommendations.

Author: Ralph Agent
Date: 2026-02-12
"""

import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
from collections import defaultdict

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, Field

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from api_service.core.config import settings
from api_service.core.audit_trail import (
    log_configuration_change,
    get_audit_manager
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/cost", tags=["Cost Monitoring"])

# ============================================================================
# Data Models
# ============================================================================

class APICostRecord(BaseModel):
    """API调用成本记录"""
    request_id: str = Field(..., description="请求ID")
    timestamp: str = Field(..., description="时间戳")
    api_name: str = Field(..., description="API名称（wenxin/other）")
    endpoint: str = Field(..., description="端点路径")
    model: str = Field(..., description="使用的模型")
    request_type: str = Field(..., description="请求类型（segment/classify/diagnosis）")
    token_count: int = Field(..., description="消耗token数")
    cost_estimate: float = Field(..., description="预估成本（元）")
    actual_cost: Optional[float] = Field(None, description="实际成本（从账单获取）")

class DailyCostSummary(BaseModel):
    """每日成本汇总"""
    date: str = Field(..., description="日期（YYYY-MM-DD）")
    total_requests: int = Field(..., description="总请求数")
    total_tokens: int = Field(..., description="总token消耗")
    total_cost: float = Field(..., description="总成本（元）")
    cost_breakdown: Dict[str, float] = Field(default_factory=dict, description="成本明细")

class BudgetAlert(BaseModel):
    """预算告警"""
    alert_id: str = Field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:16]}")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    alert_type: str = Field(..., description="告警类型（info/warning/critical）")
    current_monthly_budget: float = Field(..., description="当月预算")
    current_spend: float = Field(..., description="当前已花费")
    spend_percentage: float = Field(..., description="花费百分比")
    message: str = Field(..., description="告警消息")
    resolved: bool = Field(default=False, description="是否已解决")

class CostOptimizationSuggestion(BaseModel):
    """成本优化建议"""
    suggestion_id: str = Field(default_factory=lambda: f"suggest_{uuid.uuid4().hex[:16]}")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    category: str = Field(..., description="优化类别（prompt/caching/architecture）")
    priority: str = Field(..., description="优先级（high/medium/low）")
    title: str = Field(..., description="建议标题")
    description: str = Field(..., description="详细描述")
    estimated_savings: float = Field(..., description="预估节省（元/月）")
    implementation_effort: str = Field(..., description="实施难度（小时）")

# ============================================================================
# Storage (In-memory for demo, use database in production)
# ============================================================================

_cost_records: Dict[str, APICostRecord] = {}
_daily_summaries: Dict[str, DailyCostSummary] = {}
_alerts: Dict[str, BudgetAlert] = {}
_suggestions: Dict[str, CostOptimizationSuggestion] = {}

COST_DATA_PATH = Path("data/cost_records.json")
DAILY_SUMMARY_PATH = Path("data/daily_summaries.json")
ALERTS_PATH = Path("data/budget_alerts.json")
SUGGESTIONS_PATH = Path("data/cost_suggestions.json")

def _load_data():
    """加载成本数据"""
    global _cost_records, _daily_summaries, _alerts, _suggestions

    if COST_DATA_PATH.exists():
        with open(COST_DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for record_data in data:
                record = APICostRecord(**record_data)
                _cost_records[record.request_id] = record

    if DAILY_SUMMARY_PATH.exists():
        with open(DAILY_SUMMARY_PATH, 'r', encoding='utf-8') as f:
            _daily_summaries = json.load(f)

    if ALERTS_PATH.exists():
        with open(ALERTS_PATH, 'r', encoding='utf-8') as f:
            _alerts = json.load(f)

    if SUGGESTIONS_PATH.exists():
        with open(SUGGESTIONS_PATH, 'r', encoding='utf-8') as f:
            _suggestions = json.load(f)

def _save_data():
    """保存成本数据"""
    # Cost records
    COST_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_DATA_PATH, 'w', encoding='utf-8') as f:
        data = [r.model_dump() for r in _cost_records.values()]
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Daily summaries
    DAILY_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_SUMMARY_PATH, 'w', encoding='utf-8') as f:
        json.dump(_daily_summaries, f, ensure_ascii=False, indent=2)

    # Alerts
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(_alerts, f, ensure_ascii=False, indent=2)

    # Suggestions
    SUGGESTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUGGESTIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(_suggestions, f, ensure_ascii=False, indent=2)

# Load data on startup
_load_data()

# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/stats", response_model=Dict[str, Any])
async def get_cost_stats(
    days: int = 30,
    request: Request = None
):
    """
    获取成本统计

    返回指定天数内的成本统计摘要。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    total_requests = 0
    total_tokens = 0
    total_cost = 0.0

    breakdown = defaultdict(float)

    for record in _cost_records.values():
        record_date = record.timestamp[:10]
        if record_date >= cutoff_date:
            total_requests += 1
            total_tokens += record.token_count
            cost = record.actual_cost or record.cost_estimate
            total_cost += cost
            breakdown[record.model] += cost

    return {
        "success": True,
        "period_days": days,
        "cutoff_date": cutoff_date,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 2),
        "cost_breakdown": dict(breakdown),
        "average_cost_per_request": round(total_cost / total_requests, 4) if total_requests > 0 else 0
    }

@router.get("/budget", response_model=Dict[str, Any])
async def get_budget_status(
    request: Request
):
    """
    获取预算状态和告警

    返回当月预算使用情况和告警历史。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    current_month = datetime.now().strftime("%Y-%m")
    monthly_budget = settings.MONTHLY_BUDGET_ALERT

    # Calculate current month spend
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    current_spend = 0.0

    for record in _cost_records.values():
        if record.timestamp.startswith(current_month):
            cost = record.actual_cost or record.cost_estimate
            current_spend += cost

    spend_percentage = (current_spend / monthly_budget * 100) if monthly_budget > 0 else 0

    # Get active alerts
    active_alerts = [a for a in _alerts.values() if not a.get("resolved", True)]

    # Check if need alert
    needs_alert = (
        settings.ENABLE_COST_MONITORING and
        monthly_budget > 0 and
        spend_percentage >= 80
    )

    if needs_alert and not active_alerts:
        alert = BudgetAlert(
            current_monthly_budget=monthly_budget,
            current_spend=round(current_spend, 2),
            spend_percentage=round(spend_percentage, 2),
            message=f"月度预算已使用{spend_percentage:.1f}%，剩余{100-spend_percentage:.1f}%"
        )
        _alerts[alert.alert_id] = alert
        _save_data()

        log_configuration_change(
            request_id=f"budget_alert_{alert.alert_id}",
            source_ip=client_ip,
            config_key="monthly_budget",
            old_value=str(monthly_budget),
            new_value="alert_triggered"
        )

    return {
        "success": True,
        "current_month": current_month,
        "monthly_budget": monthly_budget,
        "current_spend": round(current_spend, 2),
        "spend_percentage": round(spend_percentage, 2) if monthly_budget > 0 else 0,
        "remaining_budget": round(monthly_budget - current_spend, 2) if monthly_budget > 0 else 0,
        "active_alerts": len(active_alerts),
        "needs_alert": needs_alert
    }

@router.post("/alerts/{alert_id}/resolve", response_model=Dict[str, Any])
async def resolve_alert(
    alert_id: str,
    request: Request
):
    """
    解决告警

    标记告警为已解决。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    if alert_id not in _alerts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    alert = _alerts[alert_id]
    alert.resolved = True
    alert.timestamp = datetime.now().isoformat()

    _save_data()

    log_configuration_change(
        request_id=f"resolve_alert_{alert_id}",
        source_ip=client_ip,
        config_key="alert_status",
        old_value="unresolved",
        new_value="resolved"
    )

    return {
        "success": True,
        "alert_id": alert_id,
        "status": "resolved",
        "resolved_at": alert.timestamp
    }

@router.get("/suggestions", response_model=List[Dict[str, Any]])
async def get_optimization_suggestions(
    status: Optional[str] = "pending",
    request: Request = None
):
    """
    获取成本优化建议列表

    返回基于使用分析和成本分析生成的优化建议。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    suggestions = _suggestions.values()
    if status:
        suggestions = [s for s in suggestions if s.get("status") == status]

    return {
        "success": True,
        "suggestions": sorted(suggestions, key=lambda x: x.get("timestamp", ""), reverse=True)
    }

@router.post("/suggestions/{suggestion_id}/implement", response_model=Dict[str, Any])
async def implement_suggestion(
    suggestion_id: str,
    request: Request
):
    """
    标记建议为已实施

    记录优化建议的实施状态。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    if suggestion_id not in _suggestions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found"
        )

    suggestion = _suggestions[suggestion_id]
    suggestion.status = "implemented"

    _save_data()

    # Log implementation
    audit_manager = get_audit_manager()
    audit_manager.log_configuration_change(
        request_id=f"implement_suggest_{suggestion_id}",
        source_ip=client_ip,
        config_key="suggestion_status",
        old_value="pending",
        new_value="implemented"
    )

    return {
        "success": True,
        "suggestion_id": suggestion_id,
        "status": "implemented"
    }

@router.post("/tokens/cost", response_model=Dict[str, Any])
async def update_token_cost(
    request: Request,
    api_name: str,
    model: str,
    token_count: int,
    cost: float
):
    """
    更新token成本

    用于从外部系统（如百度云API账单）同步实际成本。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Get recent API call records
    recent_records = [
        r for r in _cost_records.values()
        if r.api_name == api_name and r.timestamp.startswith(datetime.now().strftime("%Y-%m"))
    ][:10]  # Last 10 records

    if recent_records:
        # Update the most recent record
        record = recent_records[-1]
        record.actual_cost = cost
        _cost_records[record.request_id] = record
        _save_data()

    return {
        "success": True,
        "updated_records": len(recent_records),
        "unit_cost": round(cost / token_count, 4) if token_count > 0 else 0
    }

@router.get("/dashboard", response_class=Dict[str, Any])
async def get_dashboard_data(
    request: Request
):
    """
    获取成本监控面板数据

    返回用于可视化展示的完整成本数据。
    """
    client_ip = request.client.host if request.client else "127.0.0.1"

    current_month = datetime.now().strftime("%Y-%m")
    last_30_days = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Calculate stats
    total_requests = 0
    total_tokens = 0
    total_cost = 0.0

    for record in _cost_records.values():
        record_date = record.timestamp[:10]
        if record_date >= last_30_days:
            total_requests += 1
            total_tokens += record.token_count
            cost = record.actual_cost or record.cost_estimate
            total_cost += cost

    return {
        "success": True,
        "period": "last_30_days",
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 2),
        "requests_per_day": round(total_requests / 30, 1),
        "tokens_per_request": round(total_tokens / total_requests, 1) if total_requests > 0 else 0,
        "cost_per_1000_tokens": round(total_cost / total_tokens * 1000, 2) if total_tokens > 0 else 0
    }
