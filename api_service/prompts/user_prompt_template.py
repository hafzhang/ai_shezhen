"""
User Prompt Template Module for Tongue Diagnosis AI System

This module provides dynamic prompt generation for the LLM diagnosis service.
It converts model classification outputs into structured user prompts for the
Wenxin API.

Usage:
    from api_service.prompts.user_prompt_template import UserPromptBuilder

    # Create a prompt from model output
    builder = UserPromptBuilder()
    prompt = builder.build_prompt(
        classification_result=model_output,
        user_info=user_metadata
    )
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from enum import Enum


class TongueColor(Enum):
    """舌色枚举"""
    DANHONG = "淡红舌"
    HONG = "红舌"
    JIANZI = "绛紫舌"
    DANBAI = "淡白舌"


class CoatingColor(Enum):
    """苔色枚举"""
    BAI = "白苔"
    HUANG = "黄苔"
    HEI = "黑苔"
    HUABO = "花剥苔"


class TongueShape(Enum):
    """舌形枚举"""
    NORMAL = "正常"
    PANGDA = "胖大舌"
    SHOUBO = "瘦薄舌"


class CoatingQuality(Enum):
    """苔质枚举"""
    BO = "薄苔"
    HOU = "厚苔"
    FU = "腐苔"
    NI = "腻苔"


class SpecialFeature(Enum):
    """特殊特征枚举"""
    RED_DOTS = "红点"
    CRACKS = "裂纹"
    TEETH_MARKS = "齿痕"


@dataclass
class ClassificationResult:
    """
    分类模型输出结果

    Attributes:
        tongue_color: 舌色预测结果 (prediction, confidence, description)
        coating_color: 苔色预测结果
        tongue_shape: 舌形预测结果
        coating_quality: 苔质预测结果
        special_features: 特殊特征预测结果
        health_status: 健康状态预测结果
        raw_scores: 原始模型输出分数
    """
    tongue_color: Dict[str, Any]
    coating_color: Dict[str, Any]
    tongue_shape: Dict[str, Any]
    coating_quality: Dict[str, Any]
    special_features: Dict[str, Any]
    health_status: Dict[str, Any]
    raw_scores: Optional[Dict[str, List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "tongue_color": self.tongue_color,
            "coating_color": self.coating_color,
            "tongue_shape": self.tongue_shape,
            "coating_quality": self.coating_quality,
            "special_features": self.special_features,
            "health_status": self.health_status,
        }


@dataclass
class UserInfo:
    """
    用户信息

    Attributes:
        age: 年龄
        gender: 性别
        symptoms: 自述症状列表
        medical_history: 既往病史
        chief_complaint: 主诉
    """
    age: Optional[int] = None
    gender: Optional[str] = None
    symptoms: List[str] = field(default_factory=list)
    medical_history: List[str] = field(default_factory=list)
    chief_complaint: Optional[str] = None


class FieldMapping:
    """
    字段映射配置

    将模型输出字段映射到中医术语和描述
    """

    # 舌色映射
    TONGUE_COLOR_MAPPING = {
        0: ("淡红舌", "舌色淡红，气血调和，多为正常或轻症"),
        1: ("红舌", "舌色红，热证表现，实热或虚热"),
        2: ("绛紫舌", "舌色绛紫，热盛或气血瘀滞"),
        3: ("淡白舌", "舌色淡白，虚证表现，气血两虚或阳虚"),
    }

    # 苔色映射
    COATING_COLOR_MAPPING = {
        0: ("白苔", "苔色白，寒证、表证或虚寒"),
        1: ("黄苔", "苔色黄，里证、热证或脾胃湿热"),
        2: ("黑苔", "苔色黑，里寒极盛或肾气虚衰"),
        3: ("花剥苔", "苔色花剥，胃气阴伤或肝肾阴虚"),
    }

    # 舌形映射
    TONGUE_SHAPE_MAPPING = {
        0: ("正常", "舌体适中，无异常"),
        1: ("胖大舌", "舌体胖大，脾虚、湿盛或阳虚水肿"),
        2: ("瘦薄舌", "舌体瘦薄，气血两虚或阴虚火旺"),
    }

    # 苔质映射
    COATING_QUALITY_MAPPING = {
        0: ("薄苔", "苔质薄，胃气充盈或表证"),
        1: ("厚苔", "苔质厚，里证、湿盛或食积"),
        2: ("腐苔", "苔质腐，胃气蕴热或食积"),
        3: ("腻苔", "苔质腻，湿热困脾或湿热"),
    }

    # 特征名称映射
    FEATURE_NAME_MAPPING = {
        "red_dots": "红点",
        "cracks": "裂纹",
        "teeth_marks": "齿痕",
    }

    # 特征描述映射
    FEATURE_DESCRIPTION_MAPPING = {
        "red_dots": "红点为热毒蕴结或血热表现",
        "cracks": "裂纹提示阴血不足或血瘀",
        "teeth_marks": "齿痕为脾虚湿盛表现",
    }

    @classmethod
    def get_tongue_color(cls, index: int) -> tuple:
        """获取舌色信息"""
        return cls.TONGUE_COLOR_MAPPING.get(index, ("未知", "未知舌色"))

    @classmethod
    def get_coating_color(cls, index: int) -> tuple:
        """获取苔色信息"""
        return cls.COATING_COLOR_MAPPING.get(index, ("未知", "未知苔色"))

    @classmethod
    def get_tongue_shape(cls, index: int) -> tuple:
        """获取舌形信息"""
        return cls.TONGUE_SHAPE_MAPPING.get(index, ("未知", "未知舌形"))

    @classmethod
    def get_coating_quality(cls, index: int) -> tuple:
        """获取苔质信息"""
        return cls.COATING_QUALITY_MAPPING.get(index, ("未知", "未知苔质"))


class PromptTemplates:
    """
    提示词模板集合

    提供多种场景的提示词模板
    """

    # 基础用户提示词模板
    BASE_TEMPLATE = """请根据以下舌象AI模型分析结果，提供专业的中医舌诊诊断建议：

## 舌象特征分析

### 舌色
- 预测结果: {tongue_color_prediction}
- 置信度: {tongue_color_confidence:.2%}
- 描述: {tongue_color_description}

### 苔色
- 预测结果: {coating_color_prediction}
- 置信度: {coating_color_confidence:.2%}
- 描述: {coating_color_description}

### 舌形
- 预测结果: {tongue_shape_prediction}
- 置信度: {tongue_shape_confidence:.2%}
- 描述: {tongue_shape_description}

### 苔质
- 预测结果: {coating_quality_prediction}
- 置信度: {coating_quality_confidence:.2%}
- 描述: {coating_quality_description}

### 特殊特征
{special_features_section}

### 整体健康状态
- 预测结果: {health_status_prediction}
- 置信度: {health_status_confidence:.2%}
- 描述: {health_status_description}

## 用户信息
{user_info_section}

## 分析要求
请基于以上舌象特征，结合中医舌诊理论，提供以下内容：
1. 舌象特征的中医辨证分析
2. 可能的证型判断及置信度
3. 健康调理建议（饮食、生活、中医理疗）
4. 是否建议就医及原因
5. 整体置信度分析及不确定性因素

请严格按照System Prompt中定义的JSON格式输出结果。"""

    # 简化版模板（用于低置信度或异常情况）
    SIMPLIFIED_TEMPLATE = """舌象图像分析结果如下，请注意可能存在特征提取不确定的情况：

## 舌象特征分析

### 舌色
- 预测结果: {tongue_color_prediction}
- 置信度: {tongue_color_confidence:.2%}

### 苔色
- 预测结果: {coating_color_prediction}
- 置信度: {coating_color_confidence:.2%}

### 舌形
- 预测结果: {tongue_shape_prediction}
- 置信度: {tongue_shape_confidence:.2%}

### 苔质
- 预测结果: {coating_quality_prediction}
- 置信度: {coating_quality_confidence:.2%}

### 特殊特征
{special_features_section}

### 整体健康状态
- 预测结果: {health_status_prediction}
- 置信度: {health_status_confidence:.2%}

## 注意事项
部分特征的置信度较低，请谨慎分析。如有异常，请在anomaly_detection字段中标记。

请严格按照System Prompt中定义的JSON格式输出结果，特别要注意异常检测规则的触发。"""

    # 健康舌专用模板
    HEALTHY_TEMPLATE = """舌象分析结果显示为健康舌象，请提供健康维持建议：

## 舌象特征分析

### 舌色
- 预测结果: {tongue_color_prediction}
- 置信度: {tongue_color_confidence:.2%}

### 苔色
- 预测结果: {coating_color_prediction}
- 置信度: {coating_color_confidence:.2%}

### 舌形
- 预测结果: {tongue_shape_prediction}
- 置信度: {tongue_shape_confidence:.2%}

### 苔质
- 预测结果: {coating_quality_prediction}
- 置信度: {coating_quality_confidence:.2%}

### 特殊特征
{special_features_section}

### 整体健康状态
- 预测结果: 健康舌
- 置信度: {health_status_confidence:.2%}
- 描述: 舌象整体正常，无明显病理特征

## 用户信息
{user_info_section}

## 分析要求
请确认舌象确实为健康舌象，并提供以下内容：
1. 健康维持建议（饮食、生活、中医理疗）
2. 预防性保健建议
3. 无需就医的说明

请严格按照System Prompt中定义的JSON格式输出结果，syndrome_analysis应为空或null。"""


class UserPromptBuilder:
    """
    用户提示词构建器

    负责将分类模型输出转换为结构化的用户提示词
    """

    def __init__(self, template_type: str = "base"):
        """
        初始化构建器

        Args:
            template_type: 模板类型 ("base", "simplified", "healthy")
        """
        self.template_type = template_type
        self.field_mapping = FieldMapping()

    def build_prompt(
        self,
        classification_result: ClassificationResult,
        user_info: Optional[UserInfo] = None,
    ) -> str:
        """
        构建用户提示词

        Args:
            classification_result: 分类模型输出结果
            user_info: 用户信息（可选）

        Returns:
            格式化的用户提示词字符串
        """
        # 选择模板
        template = self._select_template(classification_result)

        # 提取特征信息
        tongue_color = self._extract_feature_info(
            classification_result.tongue_color, "tongue_color"
        )
        coating_color = self._extract_feature_info(
            classification_result.coating_color, "coating_color"
        )
        tongue_shape = self._extract_feature_info(
            classification_result.tongue_shape, "tongue_shape"
        )
        coating_quality = self._extract_feature_info(
            classification_result.coating_quality, "coating_quality"
        )
        health_status = self._extract_feature_info(
            classification_result.health_status, "health_status"
        )

        # 构建特殊特征部分
        special_features_section = self._build_special_features_section(
            classification_result.special_features
        )

        # 构建用户信息部分
        user_info_section = self._build_user_info_section(user_info)

        # 填充模板
        prompt = template.format(
            tongue_color_prediction=tongue_color["prediction"],
            tongue_color_confidence=tongue_color["confidence"],
            tongue_color_description=tongue_color["description"],
            coating_color_prediction=coating_color["prediction"],
            coating_color_confidence=coating_color["confidence"],
            coating_color_description=coating_color["description"],
            tongue_shape_prediction=tongue_shape["prediction"],
            tongue_shape_confidence=tongue_shape["confidence"],
            tongue_shape_description=tongue_shape["description"],
            coating_quality_prediction=coating_quality["prediction"],
            coating_quality_confidence=coating_quality["confidence"],
            coating_quality_description=coating_quality["description"],
            special_features_section=special_features_section,
            health_status_prediction=health_status["prediction"],
            health_status_confidence=health_status["confidence"],
            health_status_description=health_status["description"],
            user_info_section=user_info_section,
        )

        return prompt

    def _select_template(self, result: ClassificationResult) -> str:
        """根据分类结果选择合适的模板"""
        # 如果指定了非base模板类型，直接使用指定模板
        if self.template_type == "healthy":
            return PromptTemplates.HEALTHY_TEMPLATE
        elif self.template_type == "simplified":
            return PromptTemplates.SIMPLIFIED_TEMPLATE

        # 对于 "base" 模板类型或默认情况，根据分类结果自动选择模板
        # 检查是否为健康舌
        is_healthy = (
            result.health_status.get("prediction", "") == "健康舌"
            and result.health_status.get("confidence", 0) > 0.7
        )

        # 检查是否有低置信度特征
        has_low_confidence = any(
            f.get("confidence", 1.0) < 0.5
            for f in [
                result.tongue_color,
                result.coating_color,
                result.tongue_shape,
                result.coating_quality,
            ]
        )

        if is_healthy:
            return PromptTemplates.HEALTHY_TEMPLATE
        elif has_low_confidence:
            return PromptTemplates.SIMPLIFIED_TEMPLATE
        else:
            return PromptTemplates.BASE_TEMPLATE

    def _extract_feature_info(
        self, feature_dict: Dict[str, Any], feature_type: str
    ) -> Dict[str, Any]:
        """
        提取特征信息并补充描述

        Args:
            feature_dict: 特征字典
            feature_type: 特征类型

        Returns:
            包含prediction, confidence, description的字典
        """
        prediction = feature_dict.get("prediction", "未知")
        confidence = feature_dict.get("confidence", 0.0)
        description = feature_dict.get("description", "")

        # 如果没有描述，使用默认描述
        if not description:
            description = self._get_default_description(feature_type, prediction)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "description": description,
        }

    def _get_default_description(self, feature_type: str, prediction: str) -> str:
        """获取特征的默认描述"""
        descriptions = {
            "tongue_color": {
                "淡红舌": "舌色淡红，气血调和",
                "红舌": "舌色红，热证表现",
                "绛紫舌": "舌色绛紫，热盛或血瘀",
                "淡白舌": "舌色淡白，虚证表现",
            },
            "coating_color": {
                "白苔": "苔色白，寒证或表证",
                "黄苔": "苔色黄，里热证",
                "黑苔": "苔色黑，里寒或肾虚",
                "花剥苔": "苔色花剥，胃阴虚",
            },
            "tongue_shape": {
                "正常": "舌体适中，无异常",
                "胖大舌": "舌体胖大，脾虚湿盛",
                "瘦薄舌": "舌体瘦薄，气血两虚",
            },
            "coating_quality": {
                "薄苔": "苔质薄，胃气充盈",
                "厚苔": "苔质厚，里湿盛",
                "腐苔": "苔质腐，食积或蕴热",
                "腻苔": "苔质腻，湿热困脾",
            },
            "health_status": {
                "健康舌": "舌象正常，无明显病理特征",
                "不健康舌": "舌象显示异常征象",
            },
        }

        return descriptions.get(feature_type, {}).get(prediction, "")

    def _build_special_features_section(self, features: Dict[str, Any]) -> str:
        """构建特殊特征部分"""
        lines = []

        for feature_key, feature_data in features.items():
            feature_name = FieldMapping.FEATURE_NAME_MAPPING.get(
                feature_key, feature_key
            )
            present = feature_data.get("present", False)
            confidence = feature_data.get("confidence", 0.0)
            description = feature_data.get("description", "")

            if present:
                lines.append(
                    f"- {feature_name}: 存在 (置信度: {confidence:.2%}) - {description}"
                )
            else:
                lines.append(
                    f"- {feature_name}: 无明显表现 (置信度: {confidence:.2%})"
                )

        return "\n".join(lines) if lines else "- 无明显特殊特征"

    def _build_user_info_section(self, user_info: Optional[UserInfo]) -> str:
        """构建用户信息部分"""
        if user_info is None:
            return "未提供用户信息"

        lines = []

        if user_info.age is not None:
            lines.append(f"- 年龄: {user_info.age}岁")

        if user_info.gender:
            lines.append(f"- 性别: {user_info.gender}")

        if user_info.chief_complaint:
            lines.append(f"- 主诉: {user_info.chief_complaint}")

        if user_info.symptoms:
            lines.append(f"- 症状: {', '.join(user_info.symptoms)}")

        if user_info.medical_history:
            lines.append(f"- 既往史: {', '.join(user_info.medical_history)}")

        return "\n".join(lines) if lines else "未提供详细用户信息"


def create_user_prompt(
    classification_result: Dict[str, Any],
    user_info: Optional[Dict[str, Any]] = None,
    template_type: str = "base",
) -> str:
    """
    创建用户提示词的便捷函数

    Args:
        classification_result: 分类模型输出结果（字典格式）
        user_info: 用户信息（字典格式，可选）
        template_type: 模板类型

    Returns:
        格式化的用户提示词字符串

    Example:
        >>> model_output = {
        ...     "tongue_color": {"prediction": "淡红舌", "confidence": 0.92, "description": "..."},
        ...     "coating_color": {"prediction": "白苔", "confidence": 0.88, "description": "..."},
        ...     "tongue_shape": {"prediction": "正常", "confidence": 0.90, "description": "..."},
        ...     "coating_quality": {"prediction": "薄苔", "confidence": 0.85, "description": "..."},
        ...     "special_features": {
        ...         "red_dots": {"present": False, "confidence": 0.0, "description": "..."},
        ...         "cracks": {"present": False, "confidence": 0.0, "description": "..."},
        ...         "teeth_marks": {"present": False, "confidence": 0.0, "description": "..."},
        ...     },
        ...     "health_status": {"prediction": "健康舌", "confidence": 0.91, "description": "..."},
        ... }
        >>> prompt = create_user_prompt(model_output)
        >>> print(prompt)
    """
    # 转换为ClassificationResult对象
    result = ClassificationResult(
        tongue_color=classification_result.get("tongue_color", {}),
        coating_color=classification_result.get("coating_color", {}),
        tongue_shape=classification_result.get("tongue_shape", {}),
        coating_quality=classification_result.get("coating_quality", {}),
        special_features=classification_result.get("special_features", {}),
        health_status=classification_result.get("health_status", {}),
        raw_scores=classification_result.get("raw_scores"),
    )

    # 转换用户信息
    info = None
    if user_info:
        info = UserInfo(
            age=user_info.get("age"),
            gender=user_info.get("gender"),
            symptoms=user_info.get("symptoms", []),
            medical_history=user_info.get("medical_history", []),
            chief_complaint=user_info.get("chief_complaint"),
        )

    # 构建提示词
    builder = UserPromptBuilder(template_type=template_type)
    return builder.build_prompt(result, info)


# 导出的便捷函数
__all__ = [
    "UserPromptBuilder",
    "ClassificationResult",
    "UserInfo",
    "FieldMapping",
    "PromptTemplates",
    "create_user_prompt",
    "TongueColor",
    "CoatingColor",
    "TongueShape",
    "CoatingQuality",
    "SpecialFeature",
]
