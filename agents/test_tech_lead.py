"""
TechLead Agent 功能验证测试
============================

验证代理的核心功能是否正常工作
"""

from tech_lead_agent import (
    TechLeadAgent,
    DecisionStatus,
    ModuleType,
    RiskLevel
)
import json


def test_initialization():
    """测试代理初始化"""
    print("=" * 60)
    print("TEST 1: Agent Initialization")
    print("=" * 60)

    agent = TechLeadAgent()

    assert len(agent.decisions) == 6, f"Expected 6 decisions, got {len(agent.decisions)}"
    print(f"[OK] Initialized with {len(agent.decisions)} architecture decisions")

    assert agent.PROJECT_CONTEXT["name"] == "AI舌诊智能诊断系统"
    print("[OK] Project context loaded correctly")

    print()


def test_model_selection():
    """测试模型选型"""
    print("=" * 60)
    print("TEST 2: Model Selection")
    print("=" * 60)

    agent = TechLeadAgent()

    # 测试分割模型选型
    seg_choice = agent.compare_models("segmentation")
    assert seg_choice.recommendation == "STDCNet2"
    print(f"[OK] Segmentation model recommendation: {seg_choice.recommendation}")

    # 测试分类模型选型
    clas_choice = agent.compare_models("classification")
    assert clas_choice.recommendation == "PP-HGNetV2-B4"
    print(f"[OK] Classification model recommendation: {clas_choice.recommendation}")

    # 测试损失函数配置
    loss_config = agent.compare_loss_functions("classification")
    assert "recommended_config" in loss_config
    print("[OK] Loss function configuration retrieved")

    print()


def test_deployment_strategy():
    """测试部署策略"""
    print("=" * 60)
    print("TEST 3: Deployment Strategy")
    print("=" * 60)

    agent = TechLeadAgent()

    # 测试CPU部署策略
    cpu_deploy = agent.recommend_deployment({
        "budget": "medium",
        "hardware": "cpu",
        "concurrency": 50
    })
    assert cpu_deploy["primary_strategy"] == "CPU部署 + MKL加速"
    print(f"[OK] CPU deployment strategy: {cpu_deploy['primary_strategy']}")

    # 测试GPU部署策略
    gpu_deploy = agent.recommend_deployment({
        "budget": "high",
        "hardware": "gpu",
        "concurrency": 100
    })
    assert "GPU" in gpu_deploy["primary_strategy"]
    print(f"[OK] GPU deployment strategy: {gpu_deploy['primary_strategy']}")

    print()


def test_risk_assessment():
    """测试风险评估"""
    print("=" * 60)
    print("TEST 4: Risk Assessment")
    print("=" * 60)

    agent = TechLeadAgent()

    # 添加测试风险
    risk = agent.assess_risk(
        risk_name="测试风险",
        probability=0.7,
        impact="严重",
        description="测试用风险评估",
        mitigation=["措施1", "措施2"],
        owner="测试负责人"
    )

    assert risk.level == RiskLevel.HIGH
    print(f"[OK] Risk level determined correctly: {risk.level.value}")

    # 测试风险矩阵
    matrix = agent.get_risk_matrix()
    total_risks = sum(len(risks) for risks in matrix.values())
    assert total_risks == 1
    print(f"[OK] Risk matrix contains {total_risks} risk(s)")

    print()


def test_architecture_decision():
    """测试架构决策创建"""
    print("=" * 60)
    print("TEST 5: Architecture Decision Creation")
    print("=" * 60)

    agent = TechLeadAgent()

    # 创建新决策
    new_decision = agent.create_decision(
        title="测试决策",
        context="测试背景",
        decision="测试决策内容",
        consequences=["正面：测试", "负面：测试"],
        alternatives=[{"方案": "方案A", "优势": "测试", "劣势": "测试"}],
        rationale="测试理由"
    )

    assert new_decision.status == DecisionStatus.PROPOSED
    assert new_decision.id == "ADR-007"
    print(f"[OK] New decision created: {new_decision.id}")
    print(f"[OK] Decision status: {new_decision.status.value}")

    # 生成ADR文档
    adr_doc = agent.generate_decision_record(new_decision)
    assert "# ADR-007: 测试决策" in adr_doc
    print("[OK] ADR document generated successfully")

    print()


def test_code_review():
    """测试代码审查"""
    print("=" * 60)
    print("TEST 6: Code Review")
    print("=" * 60)

    agent = TechLeadAgent()

    # 创建代码审查
    findings = [
        {
            "title": "测试问题",
            "severity": "critical",
            "description": "测试描述",
            "location": "test.py:1"
        }
    ]

    review = agent.review_code(
        pr_id="TEST-001",
        module=ModuleType.API,
        code_summary="测试代码",
        findings=findings
    )

    assert review.pr_id == "TEST-001"
    assert review.verdict == "必须修复后合并"
    print(f"[OK] Code review verdict: {review.verdict}")

    # 生成审查评论
    comment = agent.generate_review_comment(review)
    assert "# 代码审查报告 - PR TEST-001" in comment
    print("[OK] Review comment generated successfully")

    print()


def test_interface_coordination():
    """测试接口协调"""
    print("=" * 60)
    print("TEST 7: Interface Coordination")
    print("=" * 60)

    agent = TechLeadAgent()

    # 定义接口
    interface = agent.define_interface(
        module_from="模块A",
        module_to="模块B",
        data_format="json",
        endpoint="/api/test",
        input_schema={"test": "string"},
        output_schema={"result": "string"},
        error_handling="抛出异常"
    )

    assert interface.module_from == "模块A"
    assert interface.module_to == "模块B"
    print(f"[OK] Interface defined: {interface.module_from} -> {interface.module_to}")

    # 验证接口
    validation = agent.validate_interface(interface)
    assert validation["valid"] == True
    print("[OK] Interface validation passed")

    print()


def test_knowledge_query():
    """测试知识库查询"""
    print("=" * 60)
    print("TEST 8: Knowledge Query")
    print("=" * 60)

    agent = TechLeadAgent()

    # 测试各种查询
    questions = [
        "模型推荐",
        "损失函数",
        "部署"
    ]

    for q in questions:
        answer = agent.query_knowledge(q)
        assert answer  # 答案不应为空
        print(f"[OK] Query '{q}' returned answer ({len(answer)} chars)")

    print()


def test_config_recommendations():
    """测试配置推荐"""
    print("=" * 60)
    print("TEST 9: Config Recommendations")
    print("=" * 60)

    agent = TechLeadAgent()

    # 测试各模块配置
    modules = ["segmentation", "classification", "deployment", "monitoring"]

    for module in modules:
        config = agent.get_recommended_config(module)
        assert config  # 配置不应为空
        print(f"[OK] {module} config retrieved")

    print()


def test_status_report():
    """测试状态报告"""
    print("=" * 60)
    print("TEST 10: Status Report Generation")
    print("=" * 60)

    agent = TechLeadAgent()

    report = agent.generate_status_report()
    assert "AI舌诊智能诊断系统" in report
    assert "架构决策" in report
    print("[OK] Status report generated successfully")
    print(f"[OK] Report length: {len(report)} chars")

    print()


def test_agent_to_dict():
    """测试代理状态序列化"""
    print("=" * 60)
    print("TEST 11: Agent Serialization")
    print("=" * 60)

    agent = TechLeadAgent()

    agent_dict = agent.to_dict()
    assert "project_context" in agent_dict
    assert "decisions" in agent_dict
    assert "risks" in agent_dict
    assert "interfaces" in agent_dict

    print("[OK] Agent state serialized to dict")
    print(f"[OK] Dict keys: {list(agent_dict.keys())}")

    print()


def run_all_tests():
    """运行所有测试"""
    print("\n")
    print("#" * 60)
    print("#" + " " * 18 + "TEST SUITE" + " " * 29 + "#")
    print("#" * 60)
    print("\n")

    tests = [
        test_initialization,
        test_model_selection,
        test_deployment_strategy,
        test_risk_assessment,
        test_architecture_decision,
        test_code_review,
        test_interface_coordination,
        test_knowledge_query,
        test_config_recommendations,
        test_status_report,
        test_agent_to_dict
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"[FAILED] {test_func.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_func.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[FAILURE] {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
