# AI舌诊智能诊断系统 - 大模型 + 知识库深入诊断方案

## 目录

1. [架构概述](#架构概述)
2. [当前实现状态](#当前实现状态)
3. [深度诊断流程](#深度诊断流程)
4. [知识库构建](#知识库构建)
5. [大模型集成](#大模型集成)
6. [混合策略](#混合策略)
7. [实现步骤](#实现步骤)
8. [持续学习](#持续学习)
9. [API 使用示例](#api-使用示例)

---

## 架构概述

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户输入层                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                    │
│  │   舌部图片  │  │  用户信息    │  │  主诉症状    │                    │
│  │  (Base64)  │  │(年龄/性别)  │  │  (文字描述)   │                    │
│  └────────────┘  └────────────┘  └────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       特征提取层 (本地 ML)                       │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  图像处理:                                             │       │
│  │  1. 解码 Base64 → PIL Image                          │       │
│  │  2. 图像预处理: 调整大小、归一化                     │       │
│  │  3. 计算哈希: 去重                                  │       │
│  └──────────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  分割模型 (BiSeNetV2):                                 │       │
│  │  - 输入: 原图 (512×512)                                 │       │
│  │  - 输出: 舌部掩码                                     │       │
│  │  - 计算: 舌部区域面积、比例                           │       │
│  └──────────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  分类模型 (PP-HGNetV2-B4):                               │       │
│  │  - 输入: 舌部区域裁剪图 (224×224)                     │       │
│  │  - 输出: 6 个分类头 (softmax)                           │       │
│  │                                                      │       │
│  │   舌色: 淡红/红/绛/紫                                       │       │
│  │  苔色: 白苔/黄苔/灰苔/黑苔                                 │       │
│  │  舌形: 胖大/瘦薄/齿痕/裂纹                                 │       │
│  │  苔质: 薄苔/厚苔/腻苔/剥苔                                 │       │
│  │  特殊: 瘀点/瘀斑/出血点                                   │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        知识增强层                                 │
│  ┌───────────────────────────────────────────────┐             │
│  │   1. 规则引擎预处理                                    │             │
│  │     - 基于中医理论快速诊断                              │             │
│     - 例如: 红舌+黄苔+腻苔→湿热蕴结证                  │             │
│  └───────────────────────────────────────────────┘             │
│  ┌───────────────────────────────────────────────┐             │
│  │   2. 案例检索 (从 40+ 专家案例)                    │             │
│  │     - 计算特征相似度 (Jaccard)                        │             │
│  │     - 特征权重: 舌色(0.25) + 苔色(0.25) + ...            │             │
│  │     - 返回 top 2-3 个最相似案例                         │             │
│  └───────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM 深度推理层 (文心一言)                     │
│  ┌───────────────────────────────────────────────┐             │
│  │  构建 Prompt:                                            │             │
│  │  ┌─────────────────────────────────────┐                 │             │
│  │  │ System: 角色定义 + 医疗伦理约束  │                 │             │
│  │  │        + JSON 输出格式要求          │                 │             │
│  │  └─────────────────────────────────────┘                 │             │
│  │  ┌─────────────────────────────────────┐                 │             │
│  │  │ User: 患者信息 + 舌象特征         │                 │             │
│  │  │       + 病例检索结果 (Few-shot)   │                 │             │
│  │  │       + 规则引擎建议 (可选)     │                 │             │
│  │  └─────────────────────────────────────┘                 │             │
│  │  ┌─────────────────────────────────────┐                 │             │
│  │  │ Few-shot: 示例输出格式            │                 │             │
│  │  │     - 证型 + 辨证依据 + 治则        │                 │             │
│  │  └─────────────────────────────────────┘                 │             │
│  └───────────────────────────────────────────────┘             │
│                              │                                 │
│  ┌───────────────────────────────────────┐                     │
│  │  调用文心 API (ERNIE-Speed/Turbo):     │                     │
│  │  - 流式响应 (实时输出)               │                     │
│  │  - 超时控制 (10秒)                    │                     │
│  │  - 重试机制 (max 2次)                  │                     │
│  └───────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        混合决策层                                 │
│  ┌───────────────────────────────────────────────┐         │
│  │  LLM 成功响应:                                       │         │
│  │    ✅ 直接使用 LLM 诊断结果                            │         │
│  │    ✅ 置信度 = LLM × 案例匹配度 (如果有)               │         │
│  │    ✅ 添加案例检索证据                               │         │
│  └───────────────────────────────────────────────┘         │
│  ┌───────────────────────────────────────────────┐         │
│  │  LLM 失败/超时:                                       │         │
│  │    ⚠️ 降级到混合策略                               │         │
│  │    - 案例 × 0.8 + 规则 × 0.2                      │         │
│  │    ✅ 返回混合诊断结果                             │         │
│  └───────────────────────────────────────────────┘         │
│  ┌───────────────────────────────────────────────┐         │
│  │  完全失败:                                           │         │
│  │    ❌ 使用纯规则诊断兜底                             │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      输出格式化层                                │
│  ┌───────────────────────────────────────────────┐         │
│  │  JSON Schema 验证:                                  │         │
│  │    - 证型名称 (标准化)                               │         │
│  │    - 置信度 (0-1)                                    │         │
│  │    - 辨证过程 (中医理论依据)                         │         │
│  │    - 健康建议 (饮食/生活/情志)                        │         │
│    - 风险评估 (低/中/高)                               │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      持久化存储层                                │
│  ┌───────────────────────────────────────────────┐         │
│  │  PostgreSQL 数据库:                                     │         │
│  │    - DiagnosisHistory 表: 诊断历史                       │         │
│  │      * features (JSONB): ML 模型输出                   │         │
│  │      * results (JSONB): LLM+混合结果                     │         │         │
│  │      * user_info (JSONB): 用户信息                    │         │
│  │    - 新诊断数据 → 持久化 → 可用于案例检索         │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     持续学习 (可选)                              │
│  ┌───────────────────────────────────────────────┐         │
│  │  用户反馈收集:                                       │         │
│  │    - "诊断结果准确吗?" 👍👎                          │         │
│  │    - 收集正负反馈                                    │         │
│  │  └─────────────────────────────────────────────┘         │
│  ┌───────────────────────────────────────────────┐         │
│  │  知识库更新:                                         │         │
│  │    - 准确案例 → 加入案例库                            │         │
│  │    - 规则权重优化 (强化学习)                         │         │
│  │    - Few-shot 示例精选                               │         │
│  │  └─────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 当前实现状态

### ✅ 已完成的组件

| 组件 | 文件路径 | 状态 |
|------|----------|------|
| 文心 API 配置 | `api_service/config/wenxin_config.yaml` | ✅ 完整 |
| 规则诊断引擎 | `api_service/core/rule_based_diagnosis.py` | ✅ 7 种证型规则 |
| 案例检索系统 | `api_service/core/case_retrieval.py` | ✅ 40+ 专家案例 |
| System Prompt | `api_service/prompts/system_prompt.txt` | ✅ 角色定义+约束 |
| User Prompt 模板 | `api_service/prompts/user_prompt_template.py` | ✅ 动态构建 |
| Few-shot 示例 | `api_service/prompts/few_shot_examples.json` | ✅ 40+ 案例 |
| 混合策略配置 | `api_service/config/rule_based_config.json` | ✅ 权重配置 |
| LLM 诊断引擎 | `api_service/core/llm_diagnosis.py` | ✅ 已创建 |

### ⏳ 待实现的功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| LLM API 调用 | 集成到 `api/v2/diagnosis` 端点 | 🔴 高 |
| 异步任务集成 | `worker/tasks.py` 中实现异步 LLM 诊断 | 🟡 中 |
| 用户反馈收集 | 前端+后端完整反馈功能 | 🟢 低 |
| 知识库更新 | 根据用户反馈动态优化 | 🟢 低 |

---

## 深度诊断流程

### 输入数据准备

```json
{
  "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
  "user_info": {
    "age": 35,
    "gender": "male",
    "symptoms": ["头晕", "口干", "乏力"],
    "medical_history": ["高血压", "糖尿病"],
    "chief_complaint": "近日感觉精力不足，舌部颜色变红"
  },
  "enable_llm_diagnosis": true,
  "enable_rule_fallback": true
}
```

### 特征提取 (本地 ML)

```python
# 分割
tongue_area, tongue_ratio = segmentor.predict(image)

# 分类
classification = classifier.predict(tongue_region)

# 特征结构化
features = {
    "tongue_color": {
        "淡红": 0.3,
        "红": 0.5,
        "绛": 0.15,
        "紫": 0.05
    },
    "coating_color": {
        "白苔": 0.2,
        "黄苔": 0.7,
        "灰苔": 0.05,
        "黑苔": 0.05
    },
    "tongue_shape": {
        "胖大": 0.3,
        "瘦薄": 0.2,
        "齿痕": 0.4,
        "裂纹": 0.1
    },
    "coating_quality": {
        "薄苔": 0.4,
        "厚苔": 0.4,
        "腻苔": 0.15,
        "剥苔": 0.05
    },
    "special_features": {
        "瘀点": 0.1,
        "瘀斑": 0.05,
        "出血点": 0
    },
    "health_status": {
        "s0": 0.6,  // 健康
        "s1": 0.3,  // 亚健康
        "s2": 0.1   // 疾病
    }
}
```

### 知识增强

#### 1. 规则预处理

```python
# 规则引擎快速诊断
from api_service.core.rule_based_diagnosis import diagnose_from_classification

rule_result = diagnose_from_classification(features)

# 输出示例:
{
    "primary_syndrome": "湿热蕴结证",
    "confidence": 0.75,
    "secondary_syndromes ["肝胆湿热证", "脾虚湿盛证"],
    "tcm_theory": "舌红苔黄腻，湿热内蕴，肝胆火旺...",
    "recommendations": {
        "dietary": ["清淡饮食", "清热利湿"],
        "lifestyle": ["保持心情舒畅", "适度运动"],
        "emotional": ["避免焦虑"]
    }
}
```

#### 2. 案例检索

```python
# 检索相似案例
from api_service.core.case_retrieval import retrieve_similar_cases_from_classification

case_result = retrieve_similar_cases_from_classification(
    classification_result=classification,
    top_k=2
)

# 输出示例:
{
    "matches": [
        {
            "syndrome": "湿热蕴结证",
            "confidence": 0.85,
            "matched_features": ["红舌", "黄苔", "腻苔"],
            "case_id": "case_001",
            "theory": "舌红苔黄腻为湿热之征...",
            "treatment": "清热利湿，调理脾胃..."
        },
        {
            "syndrome": "肝胆湿热证",
            "confidence": 0.72,
            "matched_features": ["红舌", "黄苔"],
            "case_id": "case_002",
            "theory": "肝胆湿热，郁久化火...",
            "treatment": "清肝利胆，泻火解毒..."
        }
    ],
    "match_details": {...}
}
```

### LLM 深度推理

#### 构建完整 Prompt

```
System Prompt (角色定义):
你是 AI舌诊辅助诊断系统，负责基于舌象特征进行中医辨证分析。

【角色定位】
你是一名具有丰富临床经验的中医舌诊专家，能够：
1. 分析舌象特征（舌色、苔色、舌形、苔质等）
2. 结合中医辨证理论进行证型辨识
3. 提供个性化的健康建议

【医疗伦理约束 - 禁止行为】
1. ❌ 严禁直接给出确诊结论（如"诊断为XX病"）
2. ❌ 严禁开具处方或药物建议
3. ❌ 严禁替代专业中医师的判断
4. ❌ 严禁给予具体的治疗建议（如"服用XX药物"）

【必须包含的免责声明】
以下分析仅供参考，不能替代专业中医师的诊断。
如有不适，请及时就医。

【输出格式要求】
必须严格按照以下 JSON 格式输出：
{
  "syndrome_analysis": {
    "possible_syndromes": [
      {
        "name": "证型名称",
        "confidence": 0.0-1.0,
        "evidence": "特征证据描述",
        "tcm_theory": "中医理论解释"
      }
    ],
    "primary_syndrome": "主要证型",
    "secondary_syndromes": ["次要证型1", "次要证型2"],
    "syndrome_description": "证型综合描述"
  },
  "anomaly_detection": {
    "detected": true/false,
    "reason": "异常原因",
    "recommendations": ["建议1", "建议2"]
  },
  "health_recommendations": {
    "dietary": ["饮食建议1", "饮食建议2"],
    "lifestyle": ["生活建议1", "生活建议2"],
    "emotional": ["情志建议1", "情志建议2"]
  },
  "confidence": 0.0-1.0,
  "reasoning_process": "辨证推理过程"
}

【异常检测规则】
- 置信度 < 0.3 → 标记异常，建议咨询专业医师
- 图像质量差（模糊、光线不足）→ 标记异常
- 特征矛盾（如舌色与苔色不匹配）→ 标记异常
```

```
User Prompt (上下文注入):
舌象特征分析结果：

【分类模型输出】
舌色分布:
- 淡红舌: 30%
- 红舌: 50%
- 绛紫舌: 15%
- 紫舌: 5%

苔色分布:
- 白苔: 20%
- 黄苔: 70%
- 灰苔: 5%
- 黑苔: 5%

舌形特征:
- 胖大舌: 30%
- 瘦薄舌: 20%
- 齿痕舌: 40%
- 裂纹舌: 10%

苔质特征:
- 薄苔: 40%
- 厚苔: 40%
- 腻苔: 15%
- 剥苔: 5%

特殊特征:
- 瘀点: 10%
- 瘀斑: 5%
- 出血点: 0%

健康状态:
- 健康: 60%
- 亚健康: 30%
- 病理: 10%

【用户信息】
年龄: 35 岁
性别: 男
主要症状: 头晕、口干、乏力
既往病史: 高血压、糖尿病
主诉: 近日感觉精力不足，舌部颜色变红

【案例检索结果】
相似舌诊案例 (按相似度排序):

案例 1 (相似度: 85%):
证型: 湿热蕴结证
舌象特征: 红舌、黄苔、腻苔、齿痕
专家辨证: 舌红苔黄腻为湿热内蕴之征...
治则: 清热利湿，调理脾胃

案例 2 (相似度: 72%):
证型: 肝胆湿热证
舌象特征: 红舌、黄苔、齿痕
专家辨证: 肝胆湿热，郁久化火...
治则: 清肝利胆，泻火解毒

【规则引擎建议】
规则匹配结果: 湿热蕴结证 (置信度: 75%)
特征匹配: 舌色(红) + 苔色(黄) + 苔质(腻)

【辨证要求】
1. 基于舌象特征进行证型辨识
2. 参考案例检索结果的专家辨证思路
3. 考虑用户症状和病史信息
4. 给出详细的辨证依据（中医理论）
5. 提供针对性的健康建议

请严格按照 JSON 格式输出诊断结果。
```

#### 调用文心 API

```python
import httpx
import asyncio

async def call_wenxin_api(user_prompt: str) -> str:
    """调用文心一言 API"""
    # 1. 获取 Access Token
    token = await get_access_token()

    # 2. 构建请求
    url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messages": [
            {"role": "system", "content": load_system_prompt()},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_output_tokens": 2000
    }

    # 3. 发送请求
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

    # 4. 解析响应
    result = response.json()
    return result["result"]  # 文心生成的文本
```

### 混合决策策略

```python
async def hybrid_diagnosis(features, user_info):
    """混合诊断策略"""

    # 1. 尝试 LLM 诊断
    try:
        llm_result = await llm_diagnosis_engine.diagnose(
            image_base64=features['image_base64'],
            classification_result=features['classification'],
            user_info=user_info
        )

        if llm_result['success']:
            # LLM 成功
            confidence = llm_result['confidence']
            if llm_result.get('retrieved_cases_count', 0) > 0:
                # 有案例检索支持，提高置信度
                confidence = min(confidence + 0.1, 1.0)

            return {
                'primary_syndrome': llm_result['syndrome_analysis']['primary_syndrome'],
                'confidence': confidence,
                'source': 'llm',
                'details': llm_result
            }

    except Exception as e:
        logger.error(f"LLM diagnosis failed: {e}")

    # 2. 降级到混合策略 (案例 + 规则)
    try:
        case_result = await retrieve_similar_cases(features)
        rule_result = diagnose_from_classification(features)

        # 加权融合
        final_confidence = (case_result.confidence * 0.8 +
                         rule_result.confidence * 0.2) / 2

        return {
            'primary_syndrome': rule_result.primary_syndrome,
            'confidence': final_confidence,
            'source': 'hybrid',
            'details': {
                'case_confidence': case_result.confidence,
                'rule_confidence': rule_result.confidence
            }
        }

    except Exception as e:
        logger.error(f"Hybrid diagnosis failed: {e}")

    # 3. 兜底：纯规则诊断
    return {
        'primary_syndrome': rule_result.primary_syndrome,
        'confidence': rule_result.confidence,
        'source': 'rule_only',
        'details': {}
    }
```

---

## 知识库构建

### 1. 规则知识库 (`rule_based_config.json`)

```json
{
  "syndrome_rules": {
    "心肺气虚证": {
      "primary_features": {
        "tongue_color": {"淡红": 0.3, "淡白": 0.4},
        "coating_color": {"白苔": 0.5, "薄苔": 0.4},
        "tongue_shape": {"胖大": 0.4, "齿痕": 0.3}
      },
      "synonyms": ["心脾两虚", "气血两虚"],
      "theory": "舌色淡白或淡红，苔薄白或薄白腻。心开窍于舌，心气虚则舌色淡；脾主运化水谷，脾虚则舌质胖嫩有齿痕。治宜补益心肺之气。",
      "recommendations": {
        "dietary": ["山药", "莲子", "桂圆", "大枣"],
        "lifestyle": ["避免过度劳累", "保持规律作息"],
        "chinese_medicine": "党参", "黄芪", "白术"]
      }
    },
    "肾气虚证": {
      "primary_features": {
        "tongue_color": {"淡红": 0.4, "淡白": 0.3, "淡胖大": 0.2},
        "coating_color": {"白苔": 0.6, "薄苔": 0.3},
        "tongue_shape": {"胖大": 0.5, "齿痕": 0.4, "水肿舌": 0.3}
      },
      "synonyms": ["肾阳虚", "命门火衰"],
      "theory": "舌色淡白胖嫩，苔白或白润。肾阳不足，蒸化水液无力，舌体失养而胖嫩齿痕。治宜温补肾阳。",
      "recommendations": {
        "dietary": ["羊肉", "韭菜", "栗子", "核桃"],
        "lifestyle": ["注意保暖", "节制房事"],
        "chinese_medicine": "附子", "肉桂", "杜仲"]
      }
    },
    "肝胆湿热证": {
      "primary_features": {
        "tongue_color": {"红": 0.6, "边红": 0.3},
        "coating_color": {"黄苔": 0.7, "黄腻苔": 0.5},
        "tongue_shape": {"齿痕": 0.3, "尖舌": 0.2}
      },
      "synonyms": ["肝火旺", "湿热蕴结"],
      "theory": "舌色红，苔黄腻，多为肝胆湿热或肝火上炎。肝开窍于目，肝经热盛，舌色红赤。",
      "recommendations": {
        "dietary": ["苦瓜", "黄瓜", "芹菜", "绿豆"],
        "lifestyle": ["避免熬夜", "保持心情舒畅"],
        "chinese_medicine": "龙胆草", "黄芩", "栀子"]
      }
    },
    "脾胃虚弱证": {
      "primary_features": {
        "tongue_color": {"淡红": 0.5, "淡白": 0.3},
        "coating_color": {"白苔": 0.6, "薄苔": 0.3, "白腻苔": 0.2},
        "tongue_shape": {"胖大": 0.4, "齿痕": 0.5, "舌边有齿痕": 0.2}
      },
      "synonyms": ["脾虚湿盛", "脾虚湿困"],
      "theory": "舌色淡红或淡白，苔白腻。脾主运化，脾虚失运，湿浊内生，故苔腻。治宜健脾化湿。",
      "recommendations": {
        "dietary": ["薏米", "白术", "山药", "茯苓"],
        "lifestyle": ["规律饮食", "避免生冷油腻"],
        "chinese_medicine": "党参", "白术", "茯苓", "半夏"]
      }
    },
    "阴虚火旺证": {
      "primary_features": {
        "tongue_color": {"红": 0.5, "红舌": 0.3, "绛红舌": 0.2},
        "coating_color": {"少苔": 0.4, "无苔": 0.3, "黄苔": 0.2},
        "tongue_shape": {"瘦薄": 0.6, "裂纹舌": 0.5},
        "special_features": {"裂纹": 0.4, "红点": 0.3}
      },
      "synonyms": ["阴虚内热", "肾阴不足"],
      "theory": "舌红少苔或无苔，裂纹多为阴虚火旺之象。肾阴不足，虚火内扰，灼伤津液。",
      "recommendations": {
        "dietary": ["梨", "银耳", "百合", "枸杞子"],
        "lifestyle": ["避免熬夜", "节制房事"],
        "chinese_medicine": "生地", "玄参", "麦冬"]
      }
    },
    "痰湿内阻证": {
      "primary_features": {
        "tong_color": {"淡胖大": 0.4, "淡红": 0.3},
        "coating_color": {"白腻苔": 0.6, "腻苔": 0.5},
        "tongue_shape": {"胖大": 0.6, "齿痕": 0.5},
        "coating_quality": {"腻苔": 0.6, "厚苔": 0.3}
      },
      "synonyms": ["痰浊阻中焦", "湿浊困脾"],
      "theory": "舌体胖大，苔白腻，为痰湿内阻之象。脾失运化，痰湿内停。",
      "recommendations": {
        "dietary": ["生姜", "陈皮", "半夏", "白术"],
        "lifestyle": ["少食甜食", "适度运动"],
        "chinese_medicine": "半夏", "陈皮", "茯苓", "苍术"]
      }
    },
    "血瘀证": {
      "primary_features": {
        "tongue_color": {"紫暗舌": 0.4, "青紫舌": 0.3},
        "coating_color": {"淡白苔": 0.3, "白苔": 0.3},
        "special_features": {"瘀点": 0.5, "瘀斑": 0.4, "舌下络脉怒张": 0.5}
      },
      "synonyms": ["血瘀阻络", "瘀血证"],
      "theory": "舌色紫暗，有瘀点瘀斑，为血瘀之征。气虚血滞，或气滞血瘀。",
      "recommendations": {
        "dietary": ["山楂", "桃仁", "红花", "丹参"],
        "lifestyle": ["避免受寒", "适当运动"],
        "chinese_medicine": "丹参", "桃仁", "红花", "川芎"]
      }
    }
  },
  "diagnosis_combination_rules": [
    {
      "patterns": [
        {"tongue_color": {"红": 0.5, "边红": 0.4}},
        {"coating_color": {"黄苔": 0.6, "腻苔": 0.4}}
      ],
      "result": "湿热蕴结证",
      "confidence_boost": 0.1
    },
    {
      "patterns": [
        {"tongue_color": {"淡红": 0.4, "淡白": 0.3}},
        {"coating_color": {"白苔": 0.5, "薄苔": 0.4}},
        {"tongue_shape": {"胖大": 0.4, "齿痕": 0.5}}
      ],
      "result": "心脾两虚证",
      "confidence_boost": 0.05
    }
  ],
  "feature_weights": {
    "tongue_color": 0.25,
    "coating_color": 0.25,
    "tongue_shape": 0.15,
    "coating_quality": 0.15,
    "special_features": 0.20
  },
  "fallback_strategy": {
    "llm_timeout_seconds": 10,
    "llm_max_retries": 2,
    "enable_case_retrieval": true,
    "enable_rule_based": true,
    "hybrid_weights": {
      "llm": 0.7,
      "case_retrieval": 0.2,
      "rule_based": 0.1
    }
  }
}
```

### 2. 案例知识库 (`few_shot_examples.json`)

```json
[
  {
    "id": "case_001",
    "tongue_color": ["红舌", "边红"],
    "coating_color": ["黄苔", "黄腻苔"],
    "tongue_shape": ["齿痕"],
    "special_features": [],
    "syndrome": "湿热蕴结证",
    "expert_analysis": {
      "diagnosis": "湿热蕴结证",
      "confidence": 0.85,
      "reasoning": "舌质红，苔黄腻腻，主湿热内蕴之象。舌色红主热，苔黄腻主湿热。结合舌质胖嫩有齿痕，兼有脾虚湿盛之象。",
      "tcm_theory": "舌为心之苗，苔为胃气之蒸。舌红苔黄腻，示心胃热盛；齿痕为脾虚之征。此为湿热蕴结，兼有脾虚。",
      "treatment": "清热利湿，健脾化湿。方用甘露消毒丹合参苓白术散加减。",
      "symptoms": ["口苦", "口干", "小便短赤", "大便秘结"],
      "risk_factors": ["饮食不节", "情志不畅"]
    }
  },
  {
    "id": "case_002",
    "tongue_color": ["红舌", "绛红"],
    "coating_color": ["少苔", "无苔"],
    "tongue_shape": ["瘦薄", "裂纹舌"],
    "special_features": ["红点"],
    "syndrome": "阴虚火旺证",
    "expert_analysis": {
      "diagnosis": "阴虚火旺证",
      "confidence": 0.90,
      "reasoning": "舌红少苔有裂纹，红点，为阴虚火旺典型舌象。舌质红主热，少苔主阴虚。裂纹为阴伤之征。",
      "tcm_theory": "肾阴不足，虚火内扰，灼伤津液。舌为心之苗，肾阴不足，虚火扰心，故见舌红。",
      "treatment": "滋阴降火，交通心肾。方用黄连阿胶汤合六味地黄丸加减。",
      "symptoms": ["五心烦热", "盗汗", "失眠多梦", "腰膝酸软"],
      "risk_factors": ["房劳过度", "熬夜", "辛辣厚味"]
    }
  }
  // ... 40+ more cases
]
```

---

## 大模型集成

### 文心大模型 API 集成

#### 1. API 配置

```yaml
# api_service/config/wenxin_config.yaml
wenxin:
  # API 密钥 (从百度千帆平台获取)
  api_key: "your_api_key_here"
  secret_key: "your_secret_key_here"

  # 模型选择
  model: "ERNIE-Speed"  # 选项: ERNIE-Speed, ERNIE-Turbo, ERNIE-4.0

  # API 端点
  api_base: "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop"

  # 调用参数
  temperature: 0.7      # 温度 (0-1), 越高越随机
  top_p: 0.9           # 核采样 (0-1)
  max_tokens: 2000     # 最大输出长度

  # 超时和重试
  timeout: 10           # 超时时间(秒)
  max_retries: 2        # 最大重试次数
  retry_delay: 1       # 重试延迟(秒)

  # 成本监控
  enable_cost_monitoring: true
  daily_budget: 100     # 每日预算(元)
  cost_per_1k_tokens: 0.004  # 每1K token 成本(估算)

  # 规则库兜底
  enable_rule_based: true
  enable_case_retrieval: true
```

#### 2. 获取 API 密钥

**步骤：**
1. 访问 [百度千帆平台](https://console.bce.baidu.com/qianfan/)
2. 登录后进入「应用接入」
3. 创建新应用，选择「自定义服务」
4. 在模型广场中选择「文心一言」
5. 配置应用并获取 API Key 和 Secret Key

#### 3. 访问 Token 获取

```python
import httpx

async def get_access_token():
    """获取文心 API Access Token"""
    url = "https://aip.bce.bce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/access_token"

    params = {
        "grant_type": "client_credentials",
        "client_id": "your_api_key",
        "client_secret": "your_secret_key"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=params)

        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 2592000)  # 30 days
            return access_token, expires_in
        else:
            raise Exception(f"Failed to get token: {response.text}")
```

---

## 混合策略

### 权重配置

```json
{
  "hybrid_weights": {
    "llm": 0.7,           // 大模型推理 (主要)
    "case_retrieval": 0.2,  // 案例检索 (补充证据)
    "rule_based": 0.1       // 规则库 (兜底)
  }
}
```

### 混合决策逻辑

```
┌─────────────────────────────────────────────────────┐
│  开始混合诊断                                       │
└─────────────────────────────────────────────────────┘
                │
                ▼
    ┌───────────┐
    │  调用 LLM │
    └───────────┘
        │
        ├─ 成功 ──────────────────────────┐
        │                                 │
        ▼                                 │
    ┌───────────┐                         │
    │ 解析 LLM  │                         │
    │ JSON 响应  │                         │
    └───────────┘                         │
        │                                 │
        ├─ 解析成功 ────────────────────┐    │
        │                                │    │
        ▼                                │    │
    ┌───────────┐                      │    │
    │ 置信度 =     │                      │    │
    │ LLM × 0.7   │                      │    │
    │ 案例 × 0.2   │                      │    │
    │ 规则 × 0.1   │                      │    │
    │ (降序级)     │                      │    │
    └───────────┘                      │    │
        │                                 │    │
        ├─ LLM失败/超时 ───────────────┐│    │
        │                               ││    │
        ▼                               ││    │
    ┌───────────┐                     ││    │
    │ 降级策略   │                     ││    │
    └───────────┘                     ││    │
        │                                 │    │
        ├─ 案例存在 ─────────────────┐││    │
        │                              │││    │
        ▼                              │││    │
    ┌───────────┐                      │││    │
    │ 案例 × 0.8   │                      │││    │
    │ 规则 × 0.2   │                      │││    │
    └───────────┘                      │││    │
        │                                 ││    │
        ├─ 案例不存在 ───────────────┐││    │
        │                             │││    │
        ▼                             │││    │
    ┌───────────┐                      │││    │
    │ 纯规则诊断 │                      │││    │
    └───────────┘                      │││    │
        │                                 ││    │
        ├─ 全部失败 ─────────────────┐││    │
        │                               │││    │
        ▼                             │││    │
    ┌───────────┐                      │││    │
    │ 返回错误     │                      │││    │
    └───────────┘                      │││    │
        │                                 ││    │
        └────────────────────────────────┘│││
```

---

## 实现步骤

### 步骤 1: 配置文心大模型

```bash
# 1. 安装依赖
pip install httpx httpx[http2] pydantic

# 2. 设置环境变量
export BAIDU_API_KEY="your_api_key"
export BAIDU_SECRET_KEY="your_secret_key"
```

### 步骤 2: 集成到诊断 API

修改 `api_service/app/api/v2/diagnosis.py`:

```python
from api_service.core.llm_diagnosis import LLMDiagnosisEngine, create_llm_diagnosis_engine

# 全局 LLM 引擎实例
llm_engine = create_llm_diagnosis_engine()

@router.post("", response_model=DiagnosisResponse, tags=["Diagnosis"])
async def create_diagnosis(
    request: DiagnosisRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    # ... image preprocessing ...

    # Try LLM diagnosis first
    diagnosis_result = None
    used_fallback = False

    try:
        if request.enable_llm_diagnosis:
            # 1. Prepare classification result for LLM
            classification_result = {
                'tongue_color': classification['tongue_color'],
                'coating_color': classification['coating_color'],
                'tongue_shape': classification['tongue_shape'],
                'coating_quality': classification['coating_quality'],
                'special_features': classification['special_features'],
                'health_status': classification.get('health_status', {})
            }

            # 2. Call LLM diagnosis
            llm_result = await llm_engine.diagnose(
                image_base64=image_data,
                classification_result=classification_result,
                user_info=request.user_info
            )

            if llm_result['success']:
                # Use LLM result
                syndrome_analysis = llm_result['syndrome_analysis']
                recommendations = llm_result['health_recommendations']
                anomaly = llm_result['anomaly_detection']
                confidence = llm_result['confidence']

                # Store LLM reasoning
                diagnosis_result = {
                    'primary_syndrome': syndrome_analysis['primary_syndrome'],
                    'syndromes': syndrome_analysis['possible_syndromes'],
                    'syndrome_description': syndrome_analysis['syndrome_description'],
                    'syndrome_tcm_theory': syndrome_analysis['possible_syndromes'][0].get('tcm_theory', ''),
                    'confidence': confidence,
                    'anomaly': anomaly['detected'],
                    'risk_level': 'high' if anomaly['detected'] else 'low',
                    'recommendations': recommendations,
                    'reasoning': llm_result.get('reasoning_process', ''),
                    'diagnosis_method': 'llm',
                    'llm_time_ms': llm_result.get('llm_time_ms', 0),
                    'retrieved_cases_count': llm_result.get('retrieved_cases_count', 0)
                }
                logger.info(f"LLM diagnosis completed successfully, syndrome: {diagnosis_result['primary_syndrome']}")
            else:
                used_fallback = True

    except Exception as e:
        logger.error(f"LLM diagnosis error: {e}")
        used_fallback = True

    # Fallback to rule-based diagnosis
    if used_fallback or not request.enable_llm_diagnosis:
        logger.info("Using rule-based diagnosis")
        rule_result = diagnose_from_classification(classification)

        diagnosis_result = {
            'primary_syndrome': rule_result.primary_syndrome,
            'syndromes': rule_result.possible_syndromes,
            'syndrome_description': rule_result.syndrome_description,
            'syndrome_tcm_theory': rule_result.tcm_theory,
            'confidence': rule_result.confidence,
            'anomaly': rule_result.confidence < 0.5,
            'risk_level': 'medium' if rule_result.confidence < 0.5 else 'low',
            'recommendations': rule_result.recommendations,
            'reasoning': '规则库诊断',
            'diagnosis_method': 'rule_based',
            'retrieved_cases_count': 0
        }

    # Store to database
    # ... database operations ...
```

---

## 持续学习

### 用户反馈收集

```javascript
// 前端反馈界面
<div class="feedback-section">
  <h3>诊断结果准确吗？</h3>
  <button onclick="submitFeedback(1)">👍 准确</button>
  <button onclick="submitFeedback(-1)">👎 不准确</button>
</div>

<script>
async function submitFeedback(feedback: 1 | -1) {
  const response = await fetch('/api/v2/diagnosis/${diagnosisId}/feedback', {
    method: 'POST',
    body: JSON.stringify({ feedback })
  })
  const result = await response.json()

  if (result.success) {
    alert('感谢反馈')
    // 根据反馈调整诊断结果
  }
}
</script>
```

### 知识库更新机制

```python
async def update_knowledge_base(diagnosis_id: str, feedback: int):
    """根据反馈更新知识库"""
    # 1. 获取诊断详情
    diagnosis = get_diagnosis_by_id(diagnosis_id)

    # 2. 如果反馈为正面 (feedback = 1)，加入案例库
    if feedback == 1:
        add_to_case_library(diagnosis)

    # 3. 调整规则权重
    if feedback == 1:
        increase_rule_weight(diagnosis.primary_syndrome)
    elif feedback == -1:
        decrease_rule_weight(diagnosis.primary_syndrome)

def add_to_case_library(diagnosis):
    """将准确的诊断添加到案例库"""
    new_case = {
        "id": f"case_{len(case_library) + 1:03d}",
        "tongue_color": extract_tongue_color(diagnosis.features),
        "coating_color": extract_coating_color(diagnosis.features),
        "syndrome": diagnosis.primary_syndrome,
        "expert_analysis": {
            "diagnosis": diagnosis.primary_syndrome,
            "confidence": diagnosis.confidence,
            "reasoning": diagnosis.reasoning,
            "tcm_theory": diagnosis.syndrome_tcm_theory,
            "treatment": "基于...",
            "symptoms": diagnosis.symptoms,
            "risk_factors": diagnosis.risk_factors
        }
    }

    case_library.append(new_case)
    save_case_library_to_disk()
```

---

## API 使用示例

### Python 客户端示例

```python
import httpx
import base64

async def submit_diagnosis(image_path: str):
    """提交诊断请求"""

    # 1. 读取并编码图片
    with open(image_path, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode()

    # 2. 构建请求
    payload = {
        "image": f"data:image/png;base64,{image_base64}",
        "enable_llm_diagnosis": True,
        "enable_rule_fallback": True,
        "user_info": {
            "age": 35,
            "gender": "male",
            "symptoms": ["头晕", "口干"],
            "chief_complaint": "精力不足"
        }
    }

    # 3. 发送请求
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://192.168.51.194:9000/api/v2/diagnosis",
            json=payload,
            timeout=60
        )

        result = response.json()

    # 4. 解析响应
    if result['success']:
        diagnosis = result['data']
        print(f"证型: {diagnosis['primary_syndrome']}")
        print(f"置信度: {diagnosis['confidence']:.1%}")
        print(f"诊断方法: {diagnosis['diagnosis_method']}")
        print(f"推理过程: {diagnosis.get('reasoning', '')}")
        print(f"健康建议: {diagnosis['recommendations']}")
    else:
        print(f"诊断失败: {result.get('error', 'Unknown error')}")

# 使用示例
await submit_diagnosis("path/to/tongue_image.png")
```

---

## 总结

结合大模型和知识库进行深入诊断的关键要点：

### 1. 三层架构
- **特征提取层**: 本地 ML 模型 (BiSeNetV2 + PP-HGNetV2)
- **知识增强层**: 规则库 + 案例检索
- **LLM 推理层**: 文心大模型深度辨证

### 2. 混合策略
- **LLM (70%)**: 主要推理，提供深度分析
- **案例检索 (20%): 补充证据，提高可信度
- **规则库 (10%)**: 兜底机制，确保可用性

### 3. 知识库构建
- **规则知识库**: 7 种证型的完整规则
- **案例知识库**: 40+ 专家标注的真实案例
- **持续学习**: 基于用户反馈动态优化

### 4. 输出质量保证
- **结构化输出**: JSON Schema 约束
- **中医理论验证**: 与规则库一致性检查
- **医疗伦理约束**: 严禁确诊、开处方
- **异常检测**: 低置信度自动标记

### 5. 持续优化
- **用户反馈**: 收集准确度反馈
- **案例库更新**: 精选高质量案例
- **规则调优**: 基于反馈调整权重

这种架构充分利用了大模型的推理能力、案例库的经验传承和规则库的确定性，形成了一个强大且可靠的舌诊诊断系统。