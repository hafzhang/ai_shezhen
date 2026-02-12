#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
历史案例检索模块

Case retrieval module for similarity-based historical case matching.
Uses feature similarity scoring to find relevant cases from the database.

Author: Ralph Agent
Date: 2026-02-12
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

from api_service.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CaseMatch:
    """案例匹配结果"""
    image_id: int
    filename: str
    similarity: float
    syndromes: List[Dict[str, Any]]
    tongue_features: Dict[str, Any]
    expert_reasoning: str
    feature_match_details: Dict[str, float]


@dataclass
class RetrievalResult:
    """检索结果"""
    total_cases: int
    matched_cases: List[CaseMatch]
    syndromes_distribution: Dict[str, int]
    avg_similarity: float
    best_match: Optional[CaseMatch]


# 特征相似度权重
FEATURE_SIMILARITY_WEIGHTS = {
    "tongue_color": 0.20,
    "coating_color": 0.20,
    "tongue_shape": 0.15,
    "coating_quality": 0.10,
    "special_features": 0.25,
    "health_status": 0.10
}


class CaseRetrieval:
    """案例检索系统"""

    def __init__(self, cases_path: Optional[str] = None):
        """初始化案例检索系统

        Args:
            cases_path: 案例数据文件路径
        """
        self.cases_path = cases_path or str(
            settings.BASE_DIR / "api_service/prompts/few_shot_examples.json"
        )
        self.cases: List[Dict[str, Any]] = []
        self._syndrome_index: Dict[str, List[int]] = defaultdict(list)
        self._feature_index: Dict[str, List[int]] = defaultdict(list)
        self._load_cases()

    def _load_cases(self):
        """加载案例数据"""
        try:
            cases_file = Path(self.cases_path)
            if cases_file.exists():
                with open(cases_file, 'r', encoding='utf-8') as f:
                    self.cases = json.load(f)

                # 构建索引
                self._build_indexes()
                logger.info(f"Loaded {len(self.cases)} cases from {self.cases_path}")
            else:
                logger.warning(f"Cases file not found: {self.cases_path}")
                self.cases = []

        except Exception as e:
            logger.error(f"Failed to load cases: {e}")
            self.cases = []

    def _build_indexes(self):
        """构建案例索引以加速检索"""
        for idx, case in enumerate(self.cases):
            # 证型索引
            for syndrome in case.get("syndromes", []):
                syndrome_name = syndrome.get("name", "")
                if syndrome_name:
                    self._syndrome_index[syndrome_name].append(idx)

            # 特征索引
            features = case.get("tongue_features", {})

            # 舌色索引
            tongue_color = features.get("tongue_color")
            if tongue_color:
                self._feature_index[f"tongue_color:{tongue_color}"].append(idx)

            # 苔色索引
            coating_color = features.get("coating_color")
            if coating_color:
                self._feature_index[f"coating_color:{coating_color}"].append(idx)

            # 舌形索引
            tongue_shape = features.get("tongue_shape")
            if tongue_shape:
                self._feature_index[f"tongue_shape:{tongue_shape}"].append(idx)

            # 特殊特征索引
            for special in features.get("special_features", []):
                self._feature_index[f"special:{special}"].append(idx)

    def retrieve_similar_cases(
        self,
        tongue_color: Optional[str] = None,
        coating_color: Optional[str] = None,
        tongue_shape: Optional[str] = None,
        coating_quality: Optional[str] = None,
        special_features: Optional[List[str]] = None,
        health_status: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.3
    ) -> RetrievalResult:
        """检索相似案例

        Args:
            tongue_color: 舌色
            coating_color: 苔色
            tongue_shape: 舌形
            coating_quality: 苔质
            special_features: 特殊特征列表
            health_status: 健康状态
            top_k: 返回前k个最相似案例
            min_similarity: 最低相似度阈值

        Returns:
            RetrievalResult: 检索结果
        """
        if not self.cases:
            return RetrievalResult(
                total_cases=0,
                matched_cases=[],
                syndromes_distribution={},
                avg_similarity=0.0,
                best_match=None
            )

        # 计算所有案例的相似度
        case_scores = []

        for case in self.cases:
            similarity, details = self._calculate_similarity(
                case,
                tongue_color,
                coating_color,
                tongue_shape,
                coating_quality,
                special_features,
                health_status
            )

            if similarity >= min_similarity:
                case_scores.append((case, similarity, details))

        # 按相似度排序
        case_scores.sort(key=lambda x: x[1], reverse=True)

        # 取前k个
        top_cases = case_scores[:top_k]

        # 构建匹配结果
        matched_cases = []
        syndromes_count = defaultdict(int)

        for case, similarity, details in top_cases:
            match = CaseMatch(
                image_id=case.get("image_id"),
                filename=case.get("filename"),
                similarity=similarity,
                syndromes=case.get("syndromes", []),
                tongue_features=case.get("tongue_features", {}),
                expert_reasoning=case.get("expert_reasoning", ""),
                feature_match_details=details
            )
            matched_cases.append(match)

            # 统计证型分布
            for syndrome in case.get("syndromes", []):
                syndromes_count[syndrome.get("name", "")] += 1

        # 计算平均相似度
        avg_similarity = sum(m.similarity for m in matched_cases) / len(matched_cases) if matched_cases else 0.0

        return RetrievalResult(
            total_cases=len(self.cases),
            matched_cases=matched_cases,
            syndromes_distribution=dict(syndromes_count),
            avg_similarity=round(avg_similarity, 3),
            best_match=matched_cases[0] if matched_cases else None
        )

    def _calculate_similarity(
        self,
        case: Dict[str, Any],
        tongue_color: Optional[str],
        coating_color: Optional[str],
        tongue_shape: Optional[str],
        coating_quality: Optional[str],
        special_features: Optional[List[str]],
        health_status: Optional[str]
    ) -> Tuple[float, Dict[str, float]]:
        """计算案例相似度

        Args:
            case: 历史案例
            tongue_color: 查询舌色
            coating_color: 查询苔色
            tongue_shape: 查询舌形
            coating_quality: 查询苔质
            special_features: 查询特殊特征
            health_status: 查询健康状态

        Returns:
            Tuple[float, Dict[str, float]]: (总体相似度, 各特征相似度)
        """
        case_features = case.get("tongue_features", {})
        feature_scores = {}

        # 舌色相似度
        tongue_color_score = self._compare_features(
            tongue_color,
            case_features.get("tongue_color")
        )
        feature_scores["tongue_color"] = tongue_color_score

        # 苔色相似度
        coating_color_score = self._compare_features(
            coating_color,
            case_features.get("coating_color")
        )
        feature_scores["coating_color"] = coating_color_score

        # 舌形相似度
        tongue_shape_score = self._compare_features(
            tongue_shape,
            case_features.get("tongue_shape")
        )
        feature_scores["tongue_shape"] = tongue_shape_score

        # 苔质相似度
        coating_quality_score = self._compare_features(
            coating_quality,
            case_features.get("coating_quality")
        )
        feature_scores["coating_quality"] = coating_quality_score

        # 特殊特征相似度
        case_specials = case_features.get("special_features", [])
        special_score = self._compare_special_features(
            special_features or [],
            case_specials
        )
        feature_scores["special_features"] = special_score

        # 健康状态相似度
        health_score = self._compare_features(
            health_status,
            case_features.get("health_status")
        )
        feature_scores["health_status"] = health_score

        # 加权计算总相似度
        total_similarity = sum(
            feature_scores[feat] * FEATURE_SIMILARITY_WEIGHTS[feat]
            for feat in FEATURE_SIMILARITY_WEIGHTS
        )

        return total_similarity, feature_scores

    def _compare_features(
        self,
        query_value: Optional[str],
        case_value: Optional[str]
    ) -> float:
        """比较单个特征

        Args:
            query_value: 查询特征值
            case_value: 案例特征值

        Returns:
            float: 相似度分数 (0-1)
        """
        if query_value is None or case_value is None:
            return 0.5  # 缺失值给予中性分数

        if query_value == case_value:
            return 1.0

        # 某些相似特征给予部分分数
        similar_pairs = {
            ("红舌", "绛紫舌"): 0.5,
            ("绛紫舌", "红舌"): 0.5,
            ("淡白舌", "红舌"): 0.2,
            ("红舌", "淡白舌"): 0.2,
        }

        return similar_pairs.get((query_value, case_value), 0.0)

    def _compare_special_features(
        self,
        query_features: List[str],
        case_features: List[str]
    ) -> float:
        """比较特殊特征

        Args:
            query_features: 查询特殊特征
            case_features: 案例特殊特征

        Returns:
            float: 相似度分数 (0-1)
        """
        if not query_features or not case_features:
            return 0.5

        # 计算交集比例
        query_set = set(query_features)
        case_set = set(case_features)

        if not query_set or not case_set:
            return 0.5

        intersection = query_set & case_set
        union = query_set | case_set

        # 使用Jaccard相似度
        jaccard = len(intersection) / len(union) if union else 0

        # 额外奖励：如果案例特征是查询特征的子集
        if case_set.issubset(query_set):
            jaccard *= 1.2

        return min(jaccard, 1.0)

    def retrieve_by_syndrome(
        self,
        syndrome_name: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """按证型检索案例

        Args:
            syndrome_name: 证型名称
            top_k: 返回案例数量

        Returns:
            List[Dict]: 匹配的案例列表
        """
        indices = self._syndrome_index.get(syndrome_name, [])
        result = [self.cases[i] for i in indices[:top_k]]
        return result

    def get_statistics(self) -> Dict[str, Any]:
        """获取案例库统计信息

        Returns:
            Dict: 统计信息
        """
        # 证型分布统计
        syndrome_counts = defaultdict(int)
        # 特征分布统计
        feature_counts = defaultdict(lambda: defaultdict(int))

        for case in self.cases:
            # 统计证型
            for syndrome in case.get("syndromes", []):
                syndrome_counts[syndrome.get("name", "")] += 1

            # 统计特征
            features = case.get("tongue_features", {})

            tc = features.get("tongue_color")
            if tc:
                feature_counts["tongue_color"][tc] += 1

            cc = features.get("coating_color")
            if cc:
                feature_counts["coating_color"][cc] += 1

            ts = features.get("tongue_shape")
            if ts:
                feature_counts["tongue_shape"][ts] += 1

        return {
            "total_cases": len(self.cases),
            "syndrome_distribution": dict(syndrome_counts),
            "feature_distribution": {
                k: dict(v) for k, v in feature_counts.items()
            },
            "indexed_syndromes": len(self._syndrome_index),
            "indexed_features": len(self._feature_index)
        }

    def export_retrieval_report(
        self,
        retrieval_result: RetrievalResult,
        output_path: Optional[str] = None
    ) -> str:
        """导出检索报告

        Args:
            retrieval_result: 检索结果
            output_path: 输出文件路径

        Returns:
            str: 报告文本
        """
        lines = []
        lines.append("=" * 60)
        lines.append("案例检索报告")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"案例库总数: {retrieval_result.total_cases}")
        lines.append(f"匹配案例数: {len(retrieval_result.matched_cases)}")
        lines.append(f"平均相似度: {retrieval_result.avg_similarity:.2%}")
        lines.append("")

        if retrieval_result.best_match:
            lines.append("最佳匹配:")
            lines.append(f"  文件名: {retrieval_result.best_match.filename}")
            lines.append(f"  相似度: {retrieval_result.best_match.similarity:.2%}")
            lines.append(f"  证型: {', '.join([s['name'] for s in retrieval_result.best_match.syndromes])}")
            lines.append("")

        if retrieval_result.matched_cases:
            lines.append("匹配案例列表:")
            for i, match in enumerate(retrieval_result.matched_cases, 1):
                lines.append(f"  {i}. {match.filename} (相似度: {match.similarity:.2%})")
                for feat, score in match.feature_match_details.items():
                    lines.append(f"     {feat}: {score:.2f}")
            lines.append("")

        if retrieval_result.syndromes_distribution:
            lines.append("证型分布:")
            for syndrome, count in sorted(
                retrieval_result.syndromes_distribution.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                lines.append(f"  {syndrome}: {count}")
            lines.append("")

        report = "\n".join(lines)

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Exported retrieval report to {output_path}")

        return report


# 全局实例
_retrieval_instance: Optional[CaseRetrieval] = None


def get_case_retrieval() -> CaseRetrieval:
    """获取案例检索实例

    Returns:
        CaseRetrieval: 案例检索实例
    """
    global _retrieval_instance
    if _retrieval_instance is None:
        _retrieval_instance = CaseRetrieval()
    return _retrieval_instance


def retrieve_similar_cases_from_classification(
    classification_result: Dict[str, Any],
    top_k: int = 5
) -> RetrievalResult:
    """从分类结果检索相似案例

    Args:
        classification_result: 分类模型输出结果
        top_k: 返回案例数量

    Returns:
        RetrievalResult: 检索结果
    """
    engine = get_case_retrieval()

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

    # 执行检索
    return engine.retrieve_similar_cases(
        tongue_color=tongue_color,
        coating_color=coating_color,
        tongue_shape=tongue_shape,
        coating_quality=coating_quality,
        special_features=special_features,
        health_status=health_status,
        top_k=top_k
    )
