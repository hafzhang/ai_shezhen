# A/B测试与灰度发布指南
# A/B Testing and Canary Deployment Guide

## 目录 / Table of Contents

1. [概述](#概述)
2. [A/B测试框架](#ab测试框架)
3. [灰度发布策略](#灰度发布策略)
4. [模型版本管理](#模型版本管理)
5. [回滚机制](#回滚机制)
6. [发布流程](#发布流程)
7. [监控指标](#监控指标)
8. [最佳实践](#最佳实践)

---

## 概述 / Overview

本文档描述了AI舌诊智能诊断系统的A/B测试与灰度发布策略，确保新模型版本的安全上线和平滑过渡。

### 目标 / Goals

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 灰度发布时间 | 2-4周 | 从5%到100%的渐进式发布 |
| A/B测试样本量 | ≥ 1000 | 每个分组至少1000次诊断 |
| 统计显著性 | p < 0.05 | 置信度95%以上 |
| 回滚时间 | ≤ 5分钟 | 检测到问题后快速回滚 |
| 流量分配精度 | ±1% | 实际流量与预期偏差 |

### 发布类型 / Release Types

1. **A/B测试**: 对比两个模型版本的性能
2. **灰度发布**: 新版本渐进式替换旧版本
3. **金丝雀发布**: 先开放给小部分用户验证
4. **蓝绿部署**: 快速切换的发布方式

---

## A/B测试框架 / A/B Testing Framework

### 架构设计 / Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Load Balancer / Gateway      │
                    │         (Traffic Router)            │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────┴───────────────────┐
                    │                                       │
         ┌──────────▼──────────┐              ┌───────────▼──────────┐
         │   Control Group    │              │    Treatment Group   │
         │   (Current Model)  │              │     (New Model)      │
         │                     │              │                      │
         │  Traffic: 50%       │              │  Traffic: 50%        │
         │  ┌───────────────┐  │              │  ┌───────────────┐   │
         │  │ API Service   │  │              │  │ API Service   │   │
         │  │ (v1.0)        │  │              │  │ (v1.1)        │   │
         │  └───────────────┘  │              │  └───────────────┘   │
         │                     │              │                      │
         └─────────────────────┘              └──────────────────────┘
                    │                                       │
                    └──────────────────┬────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │  Metrics Store  │
                              │  (Prometheus)    │
                              └─────────────────┘
```

### 流量路由配置 / Traffic Routing

```python
# api_service/app/ab_testing/traffic_router.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict
import hashlib
import logging

logger = logging.getLogger(__name__)


class ModelVersion(Enum):
    """模型版本枚举"""
    CONTROL = "control"      # 对照组（当前版本）
    TREATMENT = "treatment"  # 实验组（新版本）


@dataclass
class ExperimentConfig:
    """A/B测试配置"""
    experiment_id: str
    name: str
    description: str
    traffic_split: Dict[ModelVersion, float]  # 流量分配比例
    start_time: str
    end_time: Optional[str] = None
    min_sample_size: int = 1000
    metrics: list = None

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = ["accuracy", "latency_p95", "user_satisfaction"]


class TrafficRouter:
    """流量路由器"""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self._validate_traffic_split()

    def _validate_traffic_split(self):
        """验证流量分配比例总和为1"""
        total = sum(self.config.traffic_split.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Traffic split must sum to 1.0, got {total}")

    def assign_group(self, user_id: str, session_id: Optional[str] = None) -> ModelVersion:
        """
        为用户分配实验组

        使用一致性哈希确保同一用户始终分配到同一组

        Args:
            user_id: 用户ID
            session_id: 会话ID（可选）

        Returns:
            分配的模型版本
        """
        # 组合键确保一致性
        key = f"{self.config.experiment_id}:{user_id}"
        if session_id:
            key += f":{session_id}"

        # 计算哈希值
        hash_value = int(hashlib.sha256(key.encode()).hexdigest(), 16) % 100

        # 根据哈希值分配组
        threshold = 0
        for version, split in sorted(
            self.config.traffic_split.items(),
            key=lambda x: x[0].value
        ):
            threshold += split * 100
            if hash_value < threshold:
                return version

        return ModelVersion.CONTROL  # 默认对照组

    def get_model_path(self, version: ModelVersion) -> str:
        """获取模型路径"""
        version_map = {
            ModelVersion.CONTROL: "/app/models/deploy/segment_fp16",
            ModelVersion.TREATMENT: "/app/models/deploy/segment_v2_fp16"
        }
        return version_map.get(version, version_map[ModelVersion.CONTROLLER])


# 默认实验配置
DEFAULT_EXPERIMENT = ExperimentConfig(
    experiment_id="exp_001",
    name="Segmentation Model V2 Test",
    description="Testing new segmentation model with improved boundary detection",
    traffic_split={
        ModelVersion.CONTROL: 0.5,
        ModelVersion.TREATMENT: 0.5
    },
    start_time="2026-02-21T00:00:00Z",
    min_sample_size=1000
)
```

### 统计显著性检验 / Statistical Significance Test

```python
# api_service/app/ab_testing/statistical_test.py

import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class ExperimentMetrics:
    """实验指标"""
    group: str
    sample_size: int
    mean: float
    std: float
    values: List[float]


@dataclass
class TestResult:
    """统计检验结果"""
    metric_name: str
    control_mean: float
    treatment_mean: float
    relative_improvement: float
    absolute_improvement: float
    p_value: float
    is_significant: bool
    confidence_interval: tuple
    recommendation: str


class ABTestAnalyzer:
    """A/B测试分析器"""

    def __init__(self, alpha: float = 0.05):
        """
        初始化分析器

        Args:
            alpha: 显著性水平（默认0.05）
        """
        self.alpha = alpha

    def compare_metrics(
        self,
        control_values: List[float],
        treatment_values: List[float],
        metric_name: str
    ) -> TestResult:
        """
        比较两组指标的统计显著性

        使用独立样本t检验

        Args:
            control_values: 对照组指标值
            treatment_values: 实验组指标值
            metric_name: 指标名称

        Returns:
            检验结果
        """
        control = np.array(control_values)
        treatment = np.array(treatment_values)

        # 计算基本统计量
        control_mean = np.mean(control)
        treatment_mean = np.mean(treatment)
        control_std = np.std(control, ddof=1)
        treatment_std = np.std(treatment, ddof=1)

        # 执行t检验
        t_stat, p_value = stats.ttest_ind(treatment, control)

        # 计算置信区间
        se_diff = np.sqrt(
            control_std**2 / len(control) +
            treatment_std**2 / len(treatment)
        )
        ci_margin = 1.96 * se_diff  # 95% CI
        diff_mean = treatment_mean - control_mean

        # 判断显著性
        is_significant = p_value < self.alpha

        # 计算改善幅度
        absolute_improvement = diff_mean
        relative_improvement = (diff_mean / control_mean) * 100 if control_mean != 0 else 0

        # 生成建议
        if is_significant and relative_improvement > 0:
            recommendation = "ADOPT"
        elif is_significant and relative_improvement < 0:
            recommendation = "REJECT"
        else:
            recommendation = "CONTINUE"

        return TestResult(
            metric_name=metric_name,
            control_mean=control_mean,
            treatment_mean=treatment_mean,
            relative_improvement=relative_improvement,
            absolute_improvement=absolute_improvement,
            p_value=p_value,
            is_significant=is_significant,
            confidence_interval=(
                diff_mean - ci_margin,
                diff_mean + ci_margin
            ),
            recommendation=recommendation
        )

    def generate_report(
        self,
        results: List[TestResult],
        experiment_name: str
    ) -> Dict:
        """
        生成A/B测试报告

        Args:
            results: 所有指标的检验结果
            experiment_name: 实验名称

        Returns:
            报告字典
        """
        return {
            "experiment_name": experiment_name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_metrics": len(results),
                "significant_improvements": sum(
                    1 for r in results
                    if r.is_significant and r.relative_improvement > 0
                ),
                "significant_regressions": sum(
                    1 for r in results
                    if r.is_significant and r.relative_improvement < 0
                ),
                "overall_recommendation": self._get_overall_recommendation(results)
            },
            "metrics": [
                {
                    "name": r.metric_name,
                    "control_mean": r.control_mean,
                    "treatment_mean": r.treatment_mean,
                    "relative_improvement": f"{r.relative_improvement:.2f}%",
                    "p_value": r.p_value,
                    "is_significant": r.is_significant,
                    "confidence_interval": r.confidence_interval,
                    "recommendation": r.recommendation
                }
                for r in results
            ]
        }

    def _get_overall_recommendation(self, results: List[TestResult]) -> str:
        """获取总体建议"""
        # 如果有关键指标显著下降，拒绝
        critical_metrics = ["accuracy", "user_satisfaction"]
        for r in results:
            if r.metric_name in critical_metrics:
                if r.is_significant and r.relative_improvement < -5:
                    return "REJECT"

        # 如果有关键指标显著改善，采纳
        for r in results:
            if r.metric_name in critical_metrics:
                if r.is_significant and r.relative_improvement > 5:
                    return "ADOPT"

        # 否则继续收集数据
        return "CONTINUE"
```

---

## 灰度发布策略 / Canary Deployment Strategy

### 发布阶段 / Release Phases

```python
# api_service/app/canary/deployment_phases.py

from enum import Enum
from dataclasses import dataclass
from typing import List


class Phase(Enum):
    """发布阶段"""
    INTERNAL = "internal"           # 内部测试
    CANARY_5 = "canary_5"           # 5% 灰度
    CANARY_10 = "canary_10"         # 10% 灰度
    CANARY_25 = "canary_25"         # 25% 灰度
    CANARY_50 = "canary_50"         # 50% 灰度
    CANARY_75 = "canary_75"         # 75% 灰度
    CANARY_100 = "canary_100"       # 100% 全量


@dataclass
class PhaseConfig:
    """阶段配置"""
    phase: Phase
    traffic_percentage: int
    min_duration_hours: int
    success_criteria: Dict[str, float]
    rollback_triggers: Dict[str, float]


# 默认灰度发布配置
CANARY_PHASES = [
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
        min_duration_hours=168,  # 1周观察期
        success_criteria={"accuracy": ">0.92", "latency_p95": "<450"},
        rollback_triggers={"error_rate": ">0.01", "user_satisfaction": "<0.92"}
    ),
]
```

### 自动化发布控制器 / Automated Release Controller

```python
# api_service/app/canary/release_controller.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class ReleaseController:
    """发布控制器"""

    def __init__(self, phases: List[PhaseConfig], metrics_store):
        self.phases = phases
        self.metrics_store = metrics_store
        self.current_phase_index = 0
        self.phase_start_time: Optional[datetime] = None
        self.is_running = False

    async def start_release(self, new_model_version: str):
        """
        启动灰度发布流程

        Args:
            new_model_version: 新模型版本标识
        """
        logger.info(f"Starting canary release for model: {new_model_version}")
        self.is_running = True
        self.current_phase_index = 0

        await self._enter_phase(new_model_version)

        while self.is_running and self.current_phase_index < len(self.phases):
            await self._monitor_phase()
            await asyncio.sleep(300)  # 每5分钟检查一次

    async def _enter_phase(self, model_version: str):
        """进入当前阶段"""
        phase = self.phases[self.current_phase_index]

        # 更新流量分配
        await self._update_traffic_split(
            model_version,
            phase.traffic_percentage
        )

        self.phase_start_time = datetime.now()
        logger.info(
            f"Entered phase: {phase.phase.value}, "
            f"traffic: {phase.traffic_percentage}%"
        )

    async def _monitor_phase(self):
        """监控当前阶段"""
        phase = self.phases[self.current_phase_index]

        # 检查最小持续时间
        elapsed = datetime.now() - self.phase_start_time
        if elapsed < timedelta(hours=phase.min_duration_hours):
            logger.debug(
                f"Phase minimum duration not met: "
                f"{elapsed} / {phase.min_duration_hours}h"
            )
            return

        # 收集指标
        metrics = await self._collect_metrics()

        # 检查回滚条件
        if self._should_rollback(phase, metrics):
            logger.warning("Rollback triggers met, initiating rollback...")
            await self.rollback()
            return

        # 检查成功条件
        if self._meets_success_criteria(phase, metrics):
            logger.info("Phase success criteria met, advancing to next phase...")
            self.current_phase_index += 1

            if self.current_phase_index < len(self.phases):
                await self._enter_phase(self.current_model_version)
            else:
                logger.info("All phases completed successfully!")
                self.is_running = False
        else:
            logger.info("Success criteria not yet met, continuing monitoring...")

    async def _update_traffic_split(self, model_version: str, percentage: int):
        """更新流量分配"""
        # 更新Nginx/LB配置
        pass

    async def _collect_metrics(self) -> Dict:
        """收集当前指标"""
        # 从Prometheus查询指标
        return {
            "accuracy": 0.92,
            "latency_p95": 450,
            "error_rate": 0.01,
            "user_satisfaction": 0.93
        }

    def _should_rollback(self, phase: PhaseConfig, metrics: Dict) -> bool:
        """判断是否应该回滚"""
        for metric, trigger in phase.rollback_triggers.items():
            value = metrics.get(metric, 0)
            op, threshold = trigger[0], float(trigger[1:])

            if op == ">" and value > threshold:
                logger.warning(
                    f"Rollback trigger: {metric}={value} {trigger}"
                )
                return True
            elif op == "<" and value < threshold:
                logger.warning(
                    f"Rollback trigger: {metric}={value} {trigger}"
                )
                return True

        return False

    def _meets_success_criteria(self, phase: PhaseConfig, metrics: Dict) -> bool:
        """判断是否满足成功条件"""
        for metric, criterion in phase.success_criteria.items():
            value = metrics.get(metric)
            if value is None:
                return False

            op, threshold = criterion[0], float(criterion[1:])

            if op == ">" and value <= threshold:
                logger.debug(
                    f"Success criteria not met: {metric}={value} {criterion}"
                )
                return False
            elif op == "<" and value >= threshold:
                logger.debug(
                    f"Success criteria not met: {metric}={value} {criterion}"
                )
                return False

        return True

    async def rollback(self):
        """回滚到上一版本"""
        logger.warning("Initiating rollback...")

        # 恢复100%流量到旧版本
        await self._update_traffic_split(
            self.previous_model_version,
            100
        )

        self.is_running = False
        logger.info("Rollback completed")
```

---

## 模型版本管理 / Model Version Management

### 版本控制 / Version Control

```python
# api_service/app/model_management/version_manager.py

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import json
import shutil


@dataclass
class ModelVersion:
    """模型版本信息"""
    version: str
    model_type: str  # segment/classify
    path: str
    created_at: str
    metrics: Dict[str, float]
    status: str  # staging/production/retired
    parent_version: Optional[str] = None


class ModelVersionManager:
    """模型版本管理器"""

    def __init__(self, registry_path: str = "/data/models/registry.json"):
        self.registry_path = Path(registry_path)
        self.registry: Dict[str, ModelVersion] = {}
        self._load_registry()

    def _load_registry(self):
        """加载版本注册表"""
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                data = json.load(f)
                for version_str, version_data in data.items():
                    self.registry[version_str] = ModelVersion(**version_data)

    def _save_registry(self):
        """保存版本注册表"""
        data = {
            version: v.__dict__
            for version, v in self.registry.items()
        }
        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def register_version(
        self,
        version: str,
        model_type: str,
        path: str,
        metrics: Dict[str, float],
        parent_version: Optional[str] = None
    ):
        """注册新模型版本"""
        model_version = ModelVersion(
            version=version,
            model_type=model_type,
            path=path,
            created_at=datetime.now().isoformat(),
            metrics=metrics,
            status="staging",
            parent_version=parent_version
        )
        self.registry[version] = model_version
        self._save_registry()

    def get_production_version(self, model_type: str) -> Optional[ModelVersion]:
        """获取生产版本"""
        for version in self.registry.values():
            if version.model_type == model_type and version.status == "production":
                return version
        return None

    def set_production_version(self, version: str):
        """设置生产版本"""
        if version not in self.registry:
            raise ValueError(f"Version {version} not found")

        model_type = self.registry[version].model_type

        # 将当前生产版本标记为retired
        current_prod = self.get_production_version(model_type)
        if current_prod:
            current_prod.status = "retired"

        # 设置新版本为生产
        self.registry[version].status = "production"
        self._save_registry()

    def rollback_to_version(self, version: str):
        """回滚到指定版本"""
        if version not in self.registry:
            raise ValueError(f"Version {version} not found")

        model_type = self.registry[version].model_type
        current_prod = self.get_production_version(model_type)

        # 交换版本
        if current_prod:
            current_prod.status = "staging"

        self.registry[version].status = "production"
        self._save_registry()
```

---

## 回滚机制 / Rollback Mechanism

### 自动回滚触发条件 / Automatic Rollback Triggers

```yaml
# canary_rollback_config.yml

rollback_triggers:
  # P0级 - 立即回滚
  critical:
    error_rate:
      threshold: 0.05  # 5%
      window: 5m
    api_latency_p99:
      threshold: 2000  # 2000ms
      window: 5m
    model_load_failure:
      threshold: 0.1   # 10%
      window: 1m

  # P1级 - 告警后回滚
  high:
    user_satisfaction:
      threshold: 0.7   # 70%
      window: 30m
    accuracy_drop:
      threshold: 0.05  # 5%下降
      window: 15m
    memory_usage:
      threshold: 0.9   # 90%
      window: 10m

  # P2级 - 观察后决定
  medium:
    latency_p95_increase:
      threshold: 0.2   # 20%增加
      window: 1h
    cpu_usage:
      threshold: 0.8   # 80%
      window: 1h
```

### 回滚执行 / Rollback Execution

```python
# api_service/app/canary/rollback_executor.py

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RollbackExecutor:
    """回滚执行器"""

    def __init__(self, version_manager: ModelVersionManager, traffic_manager):
        self.version_manager = version_manager
        self.traffic_manager = traffic_manager

    async def execute_rollback(
        self,
        reason: str,
        target_version: Optional[str] = None
    ):
        """
        执行回滚

        Args:
            reason: 回滚原因
            target_version: 目标版本（None则回滚到上一生产版本）
        """
        logger.error(f"Executing rollback: {reason}")

        # 确定目标版本
        if target_version is None:
            # 查找最近的稳定版本
            target_version = self._find_stable_version()

        if not target_version:
            logger.error("No valid target version for rollback")
            return False

        # 1. 切换流量
        logger.info(f"Switching traffic to version: {target_version}")
        await self.traffic_manager.set_production_version(target_version)

        # 2. 更新版本状态
        logger.info(f"Setting {target_version} as production")
        self.version_manager.set_production_version(target_version)

        # 3. 验证回滚成功
        success = await self._verify_rollback(target_version)

        if success:
            logger.info("Rollback completed successfully")
            # 发送回滚通知
            await self._send_rollback_notification(reason, target_version)
        else:
            logger.error("Rollback verification failed")

        return success

    def _find_stable_version(self) -> Optional[str]:
        """查找最近的稳定版本"""
        # 查找曾是production的版本
        for version in sorted(
            self.version_manager.registry.values(),
            key=lambda v: v.created_at,
            reverse=True
        ):
            if version.status in ["retired", "production"]:
                return version.version
        return None

    async def _verify_rollback(self, version: str) -> bool:
        """验证回滚是否成功"""
        # 检查服务健康状态
        # 检查关键指标
        return True

    async def _send_rollback_notification(self, reason: str, version: str):
        """发送回滚通知"""
        # 发送到告警系统
        pass
```

---

## 发布流程 / Release Process

### 标准发布流程 / Standard Release Process

```
┌─────────────────────────────────────────────────────────────────┐
│                    发布流程 / Release Flow                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 准备阶段 / Preparation                                    │
│     ├─ 新模型训练与验证                                         │
│     ├─ 评估报告生成                                             │
│     ├─ 代码审查                                                 │
│     └─ 创建发布计划                                             │
│                                                                 │
│  2. 内部测试阶段 / Internal Testing                            │
│     ├─ 部署到staging环境                                        │
│     ├─ 运行完整测试套件                                         │
│     ├─ 性能基准测试                                             │
│     └─ 安全扫描                                                 │
│                                                                 │
│  3. 灰度发布阶段 / Canary Deployment                           │
│     ├─ 5% 灰度 (48小时)                                         │
│     ├─ 10% 灰度 (48小时)                                        │
│     ├─ 25% 灰度 (72小时)                                        │
│     ├─ 50% 灰度 (72小时)                                        │
│     ├─ 75% 灰度 (96小时)                                        │
│     └─ 100% 全量 (168小时观察期)                                │
│                                                                 │
│  4. 监控与调整 / Monitoring & Adjustment                       │
│     ├─ 实时监控关键指标                                         │
│     ├─ 收集用户反馈                                             │
│     ├─ 必要时暂停或回滚                                         │
│     └─ 调整流量分配                                             │
│                                                                 │
│  5. 完成与总结 / Completion & Summary                          │
│     ├─ 生成发布报告                                             │
│     ├─ 记录经验教训                                             │
│     ├─ 更新文档                                                 │
│     └─ 归档相关数据                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 发布检查清单 / Release Checklist

```markdown
# 发布检查清单 / Release Checklist

## 准备阶段 / Preparation
- [ ] 新模型通过所有单元测试
- [ ] 新模型通过集成测试
- [ ] 性能基准测试达标
- [ ] 安全扫描无高危漏洞
- [ ] 代码审查完成
- [ ] 发布计划已批准
- [ ] 回滚计划已准备

## 灰度发布前 / Pre-Canary
- [ ] 备份当前生产版本
- [ ] 准备监控仪表板
- [ ] 配置告警规则
- [ ] 通知相关人员
- [ ] 准备回滚脚本

## 灰度发布中 / During Canary
- [ ] 5% 阶段指标正常
- [ ] 10% 阶段指标正常
- [ ] 25% 阶段指标正常
- [ ] 50% 阶段指标正常
- [ ] 75% 阶段指标正常
- [ ] 用户反馈良好

## 发布完成后 / Post-Release
- [ ] 100% 流量稳定
- [ ] 生成发布报告
- [ ] 更新文档
- [ ] 团队复盘会议
- [ ] 归档相关数据
```

---

## 监控指标 / Monitoring Metrics

### 关键指标 / Key Metrics

| 类别 | 指标 | 目标值 | 说明 |
|------|------|--------|------|
| **性能** | API延迟P50 | < 200ms | 中位响应时间 |
| **性能** | API延迟P95 | < 500ms | 95分位响应时间 |
| **性能** | API延迟P99 | < 1000ms | 99分位响应时间 |
| **质量** | 准确率 | > 90% | 诊断准确率 |
| **质量** | 错误率 | < 1% | API错误率 |
| **质量** | 用户满意度 | > 90% | 正面反馈比例 |
| **稳定性** | 可用性 | > 99.9% | 服务可用时间比例 |
| **稳定性** | 回滚率 | < 5% | 回滚次数比例 |

### Prometheus 查询 / Prometheus Queries

```promql
# 新旧版本对比
# 准确率对比
accuracy_by_version{model_version="v2.0"} / accuracy_by_version{model_version="v1.0"}

# 延迟对比
rate(api_latency_seconds_bucket{version="v2.0"}[5m]) /
rate(api_latency_seconds_bucket{version="v1.0"}[5m])

# 错误率对比
sum(rate(api_errors_total{version="v2.0"}[5m])) /
sum(rate(api_requests_total{version="v2.0"}[5m]))
```

---

## 最佳实践 / Best Practices

### 1. 小步迭代 / Small Iterations

- 每次发布只包含有限变更
- 避免同时修改多个组件
- 便于定位问题和快速回滚

### 2. 数据驱动 / Data Driven

- 基于实际数据做决策
- 避免主观判断
- 设置明确的成功/失败标准

### 3. 快速反馈 / Fast Feedback

- 实时监控关键指标
- 设置合理的告警阈值
- 建立快速响应机制

### 4. 充分测试 / Comprehensive Testing

- 内部测试充分
- 灰度阶段逐步验证
- 收集真实用户反馈

### 5. 完善文档 / Documentation

- 记录每次发布
- 总结经验教训
- 持续优化流程

---

**文档版本**: v1.0
**最后更新**: 2026-02-21
**维护者**: AI舌诊智能诊断系统团队
