"""
TechLead Agent 使用示例与测试
==============================

演示如何使用技术领导代理进行：
1. 架构决策制定
2. 模型选型对比
3. 风险评估与管理
4. 代码审查
5. 接口协调与规范
6. 知识库查询
"""

from tech_lead_agent import (
    TechLeadAgent,
    DecisionStatus,
    ModuleType,
    RiskLevel,
    ReviewResult
)
import json


def demo_architecture_decisions():
    """演示架构决策功能"""
    print("=" * 70)
    print("【演示1】架构决策制定")
    print("=" * 70)

    agent = TechLeadAgent()

    # 查看现有决策
    print("\n1. 现有架构决策:")
    print("-" * 50)
    for d in agent.decisions[:3]:
        print(f"  {d.id}: {d.title}")
        print(f"    状态: {d.status.value}")
        print(f"    日期: {d.date}")
        print()

    # 创建新决策
    print("2. 创建新架构决策:")
    print("-" * 50)
    new_decision = agent.create_decision(
        title="采用FastAPI作为Web服务框架",
        context="需要高性能异步API服务，支持自动文档生成",
        decision="使用FastAPI + Uvicorn构建REST API，集成Swagger文档",
        consequences=[
            "正面：异步支持，性能优异",
            "正面：自动生成OpenAPI文档",
            "正面：类型提示支持，IDE友好",
            "负面：相比Flask，生态较小"
        ],
        alternatives=[
            {"方案": "Flask", "优势": "生态成熟", "劣势": "同步框架"},
            {"方案": "Django", "优势": "功能完整", "劣势": "过于重量级"}
        ],
        rationale="FastAPI的异步特性和自动文档生成非常适合AI服务场景"
    )
    print(f"  创建决策: {new_decision.id}")
    print(f"  标题: {new_decision.title}")
    print(f"  理由: {new_decision.rationale}")

    # 生成ADR文档
    print("\n3. 生成ADR文档:")
    print("-" * 50)
    adr_doc = agent.generate_decision_record(new_decision)
    print(adr_doc[:300] + "...")


def demo_model_selection():
    """演示模型选型功能"""
    print("\n\n" + "=" * 70)
    print("【演示2】模型选型对比")
    print("=" * 70)

    agent = TechLeadAgent()

    # 分割模型选型
    print("\n1. 舌体分割模型选型:")
    print("-" * 50)
    seg_choice = agent.compare_models("segmentation")

    print(f"推荐模型: {seg_choice.recommendation}")
    print(f"\n推荐理由: {seg_choice.rationale}")
    print("\n备选方案对比:")
    for opt in seg_choice.options:
        print(f"  {opt['name']}:")
        print(f"    - 参数量: {opt['params']}")
        print(f"    - 精度: {opt['accuracy']}")
        print(f"    - 速度: {opt['speed']}")
        print(f"    - 适用: {opt['use_case']}")

    # 分类模型选型
    print("\n2. 舌象分类模型选型:")
    print("-" * 50)
    clas_choice = agent.compare_models("classification")
    print(f"推荐模型: {clas_choice.recommendation}")
    print(f"\n推荐理由: {clas_choice.rationale}")

    # 损失函数配置
    print("\n3. 分类任务损失函数配置:")
    print("-" * 50)
    loss_config = agent.compare_loss_functions("classification")
    print("推荐配置:")
    for loss_name, config in loss_config["recommended_config"].items():
        if isinstance(config, dict):
            print(f"  {loss_name}: {config}")
        else:
            print(f"  {loss_name} 权重: {config}")

    print("\n调优建议:")
    for tip in loss_config["tuning_tips"]:
        print(f"  - {tip}")


def demo_risk_assessment():
    """演示风险评估功能"""
    print("\n\n" + "=" * 70)
    print("【演示3】风险评估与管理")
    print("=" * 70)

    agent = TechLeadAgent()

    # 定义项目关键风险
    risks = [
        {
            "name": "类别不平衡导致模型偏向",
            "probability": 0.8,
            "impact": "严重 - 少数类舌象检出率低",
            "description": "淡白舌占80.9%，模型可能忽略少数类",
            "mitigation": [
                "Focal Loss (α=0.25, γ=2)",
                "分层采样保证batch内平衡",
                "少数类过采样（轻微增强）",
                "监控少数类召回率指标"
            ],
            "owner": "算法负责人"
        },
        {
            "name": "文心API不稳定",
            "probability": 0.3,
            "impact": "中等 - 诊断功能不可用",
            "description": "网络问题或API限流导致诊断失败",
            "mitigation": [
                "实现本地规则库兜底",
                "API超时设置（10s）",
                "Redis缓存诊断结果（24h）",
                "熔断机制防止连续失败"
            ],
            "owner": "后端负责人"
        },
        {
            "name": "数据标注质量不一致",
            "probability": 0.5,
            "impact": "严重 - 模型训练质量差",
            "description": "多标签标注可能存在主观差异",
            "mitigation": [
                "制定详细标注规范文档",
                "10%样本双标注一致性检查",
                "标注者培训与考核",
                "使用置信度加权训练"
            ],
            "owner": "数据负责人"
        },
        {
            "name": "推理性能不达标",
            "probability": 0.4,
            "impact": "高 - 用户体验差",
            "description": "CPU推理速度可能无法满足实时要求",
            "mitigation": [
                "模型INT8量化",
                "启用OpenMKLDNN加速",
                "批处理优化",
                "考虑GPU部署方案"
            ],
            "owner": "部署负责人"
        },
        {
            "name": "医疗合规风险",
            "probability": 0.6,
            "impact": "严重 - 法律风险",
            "description": "AI医疗建议需要合规免责",
            "mitigation": [
                "明确免责声明",
                "数据脱敏处理",
                "审计日志完整记录",
                "二类医疗器械备案咨询"
            ],
            "owner": "产品负责人"
        }
    ]

    # 添加风险
    print("\n添加项目关键风险:")
    print("-" * 50)
    for r in risks:
        risk = agent.assess_risk(**r)
        print(f"  {risk.id} {risk.level.value}: {risk.name}")

    # 风险矩阵
    print("\n风险矩阵:")
    print("-" * 50)
    matrix = agent.get_risk_matrix()
    for level, risk_list in matrix.items():
        if risk_list:
            print(f"\n{level} ({len(risk_list)}个):")
            for risk in risk_list:
                print(f"  - {risk.name} (概率: {risk.probability:.0%})")
                print(f"    责任人: {risk.owner}")

    # 风险分析
    print("\n项目风险分析:")
    print("-" * 50)
    analysis = agent.analyze_project_risks()
    print(f"总风险数: {analysis['summary']['total_risks']}")
    print("\n等级分布:")
    for level, count in analysis['summary']['by_level'].items():
        if count > 0:
            print(f"  {level}: {count}个")

    print("\n需重点关注的风险:")
    for top in analysis['top_risks']:
        print(f"  - {top['id']} {top['name']} (概率: {top['probability']:.0%})")


def demo_deployment_strategy():
    """演示部署策略推荐"""
    print("\n\n" + "=" * 70)
    print("【演示4】部署策略推荐")
    print("=" * 70)

    agent = TechLeadAgent()

    scenarios = [
        {"name": "低成本方案", "constraints": {"budget": "low", "hardware": "cpu", "concurrency": 10}},
        {"name": "标准方案", "constraints": {"budget": "medium", "hardware": "cpu", "concurrency": 50}},
        {"name": "高性能方案", "constraints": {"budget": "high", "hardware": "gpu", "concurrency": 100}},
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}:")
        print("-" * 50)
        rec = agent.recommend_deployment(**scenario["constraints"])

        print(f"策略: {rec['primary_strategy']}")
        print(f"硬件: {rec['hardware_config']}")
        print("\n优化措施:")
        for action in rec['optimization_actions']:
            print(f"  - {action}")
        print("\n预期性能:")
        for metric, value in rec['expected_performance'].items():
            print(f"  {metric}: {value}")
        print("\n成本估算:")
        for item, cost in rec['cost_estimate'].items():
            print(f"  {item}: {cost}")


def demo_code_review():
    """演示代码审查功能"""
    print("\n\n" + "=" * 70)
    print("【演示5】代码审查")
    print("=" * 70)

    agent = TechLeadAgent()

    # 模拟PR代码审查
    findings = [
        {
            "title": "缺少输入验证",
            "severity": "critical",
            "description": "API端点未验证图像文件大小和格式",
            "location": "api/routes.py:45",
            "suggestion": "添加文件大小(<=10MB)和格式(jpg/png)验证"
        },
        {
            "title": "硬编码配置值",
            "severity": "high",
            "description": "模型路径硬编码在代码中",
            "location": "models/predictor.py:12",
            "suggestion": "使用环境变量或配置文件"
        },
        {
            "title": "缺少异常处理",
            "severity": "medium",
            "description": "文心API调用未处理超时异常",
            "location": "core/llm_agent.py:78",
            "suggestion": "添加try-except和超时处理"
        },
        {
            "title": "良好的代码结构",
            "severity": "low",
            "description": "模块划分清晰，职责分离",
            "location": "整体架构",
            "suggestion": "继续保持"
        }
    ]

    review = agent.review_code(
        pr_id="PR-123",
        module=ModuleType.API,
        code_summary="添加图像上传和舌诊诊断API端点",
        findings=findings
    )

    print(f"\n审查结果: {review.verdict}")
    print(f"模块: {review.module.value}")
    print(f"审查人: {review.reviewer}")
    print(f"日期: {review.date}")

    print("\n发现的问题:")
    for f in findings:
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[f["severity"]]
        print(f"\n  {severity_icon} [{f['severity'].upper()}] {f['title']}")
        print(f"     位置: {f['location']}")
        print(f"     描述: {f['description']}")
        print(f"     建议: {f['suggestion']}")

    # 生成审查评论
    print("\n" + "=" * 70)
    print("审查评论:")
    print("=" * 70)
    comment = agent.generate_review_comment(review)
    print(comment)


def demo_interface_coordination():
    """演示接口协调功能"""
    print("\n\n" + "=" * 70)
    print("【演示6】接口协调与规范")
    print("=" * 70)

    agent = TechLeadAgent()

    # 定义关键接口
    interfaces = [
        {
            "name": "分割->分类",
            "from": "舌体分割模块",
            "to": "舌象分类模块",
            "format": "numpy",
            "endpoint": "internal://segmentation/to/classification",
            "input": {"mask": "numpy.ndarray", "bbox": "Tuple[int,4]"},
            "output": {"cropped_image": "numpy.ndarray", "metadata": "Dict"},
            "error": "抛出SegmentationError异常"
        },
        {
            "name": "分类->LLM",
            "from": "舌象分类模块",
            "to": "文心诊断模块",
            "format": "json",
            "endpoint": "internal://classification/to/llm",
            "input": {"features": "Dict[str, Any]", "confidence": "float"},
            "output": {"diagnosis": "Dict", "recommendations": "List[str]"},
            "error": "返回error字段，不抛出异常"
        },
        {
            "name": "API->分割",
            "from": "API服务层",
            "to": "舌体分割模块",
            "format": "image",
            "endpoint": "/api/v1/segment",
            "input": {"image": "bytes", "format": "jpg/png"},
            "output": {"mask_url": "str", "confidence": "float"},
            "error": "返回标准error响应"
        }
    ]

    print("\n定义模块间接口:")
    print("-" * 50)
    for iface in interfaces:
        interface = agent.define_interface(
            module_from=iface["from"],
            module_to=iface["to"],
            data_format=iface["format"],
            endpoint=iface["endpoint"],
            input_schema=iface["input"],
            output_schema=iface["output"],
            error_handling=iface["error"]
        )
        print(f"\n{iface['name']}:")
        print(f"  端点: {interface.endpoint}")
        print(f"  格式: {interface.data_format}")
        print(f"  输入: {interface.input_schema}")
        print(f"  输出: {interface.output_schema}")

    # 验证接口
    print("\n\n接口验证:")
    print("-" * 50)
    for interface in agent.interfaces:
        validation = agent.validate_interface(interface)
        status = "✅ 通过" if validation["valid"] else "❌ 失败"
        print(f"\n{interface.module_from} -> {interface.module_to}: {status}")
        if validation["warnings"]:
            print("  警告:")
            for w in validation["warnings"]:
                print(f"    - {w}")
        if validation["recommendations"]:
            print("  建议:")
            for r in validation["recommendations"]:
                print(f"    - {r}")


def demo_knowledge_query():
    """演示知识库查询"""
    print("\n\n" + "=" * 70)
    print("【演示7】知识库查询")
    print("=" * 70)

    agent = TechLeadAgent()

    questions = [
        "模型推荐是什么？",
        "损失函数如何配置？",
        "部署策略有哪些？",
        "项目风险有哪些？",
        "如何处理类别不平衡？"
    ]

    print("\n知识库查询示例:")
    print("-" * 50)
    for q in questions:
        print(f"\n问: {q}")
        print("-" * 30)
        answer = agent.query_knowledge(q)
        print(answer[:200] + "..." if len(answer) > 200 else answer)


def demo_config_recommendations():
    """演示配置推荐"""
    print("\n\n" + "=" * 70)
    print("【演示8】推荐配置查询")
    print("=" * 70)

    agent = TechLeadAgent()

    modules = ["segmentation", "classification", "deployment", "monitoring"]

    for module in modules:
        print(f"\n{module.upper()} 推荐配置:")
        print("-" * 50)
        config = agent.get_recommended_config(module)
        print(json.dumps(config, indent=2, ensure_ascii=False))


def demo_status_report():
    """演示状态报告生成"""
    print("\n\n" + "=" * 70)
    print("【演示9】项目状态报告")
    print("=" * 70)

    agent = TechLeadAgent()

    # 先添加一些示例数据
    agent.assess_risk(
        "示例风险", 0.5, "中等", "演示用",
        ["措施1", "措施2"], "负责人"
    )

    report = agent.generate_status_report()
    print(report)


def main():
    """运行所有演示"""
    print("\n" + "=" * 70)
    print(" " * 15 + "TechLead Agent 功能演示")
    print("=" * 70)
    print("\n本演示将展示技术领导代理的核心功能：")
    print("1. 架构决策制定")
    print("2. 模型选型对比")
    print("3. 风险评估与管理")
    print("4. 部署策略推荐")
    print("5. 代码审查")
    print("6. 接口协调与规范")
    print("7. 知识库查询")
    print("8. 配置推荐")
    print("9. 状态报告生成")

    # 运行各功能演示
    demo_architecture_decisions()
    demo_model_selection()
    demo_risk_assessment()
    demo_deployment_strategy()
    demo_code_review()
    demo_interface_coordination()
    demo_knowledge_query()
    demo_config_recommendations()
    demo_status_report()

    print("\n\n" + "=" * 70)
    print("演示完成！TechLead Agent 已就绪，可用于项目技术决策支持")
    print("=" * 70)


if __name__ == "__main__":
    main()
