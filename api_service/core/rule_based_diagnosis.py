#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本地规则库诊断模块

Rule-based diagnosis module for fallback when LLM API is unavailable.
Uses feature-to-syndrome mapping rules and confidence scoring.

Author: Ralph Agent
Date: 2026-02-12
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from api_service.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SyndromeMatch:
    """证型匹配结果"""
    name: str
    name_en: str
    pinyin: str
    confidence: float
    treatment_principle: str
    matched_features: List[str]
    missing_features: List[str]


@dataclass
class RuleDiagnosisResult:
    """规则诊断结果"""
    primary_syndrome: Optional[str]
    possible_syndromes: List[SyndromeMatch]
    confidence: float
    syndrome_description: str
    tcm_theory: str
    health_recommendations: Dict[str, Any]
    used_rules: List[str]


# 舌象特征到证型的规则映射
# 基于中医理论和训练数据统计得出
SYNDROME_RULES = {
    # 心肺气虚证
    "心肺气虚证": {
        "tongue_colors": ["淡白舌", "红舌"],
        "coating_colors": ["白苔", "黄苔"],
        "tongue_shapes": ["胖大舌", "瘦薄舌"],
        "special_features": ["齿痕", "裂纹", "红点"],
        "health_status": "非健康舌",
        "tcm_theory": "心肺气虚，血行不畅，呼吸无力。舌为心之苗，肺主气，气虚则舌淡苔薄，舌体胖大或瘦薄。",
        "treatment_principle": "补益心肺气",
        "base_confidence": 0.75
    },
    # 肾气虚证
    "肾气虚证": {
        "tongue_colors": ["淡白舌", "红舌", "绛紫舌"],
        "coating_colors": ["白苔", "花剥苔"],
        "tongue_shapes": ["胖大舌"],
        "special_features": ["齿痕", "裂纹", "红点"],
        "health_status": "非健康舌",
        "tcm_theory": "肾气不足，气化失常，舌体失养。肾主骨生髓，肾气虚则舌质淡，苔白，舌体胖大，齿痕明显。",
        "treatment_principle": "补肾益气",
        "base_confidence": 0.75
    },
    # 脾胃虚弱证
    "脾胃虚弱证": {
        "tongue_colors": ["淡白舌", "红舌", "绛紫舌"],
        "coating_colors": ["白苔"],
        "tongue_shapes": ["胖大舌", "瘦薄舌"],
        "special_features": ["齿痕", "裂纹", "红点"],
        "health_status": "非健康舌",
        "tcm_theory": "脾胃运化失司，气血生化不足。脾主运化，胃主受纳，虚弱则舌淡胖大有齿痕，苔白腻。",
        "treatment_principle": "健脾益气，和胃运湿",
        "base_confidence": 0.75
    },
    # 肝胆湿热证
    "肝胆湿热证": {
        "tongue_colors": ["红舌", "绛紫舌"],
        "coating_colors": ["白苔", "黄苔"],
        "tongue_shapes": ["胖大舌"],
        "special_features": ["裂纹", "红点"],
        "health_status": "非健康舌",
        "tcm_theory": "湿热蕴结肝胆，疏泄失常。肝胆湿热上蒸，则舌红，苔黄腻，舌边尖红。",
        "treatment_principle": "清热利湿，疏利肝胆",
        "base_confidence": 0.80
    },
    # 肝胆湿热图
    "肝胆湿热图": {
        "tongue_colors": ["红舌", "绛紫舌"],
        "coating_colors": ["白苔", "黄苔"],
        "tongue_shapes": [],
        "special_features": ["红点", "裂纹"],
        "health_status": "非健康舌",
        "tcm_theory": "肝胆湿热内蕴，舌质红，苔黄厚腻。",
        "treatment_principle": "清热利湿",
        "base_confidence": 0.70
    },
    # 肾气虚图
    "肾气虚图": {
        "tongue_colors": ["淡白舌"],
        "coating_colors": ["白苔"],
        "tongue_shapes": ["胖大舌"],
        "special_features": ["齿痕"],
        "health_status": "非健康舌",
        "tcm_theory": "肾阳不足，温煦失职，舌质淡，苔薄白，舌体胖嫩。",
        "treatment_principle": "温补肾阳",
        "base_confidence": 0.70
    },
    # 心肺气虚图
    "心肺气虚图": {
        "tongue_colors": ["淡白舌"],
        "coating_colors": ["白苔", "花剥苔"],
        "tongue_shapes": [],
        "special_features": [],
        "health_status": "非健康舌",
        "tcm_theory": "心肺两脏气虚，舌质淡白，苔薄白。",
        "treatment_principle": "补气养心",
        "base_confidence": 0.70
    }
}

# 特征权重配置
FEATURE_WEIGHTS = {
    "tongue_color": 0.25,      # 舌色权重
    "coating_color": 0.25,      # 苔色权重
    "tongue_shape": 0.15,       # 舌形权重
    "special_features": 0.25,    # 特殊特征权重
    "health_status": 0.10        # 健康状态权重
}

# 健康建议模板
HEALTH_RECOMMENDATIONS = {
    "心肺气虚证": {
        "dietary": ["宜食补气养心食物", "如红枣、桂圆、莲子、山药", "忌辛辣刺激"],
        "lifestyle": ["规律作息，避免熬夜", "适度有氧运动", "保持心情舒畅"],
        "tcm_therapy": ["可按揉内关穴、神门穴", "艾灸关元、气海"],
        "medical_consultation": "建议咨询中医师，进行益气养心调理"
    },
    "肾气虚证": {
        "dietary": ["宜温补肾阳食物", "如核桃、枸杞、韭菜、羊肉", "忌生冷寒凉"],
        "lifestyle": ["注意腰部保暖", "避免过度劳累", "节制房事"],
        "tcm_therapy": ["可按摩肾俞、命门穴", "艾灸关元、足三里"],
        "medical_consultation": "建议咨询中医师，进行补肾益气调理"
    },
    "脾胃虚弱证": {
        "dietary": ["宜健脾益气食物", "如山药、薏米、茯苓、白扁豆", "忌油腻生冷"],
        "lifestyle": ["规律饮食，细嚼慢咽", "饭后适度活动", "保持情绪稳定"],
        "tcm_therapy": ["可按揉足三里、中脘穴", "艾灸神阙、关元"],
        "medical_consultation": "建议咨询中医师，进行健脾和胃调理"
    },
    "肝胆湿热证": {
        "dietary": ["宜清热利湿食物", "如绿豆、冬瓜、苦瓜、芹菜", "忌辛辣油腻酒类"],
        "lifestyle": ["保持心情舒畅", "避免熬夜", "注意个人卫生"],
        "tcm_therapy": ["可按揉太冲、阳陵泉穴", "拔罐背部膀胱经"],
        "medical_consultation": "建议咨询中医师，进行清热利湿调理"
    },
    "default": {
        "dietary": ["保持均衡饮食", "多吃新鲜蔬菜水果", "适量饮水"],
        "lifestyle": ["规律作息", "适度运动", "保持良好心态"],
        "tcm_therapy": ["建议咨询专业中医师"],
        "medical_consultation": "如有明显不适，请及时就医"
    }
}


class RuleBasedDiagnosis:
    """基于规则的诊断系统"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化规则诊断系统

        Args:
            config_path: 规则配置文件路径（可选）
        """
        self.config_path = config_path or settings.RULE_BASED_CONFIG_PATH
        self.rules = SYNDROME_RULES
        self._load_custom_rules()

    def _load_custom_rules(self):
        """加载自定义规则配置文件"""
        config_file = Path(settings.BASE_DIR) / self.config_path
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    custom_rules = json.load(f)
                    # 合并自定义规则
                    self.rules.update(custom_rules.get("syndrome_rules", {}))
                    logger.info(f"Loaded custom rules from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load custom rules: {e}")

    def diagnose(
        self,
        tongue_color: Optional[str] = None,
        coating_color: Optional[str] = None,
        tongue_shape: Optional[str] = None,
        coating_quality: Optional[str] = None,
        special_features: Optional[List[str]] = None,
        health_status: Optional[str] = None
    ) -> RuleDiagnosisResult:
        """基于舌象特征进行规则诊断

        Args:
            tongue_color: 舌色（如"淡白舌"、"红舌"等）
            coating_color: 苔色（如"白苔"、"黄苔"等）
            tongue_shape: 舌形（如"胖大舌"、"瘦薄舌"等）
            coating_quality: 苔质（如"薄苔"、"厚苔"等）
            special_features: 特殊特征列表（如["齿痕", "裂纹"]）
            health_status: 健康状态（如"健康舌"、"非健康舌"）

        Returns:
            RuleDiagnosisResult: 规则诊断结果
        """
        # 归一化特征
        features = {
            "tongue_color": tongue_color,
            "coating_color": coating_color,
            "tongue_shape": tongue_shape,
            "coating_quality": coating_quality,
            "special_features": special_features or [],
            "health_status": health_status
        }

        # 计算每个证型的匹配分数
        syndrome_matches = []

        for syndrome_name, rule in self.rules.items():
            match_result = self._calculate_syndrome_match(
                syndrome_name, rule, features
            )
            if match_result.confidence > 0.3:  # 最低置信度阈值
                syndrome_matches.append(match_result)

        # 按置信度排序
        syndrome_matches.sort(key=lambda x: x.confidence, reverse=True)

        # 确定主要证型
        primary_syndrome = None
        if syndrome_matches:
            primary_syndrome = syndrome_matches[0].name

        # 构建诊断结果
        result = RuleDiagnosisResult(
            primary_syndrome=primary_syndrome,
            possible_syndromes=syndrome_matches[:5],  # 返回前5个候选
            confidence=syndrome_matches[0].confidence if syndrome_matches else 0.0,
            syndrome_description=self._generate_syndrome_description(syndrome_matches),
            tcm_theory=self._get_tcm_theory(syndrome_matches),
            health_recommendations=self._get_health_recommendations(primary_syndrome),
            used_rules=[m.name for m in syndrome_matches]
        )

        return result

    def _calculate_syndrome_match(
        self,
        syndrome_name: str,
        rule: Dict[str, Any],
        features: Dict[str, Any]
    ) -> SyndromeMatch:
        """计算证型匹配分数

        Args:
            syndrome_name: 证型名称
            rule: 证型规则
            features: 输入特征

        Returns:
            SyndromeMatch: 匹配结果
        """
        matched_features = []
        missing_features = []
        total_score = 0.0
        max_score = 0.0

        # 舌色匹配
        tongue_color = features.get("tongue_color")
        if tongue_color and tongue_color in rule.get("tongue_colors", []):
            matched_features.append(f"舌色:{tongue_color}")
            total_score += FEATURE_WEIGHTS["tongue_color"]
        elif tongue_color:
            missing_features.append(f"舌色不匹配")
        max_score += FEATURE_WEIGHTS["tongue_color"]

        # 苔色匹配
        coating_color = features.get("coating_color")
        if coating_color and coating_color in rule.get("coating_colors", []):
            matched_features.append(f"苔色:{coating_color}")
            total_score += FEATURE_WEIGHTS["coating_color"]
        elif coating_color:
            missing_features.append(f"苔色不匹配")
        max_score += FEATURE_WEIGHTS["coating_color"]

        # 舌形匹配
        tongue_shape = features.get("tongue_shape")
        if tongue_shape and tongue_shape in rule.get("tongue_shapes", []):
            matched_features.append(f"舌形:{tongue_shape}")
            total_score += FEATURE_WEIGHTS["tongue_shape"]
        elif tongue_shape:
            missing_features.append(f"舌形不匹配")
        max_score += FEATURE_WEIGHTS["tongue_shape"]

        # 特殊特征匹配（匹配度越高越好）
        special_features = features.get("special_features", [])
        rule_features = rule.get("special_features", [])
        if special_features and rule_features:
            feature_match_ratio = sum(
                1 for f in special_features if f in rule_features
            ) / len(special_features)
            total_score += feature_match_ratio * FEATURE_WEIGHTS["special_features"]
            matched_features.extend([f for f in special_features if f in rule_features])
        max_score += FEATURE_WEIGHTS["special_features"]

        # 健康状态匹配
        health_status = features.get("health_status")
        if health_status == rule.get("health_status"):
            total_score += FEATURE_WEIGHTS["health_status"]
        max_score += FEATURE_WEIGHTS["health_status"]

        # 计算置信度
        match_ratio = total_score / max_score if max_score > 0 else 0
        confidence = rule.get("base_confidence", 0.7) * match_ratio

        return SyndromeMatch(
            name=syndrome_name,
            name_en=rule.get("name_en", ""),
            pinyin=rule.get("pinyin", ""),
            confidence=round(confidence, 3),
            treatment_principle=rule.get("treatment_principle", ""),
            matched_features=matched_features,
            missing_features=missing_features
        )

    def _generate_syndrome_description(self, matches: List[SyndromeMatch]) -> str:
        """生成证型描述

        Args:
            matches: 证型匹配列表

        Returns:
            str: 证型描述文本
        """
        if not matches:
            return "未能识别明确的证型，建议咨询专业中医师进行面诊。"

        top_match = matches[0]

        description = f"根据舌象特征分析，最可能的证型为「{top_match.name}」"

        if top_match.matched_features:
            description += f"，匹配特征包括：{', '.join(top_match.matched_features[:3])}"

        if len(matches) > 1:
            second_match = matches[1]
            description += f"。其次可能为「{second_match.name}」（置信度{second_match.confidence:.0%}）"

        description += f"。整体置信度为{top_match.confidence:.0%}。"

        return description

    def _get_tcm_theory(self, matches: List[SyndromeMatch]) -> str:
        """获取中医理论解释

        Args:
            matches: 证型匹配列表

        Returns:
            str: 中医理论解释
        """
        if not matches:
            return "舌象特征不典型，无法给出明确的中医辨证解释。"

        top_match = matches[0]
        syndrome_name = top_match.name

        if syndrome_name in self.rules:
            return self.rules[syndrome_name].get("tcm_theory", "")

        return ""

    def _get_health_recommendations(self, syndrome: Optional[str]) -> Dict[str, Any]:
        """获取健康建议

        Args:
            syndrome: 证型名称

        Returns:
            Dict: 健康建议
        """
        recommendations = HEALTH_RECOMMENDATIONS.get(syndrome)
        if not recommendations:
            recommendations = HEALTH_RECOMMENDATIONS.get("default")

        return {
            "dietary": recommendations.get("dietary", []),
            "lifestyle": recommendations.get("lifestyle", []),
            "tcm_therapy": recommendations.get("tcm_therapy", []),
            "medical_consultation": recommendations.get("medical_consultation", "")
        }

    def get_rule_coverage(self) -> Dict[str, int]:
        """获取规则库覆盖情况

        Returns:
            Dict: 规则统计信息
        """
        total_syndromes = len(self.rules)
        total_features = sum(
            len(r.get("tongue_colors", [])) +
            len(r.get("coating_colors", [])) +
            len(r.get("tongue_shapes", [])) +
            len(r.get("special_features", []))
            for r in self.rules.values()
        )

        return {
            "total_syndromes": total_syndromes,
            "total_features": total_features,
            "average_features_per_syndrome": total_features / total_syndromes if total_syndromes > 0 else 0
        }


# 全局实例
_diagnosis_instance: Optional[RuleBasedDiagnosis] = None


def get_diagnosis_engine() -> RuleBasedDiagnosis:
    """获取诊断引擎实例

    Returns:
        RuleBasedDiagnosis: 诊断引擎实例
    """
    global _diagnosis_instance
    if _diagnosis_instance is None:
        _diagnosis_instance = RuleBasedDiagnosis()
    return _diagnosis_instance


def diagnose_from_classification(classification_result: Dict[str, Any]) -> RuleDiagnosisResult:
    """从分类结果进行诊断

    Args:
        classification_result: 分类模型输出结果

    Returns:
        RuleDiagnosisResult: 诊断结果
    """
    engine = get_diagnosis_engine()

    # 提取特征
    tongue_color = classification_result.get("tongue_color", {}).get("prediction")
    coating_color = classification_result.get("coating_color", {}).get("prediction")
    tongue_shape = classification_result.get("tongue_shape", {}).get("prediction")
    coating_quality = classification_result.get("coating_quality", {}).get("prediction")
    health_status = classification_result.get("health_status", {}).get("prediction")

    # 提取特殊特征
    special_features = []
    special_data = classification_result.get("special_features", {})

    red_dots = special_data.get("red_dots", {})
    if red_dots.get("present", False):
        special_features.append("红点")

    cracks = special_data.get("cracks", {})
    if cracks.get("present", False):
        special_features.append("裂纹")

    teeth_marks = special_data.get("teeth_marks", {})
    if teeth_marks.get("present", False):
        special_features.append("齿痕")

    # 执行诊断
    return engine.diagnose(
        tongue_color=tongue_color,
        coating_color=coating_color,
        tongue_shape=tongue_shape,
        coating_quality=coating_quality,
        special_features=special_features,
        health_status=health_status
    )
