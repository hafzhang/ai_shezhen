"""
AI舌诊智能诊断系统 - 技术领导代理 (Tech Lead Agent)
=====================================================

角色定位：
    资深技术负责人，负责整体架构把控、技术选型决策和各模块协调工作

核心职责：
    1. 整体架构审查与把关
    2. 技术选型决策（PaddlePaddle生态 vs PyTorch等）
    3. 各模块接口协调与规范制定
    4. 代码审查决策（PR审查、架构决策记录）
    5. 技术风险评估与应对

项目背景：
    - 项目名称：AI舌诊智能诊断系统
    - 技术栈：PaddleSeg + PaddleClas + FastAPI + 文心4.5 API
    - 数据集：shezhenv3-coco (5594训练/572验证/553测试)
    - 核心挑战：类别严重不平衡（淡白舌占80.9%）
    - 架构：本地推理 + 云端诊断混合方案

版本：v1.0
创建日期：2026-02-11
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


# ============================================================================
# 枚举定义
# ============================================================================

class RiskLevel(Enum):
    """风险等级"""
    LOW = "P3 - 低"
    MEDIUM = "P2 - 中"
    HIGH = "P1 - 高"
    CRITICAL = "P0 - 紧急"


class DecisionStatus(Enum):
    """决策状态"""
    PROPOSED = "已提议"
    REVIEWED = "评审中"
    APPROVED = "已批准"
    REJECTED = "已拒绝"
    DEPRECATED = "已废弃"


class ModuleType(Enum):
    """模块类型"""
    SEGMENTATION = "舌体分割"
    CLASSIFICATION = "舌象分类"
    PREPROCESSING = "图像预处理"
    API = "API服务"
    LLM = "云端诊断"
    DEPLOYMENT = "部署运维"


class ReviewResult(Enum):
    """审查结果"""
    EXCELLENT = "优秀"
    NEEDS_IMPROVEMENT = "需改进"
    MUST_FIX = "必须修复"


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class ArchitectureDecision:
    """架构决策记录 (ADR)"""
    id: str
    title: str
    status: DecisionStatus
    date: str
    context: str
    decision: str
    consequences: List[str]
    alternatives: List[Dict[str, str]]
    rationale: str
    related_decisions: List[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """风险评估"""
    id: str
    name: str
    level: RiskLevel
    probability: float  # 0-1
    impact: str
    description: str
    mitigation: List[str]
    owner: str


@dataclass
class TechChoice:
    """技术选型对比"""
    category: str
    options: List[Dict[str, Any]]
    recommendation: str
    rationale: str


@dataclass
class CodeReview:
    """代码审查"""
    pr_id: str
    module: ModuleType
    reviewer: str
    date: str
    summary: str
    findings: List[Dict[str, Any]]
    verdict: str
    conditions: List[str] = field(default_factory=list)


@dataclass
class InterfaceSpec:
    """接口规范"""
    module_from: str
    module_to: str
    data_format: str
    endpoint: str
    input_schema: Dict
    output_schema: Dict
    error_handling: str
    version: str = "1.0"


# ============================================================================
# 技术领导代理主类
# ============================================================================

class TechLeadAgent:
    """
    AI舌诊智能诊断系统 - 技术领导代理

    负责项目技术决策、架构审查、风险评估和代码审查
    """

    # 项目知识库
    PROJECT_CONTEXT = {
        "name": "AI舌诊智能诊断系统",
        "tech_stack": {
            "segmentation": "PaddleSeg (BiSeNetV2 + STDCNet2)",
            "classification": "PaddleClas (PP-HGNetV2-B4)",
            "api": "FastAPI",
            "llm": "文心4.5 API (ERNIE-Speed推荐)",
            "deployment": "Docker + Redis + Celery"
        },
        "dataset": {
            "name": "shezhenv3-coco",
            "train": 5594,
            "val": 572,
            "test": 553,
            "total": 6719,
            "imbalance_note": "淡白舌占80.9%，严重不平衡"
        },
        "architecture": {
            "layers": [
                "用户交互层 (小程序/APP/Web)",
                "业务服务层 (本地推理)",
                "云端诊断层 (文心4.5 API)"
            ],
            "pipeline": [
                "图像预处理 (归一化/增强/质量检测)",
                "舌体分割 (BiSeNetV2 + STDCNet2)",
                "特征提取 (颜色/纹理/舌象区域裁剪)",
                "舌象分类 (PP-HGNetV2-B4, 多标签)",
                "云端诊断 (文心4.5 API)"
            ]
        },
        "key_challenges": [
            "类别严重不平衡（淡白舌80.9%）",
            "多标签分类（21类→6维度18类重构）",
            "医学场景高可靠性要求",
            "成本控制（API调用）",
            "部署环境多样（CPU/GPU）"
        ]
    }

    # 模型选型知识库
    MODEL_CHOICES = {
        "segmentation": {
            "MobileNetV3": {
                "params": "2M",
                "accuracy": "mIoU 0.85",
                "speed": "高",
                "use_case": "<1000样本，移动端优先"
            },
            "STDCNet2": {
                "params": "4M",
                "accuracy": "mIoU 0.90",
                "speed": "中高",
                "use_case": "5000-10000样本，平衡方案"
            },
            "HRNet": {
                "params": "40M",
                "accuracy": "mIoU 0.95",
                "speed": "低",
                "use_case": ">10000样本，追求最高精度"
            }
        },
        "classification": {
            "MobileNetV3": {
                "params": "5.5M",
                "accuracy": "Top-1 75%",
                "speed": "极高",
                "use_case": "边缘部署，速度优先"
            },
            "PP-HGNetV2-B4": {
                "params": "~50M",
                "accuracy": "Top-1 82%",
                "speed": "高",
                "use_case": "服务器部署，平衡方案（推荐）"
            },
            "ResNet101_vd": {
                "params": "~45M",
                "accuracy": "Top-1 85%",
                "speed": "中",
                "use_case": "精度优先，有充足GPU"
            }
        }
    }

    # 损失函数配置
    LOSS_CONFIG = {
        "segmentation": {
            "cross_entropy": {"weight": 0.5, "description": "基础分类损失"},
            "dice": {"weight": 0.3, "description": "区域重叠损失"},
            "boundary": {"weight": 0.2, "description": "边缘精细化损失"}
        },
        "classification": {
            "bce": {"weight": 0.4, "description": "多标签二值交叉熵"},
            "focal": {"weight": 0.4, "alpha": 0.25, "gamma": 2, "description": "聚焦难样本"},
            "asymmetric": {"weight": 0.2, "description": "正负样本不平衡处理"}
        }
    }

    # 部署策略
    DEPLOYMENT_STRATEGIES = {
        "cpu": {
            "pros": ["成本低", "部署简单", "可扩展性好"],
            "cons": ["推理慢", "不适合大模型"],
            "recommendation": "分割+分类模型，使用MKL加速",
            "hardware": "8核+ CPU, 16GB+ 内存"
        },
        "gpu": {
            "pros": ["推理速度快", "支持大模型"],
            "cons": ["成本高", "维护复杂"],
            "recommendation": "生产环境，高并发场景",
            "hardware": "NVIDIA T4 (16GB) 或更高"
        },
        "int8": {
            "pros": ["模型小75%", "推理快40%", "精度损失<2%"],
            "cons": ["需要量化校准数据"],
            "recommendation": "移动端部署推荐",
            "hardware": "支持INT8的CPU/GPU"
        }
    }

    # 缓存策略
    CACHE_STRATEGY = {
        "redis": {
            "feature_ttl": 86400,  # 24小时
            "diagnosis_ttl": 3600,  # 1小时
            "max_memory": "2GB",
            "eviction": "allkeys-lru"
        },
        "fallback": {
            "local_rules": True,
            "historical_cases": True,
            "timeout": 10  # 秒
        }
    }

    # 监控指标 (P0-P3级)
    MONITORING_METRICS = {
        "P0": {
            "api_availability": {"threshold": "< 95%", "action": "电话+短信+钉钉"},
            "error_rate": {"threshold": "> 10%", "action": "电话+短信+钉钉"}
        },
        "P1": {
            "response_p99": {"threshold": "> 5s", "action": "短信+钉钉"},
            "gpu_memory": {"threshold": "> 90%", "action": "短信+钉钉"}
        },
        "P2": {
            "api_volume_anomaly": {"threshold": "±50%", "action": "钉钉"},
            "cost_over_budget": {"threshold": "> 80%", "action": "钉钉+邮件"}
        },
        "P3": {
            "model_drift": {"threshold": "分布偏移>0.2", "action": "邮件"}
        }
    }

    def __init__(self):
        """初始化技术领导代理"""
        self.decisions: List[ArchitectureDecision] = []
        self.risks: List[RiskAssessment] = []
        self.reviews: List[CodeReview] = []
        self.interfaces: List[InterfaceSpec] = []

        # 初始化项目默认架构决策
        self._initialize_decisions()

    def _initialize_decisions(self):
        """初始化项目核心架构决策"""
        core_decisions = [
            ArchitectureDecision(
                id="ADR-001",
                title="采用PaddlePaddle生态作为深度学习框架",
                status=DecisionStatus.APPROVED,
                date="2026-02-11",
                context="项目需要分割+分类+部署一体化方案，国内医疗场景需要本土化技术支持",
                decision="使用PaddleSeg进行舌体分割，PaddleClas进行舌象分类，FastDeploy进行推理部署",
                consequences=[
                    "正面：完善的中文文档和技术支持",
                    "正面：与文心大模型生态无缝集成",
                    "正面：INT8量化工具成熟，适合部署",
                    "负面：相比PyTorch，社区规模较小",
                    "负面：部分前沿算法实现较慢"
                ],
                alternatives=[
                    {"方案": "PyTorch", "优势": "生态最成熟", "劣势": "文心API集成复杂"},
                    {"方案": "TensorFlow", "优势": "部署方案成熟", "劣势": "学习曲线陡峭"}
                ],
                rationale="考虑到文心4.5 API集成需求和国内部署环境，PaddlePaddle是最佳选择"
            ),
            ArchitectureDecision(
                id="ADR-002",
                title="BiSeNetV2 + STDCNet2 用于舌体分割",
                status=DecisionStatus.APPROVED,
                date="2026-02-11",
                context=f"数据集约5500张，需要平衡精度和速度，医疗场景对边缘分割要求高",
                decision="使用BiSeNetV2架构，STDCNet2作为骨干网络，输入512×512",
                consequences=[
                    "正面：实时分割能力（>30 FPS CPU）",
                    "正面：边缘分割精准，适合舌体轮廓",
                    "正面：模型大小<10MB，易于部署",
                    "负面：相比HRNet，精度略低（预期mIoU 0.92 vs 0.95）"
                ],
                alternatives=[
                    {"方案": "PP-LiteSeg", "优势": "速度更快", "劣势": "边缘精度较低"},
                    {"方案": "HRNet + OCRNet", "优势": "SOTA精度", "劣势": "推理慢，模型大"}
                ],
                rationale="5594张样本规模适合中等大小模型，BiSeNetV2在医学图像分割表现优异"
            ),
            ArchitectureDecision(
                id="ADR-003",
                title="多标签分类重构：21类→6维度18类",
                status=DecisionStatus.APPROVED,
                date="2026-02-11",
                context="原始21类混合了舌象特征和证型标签，淡白舌占比80.9%严重不平衡",
                decision="重构为6维度多标签分类：舌色(4)+苔色(4)+舌形(3)+苔质(3)+特征(3)+健康(1)",
                consequences=[
                    "正面：符合中医辨证逻辑",
                    "正面：多标签学习更合理",
                    "正面：便于模型集成和解释",
                    "负面：需要重新标注映射",
                    "负面：增加了模型复杂度"
                ],
                alternatives=[
                    {"方案": "保持21类单标签", "优势": "无需改动", "劣势": "不符合医学逻辑"},
                    {"方案": "二分类（健康/异常）", "优势": "简单", "劣势": "信息损失大"}
                ],
                rationale="多标签分类符合舌诊实际（单张图可有多个特征），分层维度便于后续LLM推理"
            ),
            ArchitectureDecision(
                id="ADR-004",
                title="类别不平衡应对：Focal Loss + 分层采样 + 困难样本挖掘",
                status=DecisionStatus.APPROVED,
                date="2026-02-11",
                context="淡白舌占80.9%，部分类别样本<100，常规训练会导致模型偏向多数类",
                decision="三管齐下：1) Focal Loss(α=0.25, γ=2) 2) 分层采样保证batch内平衡 3) 困难样本挖掘",
                consequences=[
                    "正面：少数类召回率预期提升30%",
                    "正面：模型鲁棒性增强",
                    "负面：训练时间增加约20%",
                    "负面：需要调参优化"
                ],
                alternatives=[
                    {"方案": "仅过采样/欠采样", "优势": "简单", "劣势": "过拟合风险"},
                    {"方案": "代价敏感学习", "优势": "理论成熟", "劣势": "权重设置困难"}
                ],
                rationale="医学场景对少数类（如黑苔、绛紫舌）检出要求高，综合策略效果最佳"
            ),
            ArchitectureDecision(
                id="ADR-005",
                title="混合部署：本地推理 + 文心4.5云端诊断",
                status=DecisionStatus.APPROVED,
                date="2026-02-11",
                context="图像推理本地化保证隐私和速度，辨证诊断需要LLM能力",
                decision="分割+分类本地部署（CPU优先），诊断调用文心API（ERNIE-Speed），提供本地规则库兜底",
                consequences=[
                    "正面：图像不上传，隐私保护",
                    "正面：响应速度快（<2s）",
                    "正面：API成本低（仅结构化特征）",
                    "负面：依赖网络稳定性",
                    "负面：需要维护兜底规则库"
                ],
                alternatives=[
                    {"方案": "全云端", "优势": "维护简单", "劣势": "隐私风险、成本高"},
                    {"方案": "全本地（本地LLM）", "优势": "完全离线", "劣势": "硬件要求高、成本高"}
                ],
                rationale="医疗场景隐私敏感，混合方案在隐私、成本、效果间取得最佳平衡"
            ),
            ArchitectureDecision(
                id="ADR-006",
                title="类别不平衡应对策略三件套",
                status=DecisionStatus.APPROVED,
                date="2026-02-11",
                context="淡白舌占80.9%，部分类别样本<100，常规训练会导致模型偏向多数类",
                decision="采用三管齐下策略：Focal Loss + 分层采样 + 困难样本挖掘",
                consequences=[
                    "正面：少数类召回率预期提升30%",
                    "正面：模型泛化能力增强",
                    "负面：训练时间增加15-20%",
                    "负面：超参数调优复杂度增加"
                ],
                alternatives=[
                    {"方案": "仅过采样/欠采样", "优势": "实现简单", "劣势": "过拟合风险高"},
                    {"方案": "类别重加权", "优势": "理论简单", "劣势": "权重确定困难"}
                ],
                rationale="医学场景对少数类检出要求高（漏诊后果严重），综合策略在召回率和精度间最佳平衡"
            )
        ]

        self.decisions = core_decisions

    # ========================================================================
    # 架构决策方法
    # ========================================================================

    def create_decision(self, title: str, context: str, decision: str,
                       consequences: List[str], alternatives: List[Dict[str, str]],
                       rationale: str) -> ArchitectureDecision:
        """
        创建新的架构决策记录

        Args:
            title: 决策标题
            context: 决策背景
            decision: 决策内容
            consequences: 后果列表（正面/负面）
            alternatives: 备选方案列表
            rationale: 决策理由

        Returns:
            ArchitectureDecision: 新创建的决策记录
        """
        decision_id = f"ADR-{len(self.decisions) + 1:03d}"
        new_decision = ArchitectureDecision(
            id=decision_id,
            title=title,
            status=DecisionStatus.PROPOSED,
            date=datetime.now().strftime("%Y-%m-%d"),
            context=context,
            decision=decision,
            consequences=consequences,
            alternatives=alternatives,
            rationale=rationale
        )
        self.decisions.append(new_decision)
        return new_decision

    def review_architecture(self, module: str, description: str) -> Dict[str, Any]:
        """
        审查架构设计

        Args:
            module: 模块名称
            description: 架构描述

        Returns:
            审查结果字典
        """
        review = {
            "module": module,
            "timestamp": datetime.now().isoformat(),
            "assessments": [],
            "recommendations": [],
            "concerns": [],
            "overall_verdict": "待定"
        }

        # 架构审查检查项
        checks = {
            "scalability": "可扩展性",
            "maintainability": "可维护性",
            "performance": "性能",
            "security": "安全性",
            "testability": "可测试性"
        }

        for key, name in checks.items():
            review["assessments"].append({
                "aspect": name,
                "status": "需评估",
                "comment": f"请评估{module}的{name}"
            })

        return review

    # ========================================================================
    # 技术选型方法
    # ========================================================================

    def compare_models(self, task: str, criteria: Optional[List[str]] = None) -> TechChoice:
        """
        模型选型对比

        Args:
            task: 任务类型 (segmentation/classification)
            criteria: 评估标准列表

        Returns:
            TechChoice: 技术选型对比结果
        """
        if task not in self.MODEL_CHOICES:
            raise ValueError(f"未知任务类型: {task}")

        models = self.MODEL_CHOICES[task]
        options = []

        for model_name, specs in models.items():
            options.append({
                "name": model_name,
                "params": specs["params"],
                "accuracy": specs["accuracy"],
                "speed": specs["speed"],
                "use_case": specs["use_case"]
            })

        # 根据项目情况推荐
        if task == "segmentation":
            recommendation = "STDCNet2"
            rationale = ("基于5594张训练集规模，STDCNet2在精度(mIoU 0.90)和速度间达到最佳平衡，"
                        "配合BiSeNetV2架构，边缘分割精度满足医疗场景要求")
        else:  # classification
            recommendation = "PP-HGNetV2-B4"
            rationale = ("PP-HGNetV2-B4是飞桨专门优化的高精度模型，在多标签分类任务表现优异，"
                        "ImageNet22k预训练权重可提升5-8%精度，CPU推理速度满足要求")

        return TechChoice(
            category=f"{task}_model",
            options=options,
            recommendation=recommendation,
            rationale=rationale
        )

    def compare_loss_functions(self, task: str) -> Dict[str, Any]:
        """
        损失函数对比

        Args:
            task: 任务类型 (segmentation/classification)

        Returns:
            损失函数配置对比
        """
        if task not in self.LOSS_CONFIG:
            raise ValueError(f"未知任务类型: {task}")

        config = self.LOSS_CONFIG[task]

        result = {
            "task": task,
            "recommended_config": config,
            "implementation_notes": [],
            "tuning_tips": []
        }

        if task == "segmentation":
            result["implementation_notes"] = [
                "CrossEntropy处理像素级分类",
                "DiceLoss优化区域重叠，适合小目标",
                "BoundaryLoss强化舌体边缘，医学场景关键"
            ]
            result["tuning_tips"] = [
                "边界样本可适当增加BoundaryLoss权重",
                "训练初期CrossEntropy主导，后期增加Dice权重"
            ]
        else:  # classification
            result["implementation_notes"] = [
                "BCE作为多标签基础损失",
                "Focal Loss聚焦难分类样本（α=0.25, γ=2）",
                "AsymmetricLoss处理正负样本不平衡"
            ]
            result["tuning_tips"] = [
                "类别权重：weight_i = 1/√(count_i)",
                "Focal Loss的γ值可根据训练难度调整（1.5-2.5）",
                "监控少数类召回率，动态调整α值"
            ]

        return result

    def recommend_deployment(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        部署策略推荐

        Args:
            constraints: 约束条件字典（预算、硬件、并发量等）

        Returns:
            推荐的部署策略
        """
        budget = constraints.get("budget", "medium")
        hardware = constraints.get("hardware", "cpu")
        concurrency = constraints.get("concurrency", 10)

        recommendation = {
            "primary_strategy": "",
            "hardware_config": {},
            "optimization_actions": [],
            "expected_performance": {},
            "cost_estimate": {}
        }

        if hardware == "cpu":
            recommendation["primary_strategy"] = "CPU部署 + MKL加速"
            recommendation["hardware_config"] = {
                "cpu": "8核+ (推荐Xeon/AMD EPYC)",
                "memory": "16GB+",
                "storage": "100GB SSD"
            }
            recommendation["optimization_actions"] = [
                "启用OpenMKLDNN",
                "模型INT8量化",
                "批处理推理"
            ]
            recommendation["expected_performance"] = {
                "segmentation": "~50ms (CPU)",
                "classification": "~100ms (CPU)",
                "e2e_latency": "<2s"
            }
            recommendation["cost_estimate"] = {
                "cloud_server": "500-1500元/月",
                "maintenance": "低"
            }

        elif hardware == "gpu":
            recommendation["primary_strategy"] = "GPU加速 + TensorRT优化"
            recommendation["hardware_config"] = {
                "gpu": "NVIDIA T4 (16GB) 或更高",
                "cpu": "8核+",
                "memory": "32GB+"
            }
            recommendation["optimization_actions"] = [
                "启用TensorRT加速",
                "FP16/INT8混合精度",
                "动态batch处理"
            ]
            recommendation["expected_performance"] = {
                "segmentation": "~10ms (GPU)",
                "classification": "~20ms (GPU)",
                "e2e_latency": "<500ms"
            }
            recommendation["cost_estimate"] = {
                "cloud_gpu": "2000-5000元/月",
                "maintenance": "中"
            }

        return recommendation

    # ========================================================================
    # 风险评估方法
    # ========================================================================

    def assess_risk(self, risk_name: str, probability: float,
                   impact: str, description: str,
                   mitigation: List[str], owner: str) -> RiskAssessment:
        """
        创建风险评估

        Args:
            risk_name: 风险名称
            probability: 发生概率 (0-1)
            impact: 影响描述
            description: 风险描述
            mitigation: 缓解措施列表
            owner: 责任人

        Returns:
            RiskAssessment: 风险评估对象
        """
        # 根据概率和影响确定风险等级
        if probability > 0.7 or "紧急" in impact:
            level = RiskLevel.CRITICAL
        elif probability > 0.5 or "严重" in impact:
            level = RiskLevel.HIGH
        elif probability > 0.3:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        risk_id = f"RISK-{len(self.risks) + 1:03d}"
        risk = RiskAssessment(
            id=risk_id,
            name=risk_name,
            level=level,
            probability=probability,
            impact=impact,
            description=description,
            mitigation=mitigation,
            owner=owner
        )
        self.risks.append(risk)
        return risk

    def get_risk_matrix(self) -> Dict[str, List[RiskAssessment]]:
        """
        获取风险矩阵（按等级分类）

        Returns:
            按风险等级分类的字典
        """
        matrix = {
            "P0 - 紧急": [],
            "P1 - 高": [],
            "P2 - 中": [],
            "P3 - 低": []
        }

        for risk in self.risks:
            matrix[risk.level.value].append(risk)

        return matrix

    def analyze_project_risks(self) -> Dict[str, Any]:
        """
        分析项目整体风险

        Returns:
            项目风险分析报告
        """
        risk_analysis = {
            "summary": {
                "total_risks": len(self.risks),
                "by_level": {}
            },
            "top_risks": [],
            "recommendations": []
        }

        # 统计各等级风险数量
        for level in RiskLevel:
            count = sum(1 for r in self.risks if r.level == level)
            risk_analysis["summary"]["by_level"][level.value] = count

        # 顶级风险（高概率或高影响）
        top_risks = sorted(
            [r for r in self.risks if r.level in [RiskLevel.CRITICAL, RiskLevel.HIGH]],
            key=lambda x: x.probability,
            reverse=True
        )[:5]
        risk_analysis["top_risks"] = [
            {"id": r.id, "name": r.name, "probability": r.probability}
            for r in top_risks
        ]

        return risk_analysis

    # ========================================================================
    # 代码审查方法
    # ========================================================================

    def review_code(self, pr_id: str, module: ModuleType,
                   code_summary: str, findings: List[Dict[str, Any]]) -> CodeReview:
        """
        代码审查

        Args:
            pr_id: PR编号
            module: 模块类型
            code_summary: 代码摘要
            findings: 发现的问题列表

        Returns:
            CodeReview: 代码审查结果
        """
        # 分析发现的问题
        excellent = []
        needs_improvement = []
        must_fix = []

        for finding in findings:
            severity = finding.get("severity", "low")
            if severity == "critical":
                must_fix.append(finding)
            elif severity in ["high", "medium"]:
                needs_improvement.append(finding)
            else:
                excellent.append(finding)

        # 确定审查结果
        if must_fix:
            verdict = "必须修复后合并"
        elif needs_improvement:
            verdict = "建议修改后合并"
        else:
            verdict = "可以合并"

        review = CodeReview(
            pr_id=pr_id,
            module=module,
            reviewer="TechLead",
            date=datetime.now().strftime("%Y-%m-%d"),
            summary=code_summary,
            findings=findings,
            verdict=verdict
        )

        self.reviews.append(review)
        return review

    def generate_review_comment(self, review: CodeReview) -> str:
        """
        生成审查评论

        Args:
            review: 代码审查对象

        Returns:
            格式化的审查评论
        """
        comment_parts = [
            f"# 代码审查报告 - PR {review.pr_id}",
            f"",
            f"**模块**: {review.module.value}",
            f"**审查人**: {review.reviewer}",
            f"**日期**: {review.date}",
            f"",
            f"## 概述",
            f"{review.summary}",
            f"",
            f"## 审查结果: {review.verdict}",
            f""
        ]

        # 按严重程度分组
        critical = [f for f in review.findings if f.get("severity") == "critical"]
        high = [f for f in review.findings if f.get("severity") == "high"]
        medium = [f for f in review.findings if f.get("severity") == "medium"]
        low = [f for f in review.findings if f.get("severity") == "low"]

        if critical:
            comment_parts.extend([
                "## 必须修复 (Critical)",
                ""
            ])
            for f in critical:
                comment_parts.append(f"- **{f.get('title', 'Issue')}**: {f.get('description', '')}")

        if high:
            comment_parts.extend([
                "",
                "## 建议修复 (High)",
                ""
            ])
            for f in high:
                comment_parts.append(f"- **{f.get('title', 'Issue')}**: {f.get('description', '')}")

        comment_parts.extend([
            "",
            "## TechLead 建议",
            "",
            "审查重点关注：",
            "- 可维护性：代码结构清晰，易于理解",
            "- 可扩展性：便于后续功能添加",
            "- 性能：关注时间复杂度和资源使用",
            "- 健壮性：错误处理完善",
            ""
        ])

        return "\n".join(comment_parts)

    # ========================================================================
    # 接口协调方法
    # ========================================================================

    def define_interface(self, module_from: str, module_to: str,
                        data_format: str, endpoint: str,
                        input_schema: Dict, output_schema: Dict,
                        error_handling: str) -> InterfaceSpec:
        """
        定义模块间接口规范

        Args:
            module_from: 源模块
            module_to: 目标模块
            data_format: 数据格式
            endpoint: 接口端点
            input_schema: 输入数据结构
            output_schema: 输出数据结构
            error_handling: 错误处理方式

        Returns:
            InterfaceSpec: 接口规范对象
        """
        interface = InterfaceSpec(
            module_from=module_from,
            module_to=module_to,
            data_format=data_format,
            endpoint=endpoint,
            input_schema=input_schema,
            output_schema=output_schema,
            error_handling=error_handling,
            version="1.0"
        )
        self.interfaces.append(interface)
        return interface

    def validate_interface(self, interface: InterfaceSpec) -> Dict[str, Any]:
        """
        验证接口规范

        Args:
            interface: 接口规范对象

        Returns:
            验证结果
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }

        # 检查必需字段
        required_fields = ["module_from", "module_to", "endpoint",
                          "input_schema", "output_schema"]

        for field in required_fields:
            if not getattr(interface, field, None):
                validation_result["valid"] = False
                validation_result["errors"].append(f"缺少必需字段: {field}")

        # 检查数据格式一致性
        if interface.data_format not in ["json", "protobuf", "numpy", "image"]:
            validation_result["warnings"].append(
                f"非常规数据格式: {interface.data_format}"
            )

        # 检查错误处理
        if not interface.error_handling:
            validation_result["recommendations"].append(
                "建议添加明确的错误处理策略"
            )

        return validation_result

    # ========================================================================
    # 报告生成方法
    # ========================================================================

    def generate_decision_record(self, decision: ArchitectureDecision) -> str:
        """
        生成架构决策记录文档

        Args:
            decision: 架构决策对象

        Returns:
            Markdown格式的决策记录
        """
        lines = [
            f"# {decision.id}: {decision.title}",
            "",
            f"**状态**: {decision.status.value}",
            f"**日期**: {decision.date}",
            "",
            "## 背景",
            decision.context,
            "",
            "## 决策",
            decision.decision,
            "",
            "## 理由",
            decision.rationale,
            "",
            "## 后果",
            ""
        ]

        for consequence in decision.consequences:
            lines.append(f"- {consequence}")

        lines.extend([
            "",
            "## 备选方案",
            ""
        ])

        for alt in decision.alternatives:
            lines.append(f"### {alt['方案']}")
            lines.append(f"- 优势: {alt['优势']}")
            lines.append(f"- 劣势: {alt['劣势']}")

        return "\n".join(lines)

    def generate_status_report(self) -> str:
        """
        生成项目状态报告

        Returns:
            Markdown格式的状态报告
        """
        lines = [
            "# AI舌诊智能诊断系统 - 技术状态报告",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 项目概览",
            "",
            f"- **项目名称**: {self.PROJECT_CONTEXT['name']}",
            f"- **技术栈**: {', '.join(self.PROJECT_CONTEXT['tech_stack'].keys())}",
            f"- **数据集**: {self.PROJECT_CONTEXT['dataset']['name']} "
            f"(训练{self.PROJECT_CONTEXT['dataset']['train']}/"
            f"验证{self.PROJECT_CONTEXT['dataset']['val']}/"
            f"测试{self.PROJECT_CONTEXT['dataset']['test']})",
            "",
            "## 架构决策",
            ""
        ]

        for decision in self.decisions:
            status_icon = "[OK]" if decision.status == DecisionStatus.APPROVED else "[TODO]"
            lines.append(f"{status_icon} **{decision.id}**: {decision.title}")

        lines.extend([
            "",
            "## 风险概览",
            ""
        ])

        risk_matrix = self.get_risk_matrix()
        for level, risks in risk_matrix.items():
            if risks:
                lines.append(f"### {level} ({len(risks)})")
                for risk in risks[:3]:  # 只显示前3个
                    lines.append(f"- {risk.name} (概率: {risk.probability:.0%})")

        lines.extend([
            "",
            "## 待审查PR",
            ""
        ])

        if self.reviews:
            for review in self.reviews[-5:]:  # 最近5个
                lines.append(f"- PR {review.pr_id}: {review.verdict}")
        else:
            lines.append("- 暂无待审查PR")

        return "\n".join(lines)

    # ========================================================================
    # 知识查询方法
    # ========================================================================

    def get_recommended_config(self, module: str) -> Dict[str, Any]:
        """
        获取推荐配置

        Args:
            module: 模块名称

        Returns:
            推荐的配置字典
        """
        configs = {
            "segmentation": {
                "model": "BiSeNetV2",
                "backbone": "STDCNet2",
                "input_size": [512, 512],
                "loss": {
                    "cross_entropy": 0.5,
                    "dice": 0.3,
                    "boundary": 0.2
                },
                "optimizer": "SGD",
                "lr": 0.01,
                "batch_size": 24,
                "epochs": 80,
                "early_stopping": 10
            },
            "classification": {
                "model": "PP-HGNetV2-B4",
                "pretrained": "ImageNet22k",
                "input_size": [512, 512],
                "multi_head": {
                    "head1": ["tongue_color", "coating_color"],
                    "head2": ["tongue_shape", "coating_quality"],
                    "head3": ["special_features"]
                },
                "loss": {
                    "bce": 0.4,
                    "focal": {"alpha": 0.25, "gamma": 2},
                    "asymmetric": 0.2
                },
                "optimizer": "AdamW",
                "lr": 3e-4,
                "batch_size": 32,
                "epochs": 60
            },
            "deployment": {
                "quantization": "INT8",
                "acceleration": "OpenMKLDNN",
                "cache_ttl": 86400,
                "fallback_timeout": 10
            },
            "monitoring": {
                "p0_metrics": ["api_availability", "error_rate"],
                "p1_metrics": ["response_p99", "gpu_memory"],
                "alert_channels": ["phone", "sms", "dingtalk"]
            }
        }

        return configs.get(module, {})

    def query_knowledge(self, question: str) -> str:
        """
        查询知识库

        Args:
            question: 问题文本

        Returns:
            答案文本
        """
        question_lower = question.lower()

        # 模型选型相关
        if "模型" in question and "推荐" in question:
            return """根据项目情况（5594训练集，类别不平衡），推荐配置：

**舌体分割**：
- 主模型：BiSeNetV2 + STDCNet2
- 理由：边缘分割精准，速度满足要求，模型<10MB
- 备选：数据量>10000时考虑HRNet

**舌象分类**：
- 主模型：PP-HGNetV2-B4 (ImageNet22k预训练)
- 理由：飞桨优化，多标签表现好，CPU推理快
- 备选：移动端考虑MobileNetV3
"""

        # 损失函数相关
        if "损失" in question or "loss" in question_lower:
            return """类别不平衡场景损失函数配置：

**分割模型**：
- CrossEntropy(0.5) + DiceLoss(0.3) + BoundaryLoss(0.2)
- BoundaryLoss强化舌体边缘，医学场景关键

**分类模型**：
- BCE(0.4) + Focal Loss(α=0.25, γ=2, 权重0.4) + AsymmetricLoss(0.2)
- Focal Loss聚焦难样本，提升少数类召回
- 类别权重：weight_i = 1/√(count_i)
"""

        # 部署相关
        if "部署" in question:
            return """推荐部署策略（混合方案）：

**本地推理**：
- 硬件：8核+ CPU，16GB+ 内存
- 优化：OpenMKLDNN + INT8量化
- 性能：分割~50ms，分类~100ms

**云端诊断**：
- API：文心4.5 ERNIE-Speed（性价比最优）
- 成本：约¥0.002/次
- 兜底：本地规则库（超时10s触发）

**监控**：
- P0级：API可用性<95%，错误率>10%
- P1级：响应P99>5s
"""

        # 风险相关
        if "风险" in question:
            risk_matrix = self.get_risk_matrix()
            response = ["项目风险评估：\n"]
            for level, risks in risk_matrix.items():
                if risks:
                    response.append(f"**{level}**:")
                    for risk in risks:
                        response.append(f"- {risk.name} ({risk.probability:.0%})")
            return "\n".join(response)

        return "抱歉，我需要更多信息来回答这个问题。您可以询问：模型选型、损失函数配置、部署策略、风险评估等。"

    def to_dict(self) -> Dict[str, Any]:
        """将代理状态转换为字典"""
        return {
            "project_context": self.PROJECT_CONTEXT,
            "decisions": [
                {
                    "id": d.id,
                    "title": d.title,
                    "status": d.status.value,
                    "date": d.date
                }
                for d in self.decisions
            ],
            "risks": [
                {
                    "id": r.id,
                    "name": r.name,
                    "level": r.level.value,
                    "probability": r.probability
                }
                for r in self.risks
            ],
            "interfaces": [
                {
                    "from": i.module_from,
                    "to": i.module_to,
                    "endpoint": i.endpoint,
                    "version": i.version
                }
                for i in self.interfaces
            ]
        }


# ============================================================================
# 工具函数
# ============================================================================

def format_adr_table(agent: TechLeadAgent) -> str:
    """
    格式化架构决策表格

    Args:
        agent: TechLeadAgent实例

    Returns:
        Markdown格式的决策表格
    """
    lines = [
        "# 架构决策记录 (ADR)",
        "",
        "| ID | 决策标题 | 状态 | 日期 |",
        "|----|----------|------|------|"
    ]

    for decision in agent.decisions:
        status_icon = {
            DecisionStatus.APPROVED: "[OK]",
            DecisionStatus.PROPOSED: "[TODO]",
            DecisionStatus.REVIEWED: "[REVIEW]",
            DecisionStatus.REJECTED: "[REJECT]",
            DecisionStatus.DEPRECATED: "[OLD]"
        }[decision.status]

        lines.append(
            f"| {decision.id} | {decision.title} | {status_icon} {decision.status.value} | {decision.date} |"
        )

    return "\n".join(lines)


def format_risk_matrix(agent: TechLeadAgent) -> str:
    """
    格式化风险矩阵

    Args:
        agent: TechLeadAgent实例

    Returns:
        Markdown格式的风险矩阵
    """
    matrix = agent.get_risk_matrix()
    lines = [
        "# 风险评估矩阵",
        "",
        "```text",
        "影响"
    ]

    # 简化的ASCII矩阵
    lines.append("  高│")
    lines.append("中│")
    lines.append("低│")
    lines.append("  └──────────────────────────────▶")
    lines.append("    低        中        高    发生概率")
    lines.append("```")
    lines.append("")

    for level, risks in matrix.items():
        if risks:
            lines.extend([f"## {level}", ""])
            for risk in risks:
                lines.extend([
                    f"### {risk.name}",
                    f"- **概率**: {risk.probability:.0%}",
                    f"- **影响**: {risk.impact}",
                    f"- **缓解措施**:",
                ])
                for mitigation in risk.mitigation:
                    lines.append(f"  - {mitigation}")
                lines.append("")

    return "\n".join(lines)


# ============================================================================
# 主程序入口
# ============================================================================

def main():
    """主程序入口 - 演示TechLeadAgent的使用"""

    print("=" * 60)
    print("AI舌诊智能诊断系统 - 技术领导代理")
    print("=" * 60)
    print()

    # 初始化代理
    agent = TechLeadAgent()

    # 1. 显示项目状态
    print("【项目状态报告】")
    print("-" * 40)
    print(agent.generate_status_report())
    print()

    # 2. 模型选型建议
    print("【模型选型建议】")
    print("-" * 40)
    seg_choice = agent.compare_models("segmentation")
    print(f"分割模型推荐: {seg_choice.recommendation}")
    print(f"理由: {seg_choice.rationale}")
    print()

    # 3. 部署策略建议
    print("【部署策略建议】")
    print("-" * 40)
    deploy_rec = agent.recommend_deployment({"budget": "medium", "hardware": "cpu"})
    print(f"主策略: {deploy_rec['primary_strategy']}")
    print(f"硬件配置: {deploy_rec['hardware_config']}")
    print()

    # 4. 风险评估演示
    print("【风险评估演示】")
    print("-" * 40)
    agent.assess_risk(
        risk_name="模型过拟合",
        probability=0.6,
        impact="严重",
        description="小数据集(5594张)可能导致模型过拟合，影响泛化能力",
        mitigation=[
            "Early Stopping (patience=10)",
            "数据增强强度提升",
            "Dropout(0.2-0.3)",
            "交叉验证评估"
        ],
        owner="算法工程师"
    )
    risk_analysis = agent.analyze_project_risks()
    print(f"总风险数: {risk_analysis['summary']['total_risks']}")
    for level, count in risk_analysis['summary']['by_level'].items():
        if count > 0:
            print(f"  {level}: {count}个")
    print()

    # 5. 知识查询演示
    print("【知识查询演示】")
    print("-" * 40)
    print(agent.query_knowledge("损失函数如何配置？"))
    print()

    # 6. ADR表格
    print(format_adr_table(agent))
    print()

    print("=" * 60)
    print("TechLead Agent 初始化完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
