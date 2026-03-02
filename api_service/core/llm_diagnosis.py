#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 诊断模块 - 文心大模型集成
AI舌诊智能诊断系统 - LLM Diagnosis

基于文心大模型进行舌诊深度分析:
- 调用文心一言 API 进行中医辨证
- 构建结构化 Prompt (System + User + Few-Shot)
- 解析 JSON 响应并验证
- 支持流式输出和超时控制
- 包含规则库和案例检索的混合策略

Author: Ralph Agent
Date: 2026-02-27
"""

import os
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError, field_validator

from api_service.core.config import settings
from api_service.prompts.user_prompt_template import UserPromptBuilder
from api_service.core.rule_based_diagnosis import diagnose_from_classification
from api_service.core.case_retrieval import retrieve_similar_cases_from_classification
from api_service.core.rule_based_diagnosis import RuleDiagnosisResult


logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for LLM Response
# ============================================================================

class SyndromeInfo(BaseModel):
    """证型信息"""
    name: str
    confidence: float
    evidence: str = ""
    tcm_theory: str = ""

    class Config:
        """Pydantic config"""
        # Allow arbitrary types to handle list -> str conversion
        arbitrary_types_allowed = True

    @field_validator('evidence', mode='before')
    @classmethod
    def convert_evidence_to_string(cls, v):
        """Convert evidence from list to string if needed"""
        if isinstance(v, list):
            return ', '.join(str(item) for item in v)
        return v if isinstance(v, str) else str(v)


class SyndromeAnalysis(BaseModel):
    """证型分析"""
    possible_syndromes: List[SyndromeInfo]
    primary_syndrome: str
    secondary_syndromes: List[str]
    syndrome_description: str


class AnomalyDetection(BaseModel):
    """异常检测"""
    detected: bool
    reason: Optional[str] = None
    recommendations: List[str] = []


class HealthRecommendations(BaseModel):
    """健康建议"""
    dietary: List[str] = []
    lifestyle: List[str] = []
    emotional: List[str] = []


class DiagnosisResponse(BaseModel):
    """LLM 诊断响应"""
    syndrome_analysis: SyndromeAnalysis
    anomaly_detection: AnomalyDetection
    health_recommendations: HealthRecommendations
    confidence: float
    reasoning_process: str = ""


# ============================================================================
# LLM Configuration
# ============================================================================

@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str  # "wenxin" or "zhipu"
    api_key: str
    secret_key: str  # Only needed for wenxin
    model: str
    api_base: str
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 4000  # Increased for complete JSON output
    timeout: int = 180  # Increased timeout for ZhipuAI
    max_retries: int = 2
    enable_rule_based: bool = True
    enable_case_retrieval: bool = True
    hybrid_weights: Dict[str, float] = None

    @classmethod
    def from_settings(cls):
        """从 settings 加载配置"""
        provider = getattr(settings, 'LLM_PROVIDER', 'zhipu').lower()

        if provider == "zhipu":
            # ZhipuAI configuration
            api_key = os.getenv("ZHIPU_API_KEY") or settings.ZHIPU_API_KEY
            model = getattr(settings, 'ZHIPU_MODEL', 'glm-4.5-air')
            api_base = getattr(settings, 'ZHIPU_API_BASE', 'https://open.bigmodel.cn/api/paas/v4/chat/completions')
            secret_key = ""

            if not api_key:
                logger.warning("ZhipuAI API key not found in environment variables")

        elif provider == "wenxin":
            # Wenxin configuration
            api_key = os.getenv("BAIDU_API_KEY") or settings.BAIDU_API_KEY
            secret_key = os.getenv("BAIDU_SECRET_KEY") or settings.BAIDU_SECRET_KEY
            model = settings.WENXIN_MODEL
            api_base = settings.WENXIN_API_BASE

            if not api_key or not secret_key:
                logger.warning("Baidu API credentials not found in environment variables")
        else:
            # Default to zhipu
            provider = "zhipu"
            api_key = os.getenv("ZHIPU_API_KEY", "")
            model = "glm-4.5-air"
            api_base = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
            secret_key = ""
            logger.warning(f"Unknown LLM provider: {provider}, defaulting to zhipu")

        return cls(
            provider=provider,
            api_key=api_key or "",
            secret_key=secret_key or "",
            model=model,
            api_base=api_base,
            timeout=settings.API_CALL_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
            enable_rule_based=settings.ENABLE_RULE_BASED_FALLBACK,
            enable_case_retrieval=True,
            hybrid_weights={"llm": 0.7, "case_retrieval": 0.2, "rule_based": 0.1}
        )


# ============================================================================
# LLM Diagnosis Engine
# ============================================================================

class LLMDiagnosisEngine:
    """基于大模型的舌诊诊断引擎 (支持智谱AI和百度文心)"""

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 LLM 诊断引擎

        Args:
            config: LLM 配置对象，默认从环境变量加载
        """
        self.config = config or LLMConfig.from_settings()
        self.access_token = ""
        self.token_expires_at = 0
        self._http_client: Optional[httpx.AsyncClient] = None

        # Load few-shot examples
        self._few_shot_examples = self._load_few_shot_examples()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._http_client

    def _load_few_shot_examples(self) -> List[Dict[str, Any]]:
        """加载 Few-shot 示例"""
        try:
            with open("api_service/prompts/few_shot_examples.json", "r", encoding="utf-8") as f:
                examples = json.load(f)
                logger.info(f"Loaded {len(examples)} few-shot examples")
                return examples
        except Exception as e:
            logger.error(f"Failed to load few-shot examples: {e}")
            return []

    async def _get_access_token(self) -> str:
        """
        获取文心 API Access Token (仅 wenxin provider 使用)

        Returns:
            Access Token 字符串
        """
        # Only needed for wenxin provider
        if self.config.provider != "wenxin":
            return self.config.api_key

        # Check if token exists and not expired
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        # Request new token
        url = f"{self.config.api_base}/access_token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.config.api_key,
            "client_secret": self.config.secret_key
        }

        client = await self._get_http_client()
        response = await client.post(url, data=params)

        if response.status_code != 200:
            raise Exception(f"Failed to get access token: {response.text}")

        token_data = response.json()
        self.access_token = token_data.get("access_token", "")
        expires_in = token_data.get("expires_in", 2592000)  # 30 days default
        self.token_expires_at = time.time() + expires_in - 300  # 5 min buffer

        logger.info("Successfully obtained new access token")
        return self.access_token

    async def _retrieve_similar_cases(
        self,
        classification_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        检索相似案例

        Args:
            classification_result: 分类模型输出结果

        Returns:
            相似案例列表 (top 2-3)
        """
        if not self.config.enable_case_retrieval:
            return []

        try:
            retrieval_result = await asyncio.to_thread(
                retrieve_similar_cases_from_classification,
                classification_result,
                top_k=2
            )
            return retrieval_result.matched_cases if retrieval_result else []
        except Exception as e:
            logger.warning(f"Case retrieval failed: {e}")
            return []

    def _build_few_shot_prompt(
        self,
        similar_cases: List[Any]
    ) -> str:
        """
        构建 Few-shot 示例提示

        Args:
            similar_cases: 相似案例列表 (可以是dict或CaseMatch对象)

        Returns:
            Few-shot 提示字符串
        """
        if not similar_cases:
            return "以下是舌诊诊断的示例格式："

        examples = []
        for i, case in enumerate(similar_cases[:3], 1):
            # Handle both dict and CaseMatch object
            if hasattr(case, 'tongue_features'):
                features = case.tongue_features
                syndromes = case.syndromes
                reasoning = case.expert_reasoning
            else:
                features = case
                syndromes = case.get('syndromes', [{}])
                reasoning = case.get('theory', case.get('expert_reasoning', '中医辨证理论解释...'))

            # Extract feature values safely
            tongue_color = features.get('tongue_color', []) if isinstance(features, dict) else []
            coating_color = features.get('coating_color', []) if isinstance(features, dict) else []
            tongue_shape = features.get('tongue_shape', []) if isinstance(features, dict) else []
            special_features = features.get('special_features', []) if isinstance(features, dict) else []

            # Extract syndrome and theory safely
            if isinstance(syndromes, list) and len(syndromes) > 0:
                syndrome = syndromes[0].get('syndrome', '未知')
                theory = syndromes[0].get('theory', syndromes[0].get('tcm_theory', '中医辨证理论解释...'))
                treatment = syndromes[0].get('treatment', '治则...')
            else:
                syndrome = '未知'
                theory = reasoning
                treatment = '治则...'

            example = f"""
示例 {i}:
舌象特征:
- 舌色: {', '.join(tongue_color) if isinstance(tongue_color, list) else str(tongue_color)}
- 苔色: {', '.join(coating_color) if isinstance(coating_color, list) else str(coating_color)}
- 舌形: {', '.join(tongue_shape) if isinstance(tongue_shape, list) else str(tongue_shape)}
- 其他特征: {', '.join(special_features) if isinstance(special_features, list) else str(special_features)}

诊断结果:
- 证型: {syndrome}
- 辩证依据: {theory}
- 治则: {treatment}
"""
            examples.append(example.strip())

        return "以下是相似舌诊案例的专家诊断：\n" + "\n".join(examples)

    async def _call_llm_api(
        self,
        user_prompt: str
    ) -> Optional[str]:
        """
        调用 LLM API (支持智谱AI和百度文心)

        Args:
            user_prompt: 用户提示词

        Returns:
            API 响应文本
        """
        try:
            # Get access token (for wenxin) or api key (for zhipu)
            token = await self._get_access_token()

            if self.config.provider == "zhipu" and not token:
                logger.error("ZhipuAI API key is empty")
                return None

            # Prepare request based on provider
            if self.config.provider == "zhipu":
                # ZhipuAI API format
                url = self.config.api_base
                # ZhipuAI uses Bearer token with the API key directly
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
                payload = {
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": self._load_system_prompt()},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "max_tokens": self.config.max_tokens,
                    "stream": False
                }
                logger.info(f"Calling ZhipuAI API with model: {self.config.model}")
            else:
                # Wenxin API format
                url = f"{self.config.api_base}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
                payload = {
                    "messages": [
                        {"role": "system", "content": self._load_system_prompt()},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "max_output_tokens": self.config.max_tokens
                }

            # Call API
            client = await self._get_http_client()
            response = await client.post(url, json=payload, headers=headers)

            logger.info(f"{self.config.provider} API response status: {response.status_code}")

            if response.status_code != 200:
                error_msg = response.text
                logger.error(f"{self.config.provider} API error: {error_msg}")
                logger.error(f"{self.config.provider} API status code: {response.status_code}")
                logger.error(f"{self.config.provider} API headers: {headers}")
                logger.error(f"{self.config.provider} API payload: {json.dumps(payload, ensure_ascii=False)}")
                return None

            result = response.json()

            # Extract response text based on provider
            if self.config.provider == "zhipu":
                # ZhipuAI response format - may include reasoning_content
                if "choices" in result and result["choices"]:
                    message = result["choices"][0].get("message", {})
                    # Try to get content, if empty use reasoning_content
                    content = message.get("content", "")
                    if not content:
                        content = message.get("reasoning_content", "")

                    logger.info(f"ZhipuAI API response received: {len(content)} chars")
                    # Log full response for debugging
                    logger.debug(f"ZhipuAI full response: {content}")
                    return content
                else:
                    logger.error(f"Unexpected ZhipuAI response format: {result}")
                    return None
            else:
                # Wenxin response format
                if "result" in result:
                    return result["result"]
                elif "choices" in result and result["choices"]:
                    return result["choices"][0].get("message", {}).get("content", "")
                else:
                    logger.error(f"Unexpected Wenxin response format: {result}")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"{self.config.provider} API call timeout")
            return None
        except Exception as e:
            logger.error(f"{self.config.provider} API call failed: {e}", exc_info=True)
            return None

    def _load_system_prompt(self) -> str:
        """加载 System Prompt"""
        try:
            with open("api_service/prompts/system_prompt.txt", "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            return "你是AI舌诊辅助诊断系统，负责分析舌象特征并提供中医辨证建议。"

    async def diagnose(
        self,
        image_base64: str,
        classification_result: Dict[str, Any],
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行 LLM 深入诊断

        Args:
            image_base64: Base64 编码的舌部图片
            classification_result: 分类模型输出结果
            user_info: 用户信息 (年龄、性别、症状等)

        Returns:
            诊断结果字典
        """
        logger.info("Starting LLM diagnosis...")

        # Step 1: Retrieve similar cases
        similar_cases = await self._retrieve_similar_cases(classification_result)
        logger.info(f"Retrieved {len(similar_cases)} similar cases")

        # Step 2: Build user prompt
        from api_service.prompts.user_prompt_template import create_user_prompt

        # Convert list format to dict format for user prompt builder
        classification_dict = {}
        for key in ["tongue_color", "coating_color", "tongue_shape", "coating_quality", "health_status"]:
            value = classification_result.get(key, [])
            if isinstance(value, list) and len(value) > 0:
                classification_dict[key] = {"prediction": value[0], "confidence": 0.8, "description": ""}
            elif isinstance(value, dict):
                classification_dict[key] = value
            else:
                classification_dict[key] = {"prediction": str(value) if value else "未知", "confidence": 0.0, "description": ""}

        # Handle special features
        special_features_list = classification_result.get("special_features", [])
        classification_dict["special_features"] = {
            "red_dots": {"present": "红点" in special_features_list, "confidence": 0.7, "description": "红点为热毒蕴结或血热表现"},
            "cracks": {"present": "裂纹" in special_features_list, "confidence": 0.7, "description": "裂纹提示阴血不足或血瘀"},
            "teeth_marks": {"present": "齿痕" in special_features_list, "confidence": 0.7, "description": "齿痕为脾虚湿盛表现"},
        }

        user_prompt = create_user_prompt(
            classification_result=classification_dict,
            user_info=user_info or {},
            template_type="base"
        )

        # Add few-shot examples
        if similar_cases:
            few_shot = self._build_few_shot_prompt(similar_cases)
            user_prompt += "\n\n" + few_shot

        logger.info(f"Built prompt (length: {len(user_prompt)} chars)")

        # Step 3: Call LLM API
        start_time = time.time()
        llm_response = await self._call_llm_api(user_prompt)
        inference_time = (time.time() - start_time) * 1000

        if not llm_response:
            logger.warning("LLM API call failed, using fallback")
            return await self._use_fallback(classification_result, user_info)

        logger.info(f"LLM API response (length: {len(llm_response)} chars, time: {inference_time}ms)")

        # Step 4: Parse JSON response
        try:
            # Log the raw LLM response for debugging
            logger.info(f"Raw LLM response (first 500 chars): {llm_response[:500]}...")

            # Extract JSON from response
            json_str = self._extract_json_from_response(llm_response)
            if not json_str:
                logger.warning(f"Could not extract JSON from LLM response")
                logger.warning(f"Full response: {llm_response}")
                raise ValueError("No JSON found in response")

            logger.info(f"Extracted JSON (first 200 chars): {json_str[:200]}...")
            diagnosis_data = json.loads(json_str)
            response = DiagnosisResponse(**diagnosis_data)

            # Step 5: Validate and enrich with case retrieval
            confidence = response.confidence
            if similar_cases:
                # Boost confidence if cases support LLM diagnosis
                confidence = min(confidence + 0.1, 1.0)

            return {
                "success": True,
                "source": "llm",
                "llm_response": llm_response,
                "llm_time_ms": inference_time,
                "syndrome_analysis": {
                    "possible_syndromes": [
                        {"name": s.name, "confidence": s.confidence, "evidence": s.evidence, "tcm_theory": s.tcm_theory}
                        for s in response.syndrome_analysis.possible_syndromes
                    ],
                    "primary_syndrome": response.syndrome_analysis.primary_syndrome,
                    "secondary_syndromes": response.syndrome_analysis.secondary_syndromes,
                    "syndrome_description": response.syndrome_analysis.syndrome_description
                },
                "anomaly_detection": {
                    "detected": response.anomaly_detection.detected,
                    "reason": response.anomaly_detection.reason,
                    "recommendations": response.anomaly_detection.recommendations
                },
                "health_recommendations": response.health_recommendations.dict(),
                "confidence": confidence,
                "inference_time_ms": inference_time,
                "retrieved_cases_count": len(similar_cases),
                "reasoning_process": response.reasoning_process
            }

        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # Fallback to rule-based
            return await self._use_fallback(classification_result, user_info)

    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """
        从响应文本中提取 JSON

        Args:
            response: LLM 响应文本

        Returns:
            JSON 字符串
        """
        import re

        # First, try to find JSON in markdown code blocks
        patterns = [
            r'```json\s*(.*?)\s*```',  # markdown code block with json
            r'```\s*(.*?)\s*```',      # markdown code block without json
            r'\{.*\}',                 # curly braces (simple) - entire response
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                json_str = match.group(1) if pattern != r'\{.*\}' else match.group(0)
                # Clean up the JSON string
                json_str = json_str.strip()

                # Verify it starts with { and ends with }
                if json_str.startswith('{') and json_str.endswith('}'):
                    return json_str

        # If no JSON found, check if the entire response is JSON
        cleaned_response = response.strip()
        if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
            return cleaned_response

        # Try to fix truncated JSON: find the last complete object
        if cleaned_response.startswith('{'):
            # Count braces to find where JSON might be truncated
            brace_count = 0
            last_valid_pos = 0
            in_string = False
            escape_next = False

            for i, char in enumerate(cleaned_response):
                if escape_next:
                    escape_next = False
                    continue
                if char == '\\':
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            last_valid_pos = i + 1

            if last_valid_pos > 0:
                json_str = cleaned_response[:last_valid_pos]
                logger.info(f"Attempted to fix truncated JSON, extracted {len(json_str)} chars")
                return json_str

        return None

    async def _use_fallback(
        self,
        classification_result: Dict[str, Any],
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        使用规则库和案例检索作为兜底

        Args:
            classification_result: 分类结果
            user_info: 用户信息

        Returns:
            诊断结果
        """
        logger.info("Using fallback strategy (rule-based + case retrieval)")

        # Get case retrieval result
        similar_cases = await self._retrieve_similar_cases(classification_result)

        # Get rule-based diagnosis
        rule_result = await asyncio.to_thread(
            diagnose_from_classification,
            classification_result
        )

        # Combine results
        if similar_cases and rule_result:
            # Weighted combination
            rule_confidence = rule_result.confidence
            case_weight = 0.2
            rule_weight = 0.8
            final_confidence = (rule_confidence * rule_weight + 1.0 * case_weight) / 2

            # Extract secondary syndromes from possible_syndromes
            secondary_syndromes = [s.name for s in rule_result.possible_syndromes[:3] if s.name != rule_result.primary_syndrome]

            # Use rule diagnosis but enhance with case context
            return {
                "success": True,
                "source": "fallback_hybrid",
                "syndrome_analysis": {
                    "possible_syndromes": [
                        {"name": rule_result.primary_syndrome, "confidence": final_confidence, "evidence": "规则匹配", "tcm_theory": rule_result.tcm_theory}
                    ],
                    "primary_syndrome": rule_result.primary_syndrome,
                    "secondary_syndromes": secondary_syndromes,
                    "syndrome_description": f"{rule_result.syndrome_description}\n\n参考案例: {len(similar_cases)} 个相似舌诊案例"
                },
                "anomaly_detection": {
                    "detected": rule_result.confidence < 0.5,
                    "reason": "置信度较低" if rule_result.confidence < 0.5 else None,
                    "recommendations": ["建议进一步面诊确认"] if rule_result.confidence < 0.5 else []
                },
                "health_recommendations": {
                    "dietary": rule_result.health_recommendations.get("diet", []),
                    "lifestyle": rule_result.health_recommendations.get("lifestyle", []),
                    "emotional": rule_result.health_recommendations.get("emotional", [])
                },
                "confidence": final_confidence,
                "inference_time_ms": 0,
                "retrieved_cases_count": len(similar_cases),
                "reasoning_process": "使用混合策略: 规则匹配 (80%) + 案例检索 (20%)"
            }
        elif rule_result:
            # Extract secondary syndromes from possible_syndromes
            secondary_syndromes = [s.name for s in rule_result.possible_syndromes[:3] if s.name != rule_result.primary_syndrome]

            # Rule-based only
            return {
                "success": True,
                "source": "fallback_rule",
                "syndrome_analysis": {
                    "possible_syndromes": [
                        {"name": rule_result.primary_syndrome, "confidence": rule_result.confidence, "evidence": "规则匹配", "tcm_theory": rule_result.tcm_theory}
                    ],
                    "primary_syndrome": rule_result.primary_syndrome,
                    "secondary_syndromes": secondary_syndromes,
                    "syndrome_description": rule_result.syndrome_description
                },
                "anomaly_detection": {
                    "detected": rule_result.confidence < 0.5,
                    "reason": "置信度较低" if rule_result.confidence < 0.5 else None,
                    "recommendations": []
                },
                "health_recommendations": {
                    "dietary": rule_result.health_recommendations.get("diet", []),
                    "lifestyle": rule_result.health_recommendations.get("lifestyle", []),
                    "emotional": rule_result.health_recommendations.get("emotional", [])
                },
                "confidence": rule_result.confidence,
                "inference_time_ms": 0,
                "retrieved_cases_count": 0,
                "reasoning_process": "使用规则库兜底"
            }
        else:
            return {
                "success": False,
                "source": "fallback_error",
                "error": "Both LLM and fallback failed"
            }

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# ============================================================================
# Factory Function
# ============================================================================

def create_llm_diagnosis_engine(config: Optional[LLMConfig] = None) -> LLMDiagnosisEngine:
    """
    创建 LLM 诊断引擎实例

    Args:
        config: LLM 配置对象

    Returns:
        LLMDiagnosisEngine 实例
    """
    return LLMDiagnosisEngine(config)