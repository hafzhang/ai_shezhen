#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG流水线模块
RAG Pipeline Module
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """RAG上下文"""
    query: str
    retrieved_documents: List[Dict[str, Any]]
    combined_context: str
    metadata: Dict[str, Any]


class RAGPipeline:
    """RAG流水线"""

    def __init__(self, vector_db_manager=None, llm_client=None):
        """
        初始化RAG流水线

        Args:
            vector_db_manager: 向量数据库管理器
            llm_client: LLM客户端
        """
        from api_service.core.rag_config import rag_settings
        from api_service.core.vector_db import get_vector_db_manager

        self.config = rag_settings
        self.vector_db = vector_db_manager or get_vector_db_manager()
        self.llm_client = llm_client

        # 初始化LLM客户端
        if self.llm_client is None:
            self._init_llm_client()

    def _init_llm_client(self):
        """初始化LLM客户端"""
        provider = self.config.RAG_LLM_PROVIDER

        if provider == "zhipu":
            self._init_zhipu_client()
        elif provider == "openai":
            self._init_openai_client()
        elif provider == "anthropic":
            self._init_anthropic_client()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def _init_zhipu_client(self):
        """初始化智谱AI客户端"""
        import os
        import httpx

        api_key = os.getenv("ZHIPU_API_KEY")
        if not api_key:
            logger.warning("ZHIPU_API_KEY not set, using mock LLM")
            self.llm_client = None
            return

        self.llm_client = {
            'provider': 'zhipu',
            'api_key': api_key,
            'model': self.config.RAG_LLM_MODEL,
            'api_url': "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        }

        logger.info("ZhipuAI LLM client initialized")

    def _init_openai_client(self):
        """初始化OpenAI客户端"""
        import os

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, using mock LLM")
            self.llm_client = None
            return

        try:
            from openai import OpenAI

            self.llm_client = {
                'provider': 'openai',
                'client': OpenAI(api_key=api_key),
                'model': self.config.RAG_LLM_MODEL
            }

            logger.info("OpenAI LLM client initialized")

        except ImportError:
            logger.warning("OpenAI not installed, using mock LLM")
            self.llm_client = None

    def _init_anthropic_client(self):
        """初始化Anthropic客户端"""
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, using mock LLM")
            self.llm_client = None
            return

        try:
            from anthropic import Anthropic

            self.llm_client = {
                'provider': 'anthropic',
                'client': Anthropic(api_key=api_key),
                'model': self.config.RAG_LLM_MODEL
            }

            logger.info("Anthropic LLM client initialized")

        except ImportError:
            logger.warning("Anthropic not installed, using mock LLM")
            self.llm_client = None

    def retrieve_context(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> RAGContext:
        """
        检索相关上下文

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤条件

        Returns:
            RAG上下文对象
        """
        try:
            top_k = top_k or self.config.TOP_K_RESULTS

            # 执行向量搜索
            retrieved_docs = self.vector_db.search(
                query=query,
                top_k=top_k,
                filters=filters,
                min_score=self.config.MIN_SIMILARITY_SCORE
            )

            # 组合上下文
            combined_context = self._combine_documents(retrieved_docs)

            # 提取元数据
            metadata = {
                'query': query,
                'retrieved_count': len(retrieved_docs),
                'total_retrieved': top_k,
                'min_similarity': min([doc['similarity'] for doc in retrieved_docs]) if retrieved_docs else 0.0,
                'max_similarity': max([doc['similarity'] for doc in retrieved_docs]) if retrieved_docs else 0.0
            }

            return RAGContext(
                query=query,
                retrieved_documents=retrieved_docs,
                combined_context=combined_context,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return RAGContext(
                query=query,
                retrieved_documents=[],
                combined_context="",
                metadata={'error': str(e)}
            )

    def _combine_documents(self, documents: List[Dict[str, Any]]) -> str:
        """
        组合检索到的文档

        Args:
            documents: 文档列表

        Returns:
            组合后的上下文文本
        """
        if not documents:
            return ""

        # 按相似度排序
        sorted_docs = sorted(documents, key=lambda x: x['similarity'], reverse=True)

        # 组合文档
        context_parts = []
        for i, doc in enumerate(sorted_docs, 1):
            part = f"[参考文档 {i}] 相似度:{doc['similarity']:.2%}\n"
            part += f"类别: {doc['metadata'].get('category', '未知')}\n"
            part += f"内容: {doc['document']}\n"
            context_parts.append(part)

        return "\n\n".join(context_parts)

    def generate_response(
        self,
        query: str,
        context: RAGContext,
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None
    ) -> str:
        """
        生成响应

        Args:
            query: 用户查询
            context: RAG上下文
            system_prompt: 系统提示词
            user_prompt_template: 用户提示词模板

        Returns:
            生成的响应文本
        """
        try:
            # 构建完整的提示词
            full_prompt = self._build_prompt(query, context, system_prompt, user_prompt_template)

            # 调用LLM
            if self.llm_client:
                response = self._call_llm(full_prompt)
            else:
                response = self._generate_mock_response(query, context)

            return response

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return f"生成响应时出错: {str(e)}"

    def _build_prompt(
        self,
        query: str,
        context: RAGContext,
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None
    ) -> str:
        """
        构建完整提示词

        Args:
            query: 用户查询
            context: RAG上下文
            system_prompt: 系统提示词
            user_prompt_template: 用户提示词模板

        Returns:
            完整的提示词
        """
        # 默认系统提示词
        if system_prompt is None:
            system_prompt = """你是一位专业的中医舌诊专家，具有深厚的中医理论基础和丰富的临床经验。
你的职责是：
1. 基于提供的舌象特征和相关中医知识，进行专业的舌诊分析
2. 识别患者的证型，提供中医理论解释
3. 给出个性化的养生建议，包括饮食、生活方式和情绪调节
4. 使用专业但易懂的语言，便于患者理解和遵循
5. 严格按照JSON格式输出分析结果

重要提醒：
- 不要进行确诊，仅提供中医调理建议
- 建议如有明显症状应及时就医
- 保持客观中立的态度"""

        # 默认用户提示词模板
        if user_prompt_template is None:
            user_prompt_template = """# 舌诊分析请求

## 用户查询
{query}

## 参考知识库
{context}

## 分析要求
请基于以上舌象特征和参考知识库，进行专业的舌诊分析，并严格按照以下JSON格式输出：

```json
{{
  "tongue_analysis": {{
    "tongue_color": {{
      "observation": "观察到的舌色特征",
      "tcm_interpretation": "中医理论解释",
      "clinical_significance": "临床意义"
    }},
    "coating_analysis": {{
      "observation": "观察到的苔色特征",
      "tcm_interpretation": "中医理论解释",
      "clinical_significance": "临床意义"
    }},
    "tongue_shape_analysis": {{
      "observation": "观察到的舌形特征",
      "tcm_interpretation": "中医理论解释",
      "clinical_significance": "临床意义"
    }},
    "special_features_analysis": {{
      "observations": ["特殊特征1", "特殊特征2"],
      "tcm_interpretation": "综合中医理论解释",
      "clinical_significance": "综合临床意义"
    }}
  }},
  "syndrome_diagnosis": {{
    "primary_syndrome": "主要证型",
    "secondary_syndromes": ["次要证型1", "次要证型2"],
    "confidence": 0.85,
    "diagnosis_basis": "诊断依据",
    "tcm_theory_explanation": "详细中医理论解释"
  }},
  "health_recommendations": {{
    "dietary_guidance": {{
      "principle": "饮食调理原则",
      "recommended_foods": ["推荐食物1", "推荐食物2"],
      "avoid_foods": ["禁忌食物1", "禁忌食物2"],
      "seasonal_advice": "季节性建议"
    }},
    "lifestyle_guidance": {{
      "exercise": ["运动建议1", "运动建议2"],
      "sleep": "睡眠作息建议",
      "daily_routine": "日常生活建议",
      "environment": "生活环境建议"
    }},
    "emotional_guidance": {{
      "mood_regulation": "情绪调节建议",
      "stress_management": "压力管理方法",
      "mindfulness": "正念练习建议"
    }}
  }},
  "risk_assessment": {{
    "current_health_status": "当前健康状态评估",
    "potential_risks": ["潜在风险1", "潜在风险2"],
    "recommendations": ["建议1", "建议2"]
  }},
  "references_used": [
    "参考的知识来源1",
    "参考的知识来源2"
  ],
  "medical_disclaimer": "重要：本分析仅提供中医调理建议，不能替代专业医疗诊断。如有明显不适症状，请及时就医。"
}}
```"""

        # 构建用户提示词
        user_prompt = user_prompt_template.format(
            query=query,
            context=context.combined_context
        )

        return f"System: {system_prompt}\n\nUser: {user_prompt}"

    def _call_llm(self, prompt: str) -> str:
        """
        调用LLM生成响应

        Args:
            prompt: 完整的提示词

        Returns:
            LLM响应文本
        """
        try:
            provider = self.llm_client['provider']

            if provider == "zhipu":
                return self._call_zhipu_llm(prompt)
            elif provider == "openai":
                return self._call_openai_llm(prompt)
            elif provider == "anthropic":
                return self._call_anthropic_llm(prompt)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _call_zhipu_llm(self, prompt: str) -> str:
        """调用智谱AI"""
        import httpx
        import asyncio

        api_key = self.llm_client['api_key']
        model = self.llm_client['model']
        api_url = self.llm_client['api_url']

        # 分离系统提示词和用户提示词
        parts = prompt.split("\n\n")
        system_prompt = ""
        user_prompt = prompt

        for part in parts:
            if part.startswith("System:"):
                system_prompt = part[7:].strip()
            elif part.startswith("User:"):
                user_prompt = part[5:].strip()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.config.RAG_LLM_TEMPERATURE,
            "top_p": 0.9,
            "max_tokens": self.config.RAG_LLM_MAX_TOKENS,
            "stream": False
        }

        async def make_request():
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    message = result["choices"][0].get("message", {})
                    content = message.get("content", "")
                    if not content:
                        content = message.get("reasoning_content", "")
                    return content
                else:
                    raise Exception(f"ZhipuAI API error: {response.text}")

        # 运行异步请求
        return asyncio.run(make_request())

    def _call_openai_llm(self, prompt: str) -> str:
        """调用OpenAI"""
        client = self.llm_client['client']
        model = self.llm_client['model']

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "基于提供的舌象特征进行专业的中医舌诊分析。"},
                {"role": "user", "content": prompt}
            ],
            temperature=self.config.RAG_LLM_TEMPERATURE,
            max_tokens=self.config.RAG_LLM_MAX_TOKENS
        )

        return response.choices[0].message.content

    def _call_anthropic_llm(self, prompt: str) -> str:
        """调用Anthropic"""
        client = self.llm_client['client']
        model = self.llm_client['model']

        response = client.messages.create(
            model=model,
            max_tokens=self.config.RAG_LLM_MAX_TOKENS,
            system="基于提供的舌象特征进行专业的中医舌诊分析。",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.content[0].text

    def _generate_mock_response(self, query: str, context: RAGContext) -> str:
        """
        生成模拟响应（用于测试）

        Args:
            query: 用户查询
            context: RAG上下文

        Returns:
            模拟响应文本
        """
        import json

        mock_response = {
            "tongue_analysis": {
                "tongue_color": {
                    "observation": "基于知识库分析的舌色特征",
                    "tcm_interpretation": "中医理论解释：舌色淡红为气血调和之象",
                    "clinical_significance": "临床意义：表示身体机能正常"
                },
                "coating_analysis": {
                    "observation": "苔色薄白",
                    "tcm_interpretation": "中医理论解释：薄白苔为胃气充盈之象",
                    "clinical_significance": "临床意义：消化功能正常"
                },
                "tongue_shape_analysis": {
                    "observation": "舌形适中",
                    "tcm_interpretation": "中医理论解释：舌体形态正常",
                    "clinical_significance": "临床意义：无明显病理改变"
                },
                "special_features_analysis": {
                    "observations": [],
                    "tcm_interpretation": "无明显特殊特征",
                    "clinical_significance": "舌象正常"
                }
            },
            "syndrome_diagnosis": {
                "primary_syndrome": "气血调和",
                "secondary_syndromes": [],
                "confidence": 0.75,
                "diagnosis_basis": "基于知识库和舌象特征的匹配分析",
                "tcm_theory_explanation": "根据中医理论，淡红舌、薄白苔、舌形适中为气血调和、阴阳平衡之象，表示身体机能正常。"
            },
            "health_recommendations": {
                "dietary_guidance": {
                    "principle": "均衡营养，饮食有节",
                    "recommended_foods": ["五谷杂粮", "新鲜蔬菜", "适量蛋白质"],
                    "avoid_foods": ["暴饮暴食", "过度油腻", "辛辣刺激"],
                    "seasonal_advice": "根据季节调整饮食结构"
                },
                "lifestyle_guidance": {
                    "exercise": ["适度运动", "如散步、太极"],
                    "sleep": "规律作息，保证充足睡眠",
                    "daily_routine": "劳逸结合，避免过度劳累",
                    "environment": "保持环境清洁，空气流通"
                },
                "emotional_guidance": {
                    "mood_regulation": "保持心情舒畅，避免情绪波动",
                    "stress_management": "学会放松技巧，有效管理压力",
                    "mindfulness": "培养正念习惯，保持内在平静"
                }
            },
            "risk_assessment": {
                "current_health_status": "健康状态良好",
                "potential_risks": [],
                "recommendations": ["定期健康检查", "保持良好生活习惯"]
            },
            "references_used": [
                "中医舌诊基础理论",
                "舌象与证型对应关系",
                "中医养生保健指导"
            ],
            "medical_disclaimer": "重要：本分析仅提供中医调理建议，不能替代专业医疗诊断。如有明显不适症状，请及时就医。"
        }

        return json.dumps(mock_response, ensure_ascii=False, indent=2)

    def run_rag_pipeline(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行完整的RAG流水线

        Args:
            query: 用户查询
            top_k: 检索结果数量
            filters: 元数据过滤条件
            system_prompt: 系统提示词

        Returns:
            完整的RAG结果
        """
        try:
            import time

            # 步骤1: 检索上下文
            start_time = time.time()
            context = self.retrieve_context(query, top_k, filters)
            retrieval_time = (time.time() - start_time) * 1000

            # 步骤2: 生成响应
            start_time = time.time()
            response = self.generate_response(query, context, system_prompt)
            generation_time = (time.time() - start_time) * 1000

            return {
                'success': True,
                'query': query,
                'context': context,
                'response': response,
                'timing': {
                    'retrieval_time_ms': retrieval_time,
                    'generation_time_ms': generation_time,
                    'total_time_ms': retrieval_time + generation_time
                },
                'metadata': context.metadata
            }

        except Exception as e:
            logger.error(f"RAG pipeline failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query
            }


# 全局RAG流水线实例
_rag_pipeline = None


def get_rag_pipeline():
    """获取RAG流水线实例"""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline