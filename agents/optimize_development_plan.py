# -*- coding: utf-8 -*-
"""
使用 Tech Lead Agent 优化开发方案
"""

import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agents'))

from agents.tech_lead_agent import TechLeadAgent, format_adr_table, format_risk_matrix


def analyze_and_optimize_plan():
    """分析并优化开发方案"""

    print("=" * 80)
    print("Tech Lead Agent - 开发方案分析与优化")
    print("=" * 80)
    print()

    # 初始化 Tech Lead 代理
    agent = TechLeadAgent()

    # ===== 第一部分：项目现状分析 =====
    print("【第一部分：项目现状分析】")
    print("-" * 60)

    status_report = agent.generate_status_report()
    print(status_report)
    print()

    # ===== 第二部分：风险分析 =====
    print("【第二部分：关键风险分析】")
    print("-" * 60)

    risks_to_assess = [
        {
            "name": "数据集类别严重不平衡",
            "probability": 0.8,
            "impact": "高",
            "description": "淡白舌占80.9%，部分类别<100样本",
            "mitigation": ["Focal Loss", "分层采样", "过采样/欠采样"],
            "owner": "ML Engineer"
        },
        {
            "name": "小数据集过拟合风险",
            "probability": 0.7,
            "impact": "高",
            "description": "5594训练样本可能不足",
            "mitigation": ["预训练权重", "Early Stopping", "数据增强"],
            "owner": "ML Engineer"
        },
        {
            "name": "模型精度不达标",
            "probability": 0.5,
            "impact": "高",
            "description": "mAP目标0.70可能难以达成",
            "mitigation": ["调整目标", "少数类优化", "模型融合"],
            "owner": "ML Engineer"
        },
        {
            "name": "API成本超预期",
            "probability": 0.4,
            "impact": "中",
            "description": "高频调用导致成本激增",
            "mitigation": ["缓存", "本地兜底", "ERNIE-Speed"],
            "owner": "Backend Developer"
        },
        {
            "name": "医疗合规风险",
            "probability": 0.6,
            "impact": "高",
            "description": "需备案、数据脱敏、等保认证",
            "mitigation": ["数据脱敏", "免责声明", "审计日志"],
            "owner": "Compliance Officer"
        }
    ]

    for risk in risks_to_assess:
        agent.assess_risk(**risk)

    risk_analysis = agent.analyze_project_risks()
    print(f"总风险数: {risk_analysis['summary']['total_risks']}")
    for level, count in risk_analysis['summary']['by_level'].items():
        if count > 0:
            print(f"  {level}: {count}个")
    print()

    # ===== 第三部分：新增架构决策 =====
    print("【第三部分：新增架构决策建议】")
    print("-" * 60)

    new_decisions = [
        {
            "title": "采用分阶段训练策略",
            "context": "类别不平衡复杂，直接训练可能不收敛",
            "decision": "分三阶段：主任务 -> 次任务 -> 全任务",
            "consequences": ["降低难度", "逐步调优", "训练时间增加"],
            "alternatives": [{"方案": "端到端", "优势": "一次完成", "劣势": "可能不收敛"}],
            "rationale": "分阶段更稳妥"
        },
        {
            "title": "实施模型融合策略",
            "context": "单模型精度可能不足",
            "decision": "Weighted Fusion融合多模型",
            "consequences": ["mAP提升3-5%", "鲁棒性增强", "推理时间增加"],
            "alternatives": [{"方案": "单模型", "优势": "快", "劣势": "精度受限"}],
            "rationale": "医学场景精度优先"
        },
        {
            "title": "建立困难样本挖掘机制",
            "context": "小数据集需充分利用样本",
            "decision": "每epoch选取loss Top 15%重采样",
            "consequences": ["困难样本充分学习", "召回率提升", "训练时间增加"],
            "alternatives": [{"方案": "随机采样", "优势": "简单", "劣势": "效率低"}],
            "rationale": "性价比最高的数据利用"
        }
    ]

    for i, dec in enumerate(new_decisions, 7):
        agent.create_decision(**dec)
        print(f"ADR-00{i}: {dec['title']}")

    print()

    # ===== 第四部分：技术配置推荐 =====
    print("【第四部分：技术配置推荐】")
    print("-" * 60)

    seg_config = agent.get_recommended_config("segmentation")
    cls_config = agent.get_recommended_config("classification")
    deploy_config = agent.get_recommended_config("deployment")

    print("\n分割模型配置:")
    print(f"  模型: {seg_config.get('model')}")
    print(f"  主干: {seg_config.get('backbone')}")
    print(f"  损失: {seg_config.get('loss')}")

    print("\n分类模型配置:")
    print(f"  模型: {cls_config.get('model')}")
    print(f"  预训练: {cls_config.get('pretrained')}")
    print(f"  多头: {cls_config.get('multi_head')}")

    print()

    # ===== 第五部分：改进清单 =====
    print("【第五部分：开发方案改进清单】")
    print("-" * 60)

    improvements = {
        "数据层(P0)": [
            "数据质量检查脚本",
            "分层采样器实现",
            "少数类专项增强",
            "困难样本挖掘工具"
        ],
        "模型层(P0)": [
            "分阶段训练配置",
            "模型融合脚本",
            "知识蒸馏工具",
            "量化剪枝流程"
        ],
        "评估层(P1)": [
            "医学指标计算",
            "少数类评估报告",
            "混淆矩阵可视化",
            "错误案例分析"
        ],
        "工程层(P1)": [
            "MLflow配置",
            "CI/CD流水线",
            "A/B测试框架",
            "监控告警配置"
        ],
        "合规层(P0)": [
            "数据脱敏脚本",
            "免责声明模板",
            "审计日志配置",
            "合规检查清单"
        ]
    }

    for layer, items in improvements.items():
        print(f"\n{layer}:")
        for item in items:
            print(f"  [ ] {item}")

    print()

    # ===== 保存分析结果 =====
    os.makedirs("outputs/reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"outputs/reports/optimization_report_{timestamp}.txt"

    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# AI舌诊系统 - Tech Lead 优化分析报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 架构决策记录\n\n")
        f.write(format_adr_table(agent))
        f.write("\n\n## 风险评估\n\n")
        f.write(format_risk_matrix(agent))
        f.write("\n\n## 改进清单\n\n")
        for layer, items in improvements.items():
            f.write(f"### {layer}\n\n")
            for item in items:
                f.write(f"- [ ] {item}\n")
            f.write("\n")

    print(f"分析报告已保存至: {report_file}")
    print()

    return agent


if __name__ == "__main__":
    analyze_and_optimize_plan()
