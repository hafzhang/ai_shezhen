# System Prompt 工程与优化文档

## 文档信息

**任务**: task-4-2 - System Prompt工程与优化
**日期**: 2026-02-12
**版本**: v1.0
**作者**: Ralph Agent

---

## 概述

本文档详细说明了AI舌诊智能诊断系统的System Prompt设计与优化策略。System Prompt用于约束和引导文心一言大模型（ERNIE-Speed）进行专业、安全的舌诊辅助诊断。

## System Prompt 架构

### 核心约束

#### 1. 医疗安全边界

这是最重要的约束，确保AI系统的安全性：

| 约束 | 说明 | 违规处理 |
|--------|------|------------|
| 严禁确诊性诊断 | 不给出"确诊"结论 | 使用"可能提示"、"考虑"等表述 |
| 严禁开具处方 | 不建议具体药物 | 仅建议食疗、调理方向 |
| 严禁替代医生 | 强调AI辅助工具定位 | 明确需要专业医生介入 |
| 医疗免责声明 | 每次输出必含 | 标准化免责声明模板 |

#### 2. 输出格式要求

确保LLM输出的JSON格式正确且可解析：

```json
{
  "diagnosis": {...},     // 必需
  "syndrome_analysis": {...},  // 必需
  "anomaly_detection": {...},  // 必需
  "health_recommendations": {...},  // 必需
  "confidence_analysis": {...},  // 必需
  "disclaimer": {...}     // 必需
}
```

#### 3. 诊断原则

- **基于中医理论**: 参考权威中医典籍
- **多维度综合分析**: 舌色、苔色、舌形、苔质、特征
- **不确定性明确标注**: 对不确定内容明确说明
- **辨证逻辑严谨**: 遵循中医八纲辨证、脏腑辨证

#### 4. 异常检测规则

| 规则编号 | 检测条件 | 处理方式 |
|----------|-----------|-----------|
| 规则1 | 任何特征置信度 < 0.3 | 罕见特征，建议重拍 |
| 规则2 | 特征之间存在矛盾 | 提示可能识别错误 |
| 规则3 | 图像质量不合格 | 建议改善拍摄条件 |
| 规则4 | 主要特征提取失败 | 建议就医诊断 |
| 规则5 | 健康舌与多病理特征并存 | 标记需人工审核 |

## JSON Schema 定义

### diagnosis (诊断详情)

```typescript
interface Diagnosis {
  tongue_color: {
    prediction: "淡红舌" | "红舌" | "绛紫舌" | "淡白舌";
    confidence: number;  // 0.0 - 1.0
    description: string;
  };
  coating_color: {
    prediction: "白苔" | "黄苔" | "黑苔" | "花剥苔";
    confidence: number;
    description: string;
  };
  tongue_shape: {
    prediction: "正常" | "胖大舌" | "瘦薄舌";
    confidence: number;
    description: string;
  };
  coating_quality: {
    prediction: "薄苔" | "厚苔" | "腐苔";
    confidence: number;
    description: string;
  };
  special_features: {
    red_dots: FeatureDetection;
    cracks: FeatureDetection;
    teeth_marks: FeatureDetection;
  };
  health_status: {
    prediction: "健康舌" | "不健康舌";
    confidence: number;
    description: string;
  };
}

interface FeatureDetection {
  present: boolean;
  confidence: number;
  description: string;
}
```

### syndrome_analysis (证型分析)

```typescript
interface SyndromeAnalysis {
  possible_syndromes: Syndrome[];
  primary_syndrome: string | null;
  secondary_syndromes: string[];
  syndrome_description: string;
}

interface Syndrome {
  name: string;           // 证型名称
  confidence: number;       // 0.0 - 1.0
  evidence: string[];     // 辨证依据
  TCM_theory: string;     // 中医理论依据
}
```

### anomaly_detection (异常检测)

```typescript
interface AnomalyDetection {
  detected: boolean;
  reason: string | null;
  recommendations: string[];
}
```

### health_recommendations (健康建议)

```typescript
interface HealthRecommendations {
  dietary: string[];        // 饮食建议
  lifestyle: string[];       // 生活调理建议
  TCM_therapy: string[];    // 中医调理方法
  medical_consultation: string;  // 是否建议就医
}
```

### confidence_analysis (置信度分析)

```typescript
interface ConfidenceAnalysis {
  overall_confidence: number;  // 0.0 - 1.0
  confidence_breakdown: {
    feature_extraction: number;
    syndrome_identification: number;
    recommendation_generation: number;
  };
  uncertainty_factors: string[];
}
```

### disclaimer (免责声明)

```typescript
interface Disclaimer {
  ai_assistant_only: boolean;      // AI辅助工具标识
  not_medical_advice: boolean;     // 非医疗建议标识
  consult_doctor_reminder: boolean; // 就医提醒
  emergency_warning: string | null;  // 紧急情况警告
}
```

## 异常检测详细规则

### 规则1: 极度罕见特征

**检测条件**:
- 舌色为"绛紫舌"且置信度 < 0.3
- 苔色为"黑苔"或"花剥苔"且置信度 < 0.3
- 舌形与置信度 < 0.25

**异常原因**:
训练集中该特征样本极少（<1%），可能是识别错误

**处理建议**:
```json
{
  "anomaly_detection": {
    "detected": true,
    "reason": "检测到极度罕见舌象（置信度<0.3），在训练集中样本比例<1%",
    "recommendations": [
      "建议重新拍摄舌象照片",
      "确保拍摄环境光照充足均匀",
      "请专业中医师进行当面诊断",
      "不要仅依赖AI分析结果"
    ]
  }
}
```

### 规则2: 特征互相矛盾

**检测条件示例**:
- 健康舌但同时存在多个病理特征
- 淡红舌预测置信度>0.9但绛紫舌置信度>0.5
- 正常舌形但胖大舌与瘦薄舌置信度相近

**异常原因**: 特征提取可能存在逻辑错误

**处理建议**:
```json
{
  "anomaly_detection": {
    "detected": true,
    "reason": "舌象特征之间存在逻辑矛盾，建议人工审核识别结果",
    "recommendations": [
      "检查AI模型识别结果",
      "对比多个舌象照片进行验证"
    ]
  }
}
```

### 规则3: 图像质量问题

**检测条件**:
- 模型检测到图像模糊、光照异常
- 遮挡比例>30%（阴影、反光等）
- 特征提取整体置信度<0.5

**异常原因**: 输入图像质量不足影响识别

**处理建议**:
```json
{
  "anomaly_detection": {
    "detected": true,
    "reason": "图像质量可能影响特征识别（模糊/光照/遮挡），建议改善拍摄条件",
    "recommendations": [
      "在自然光下拍摄",
      "避免使用闪光灯",
      "保持舌头自然伸出",
      "拍摄多张照片选择最佳"
    ]
  }
}
```

### 规则4: 特征提取失败

**检测条件**:
- 主要分类head（舌色、苔色）的置信度均<0.5
- 无法确定主导特征

**异常原因**: 模型无法可靠提取舌象特征

**处理建议**:
```json
{
  "anomaly_detection": {
    "detected": true,
    "reason": "特征提取置信度普遍较低（<0.5），无法进行可靠诊断",
    "recommendations": [
      "请专业中医师进行当面诊断",
      "不建议继续使用AI辅助工具"
    ]
  }
}
```

### 规则5: 健康与病理并存

**检测条件**:
- 健康舌置信度>0.7
- 同时存在2个以上病理特征的置信度>0.6

**异常原因**: 健康评估与其他特征诊断冲突

**处理建议**:
```json
{
  "anomaly_detection": {
    "detected": true,
    "reason": "健康舌评估与病理特征并存，建议人工审核",
    "recommendations": [
      "综合评估整体舌象",
      "结合其他症状进行判断",
      "如有疑问请咨询专业医生"
    ]
  }
}
```

## 中医辨证理论参考

### 舌色辨证

| 舌色 | 主证 | 兼证 | 中医理论依据 |
|--------|-------|-------|---------------|
| 淡红舌 | 气血调和 | 正常或轻证 | 气血充盈，舌色红润 |
| 红舌 | 热证 | 实热/虚热 | 热盛营血，舌色红赤 |
| 绛紫舌 | 热盛/血瘀 | 气滞血瘀 | 热毒内蕴或气血瘀滞 |
| 淡白舌 | 气血两虚 | 阳虚/血虚 | 气血不足，舌色淡白 |

### 苔色辨证

| 苔色 | 主证 | 兼证 | 中医理论依据 |
|--------|-------|-------|---------------|
| 白苔 | 表证/寒证 | 虚寒/阳虚 | 舌苔薄白，多为表证或虚寒 |
| 黄苔 | 里证/热证 | 湿热/脾胃热 | 舌苔黄，主热证或里热 |
| 黑苔 | 里寒/肾虚 | 肾阳虚衰 | 舌苔黑而润滑，主肾阳虚衰 |
| 花剥苔 | 胃阴伤/肝肾阴虚 | 阴虚/血虚 | 苔剥落如地图，多为胃阴伤 |

### 舌形辨证

| 舌形 | 主证 | 兼证 | 中医理论依据 |
|--------|-------|-------|---------------|
| 正常 | 气血调和 | 无 | 舌体适中，活动自如 |
| 胖大舌 | 脾虚/湿盛 | 阳虚水肿 | 舌体胖大，多为脾虚湿盛 |
| 瘦薄舌 | 气血两虚 | 阴虚火旺 | 舌体瘦薄，多为气血两虚 |

### 苔质辨证

| 苔质 | 主证 | 兼证 | 中医理论依据 |
|--------|-------|-------|---------------|
| 薄苔 | 胃气充盈/表证 | 正常 | 苔薄白而润，为正常胃气 |
| 厚苔 | 里证/湿盛 | 痰饮/食积 | 苔厚腻，主湿盛或食积 |
| 腻苔 | 湿热困脾 | 湿热/湿热 | 苔质腐腻，主湿热困脾 |

### 特殊特征辨证

| 特征 | 主证 | 中医理论依据 |
|--------|-------|---------------|
| 红点 | 热毒蕴结 | 热邪内蕴，迫血外溢 |
| 裂纹 | 阴血不足/血瘀 | 舌体失养，血行不畅 |
| 齿痕 | 脾虚湿盛 | 脾虚不能摄血，湿邪内阻 |

## Prompt 优化策略

### 策略1: 结构化输出

使用清晰的JSON结构，避免LLM自由发挥：
- 在System Prompt中明确定义JSON schema
- 提供输出示例（正常/异常情况）
- 要求LLM"必须"遵循schema

### 策略2: 约束强度

使用多层约束确保安全性：
1. **核心约束**: 医疗安全边界（不可违反）
2. **输出约束**: JSON格式要求
3. **诊断约束**: 诊断原则和辨证理论
4. **异常约束**: 异常检测规则

### 策略3: 示例驱动

提供详细示例：
- 正常舌象示例
- 常见证型示例
- 异常情况示例
- 每个示例包含完整JSON输出

### 策略4: 引导性语言

使用引导性而非指令性语言：
- "请分析..."而非"你必须..."
- "建议..."而非"要求..."
- "考虑..."而非"认定..."

## 输出质量保证

### 自动验证检查

在返回用户之前，LLM应自检：
1. JSON格式正确
2. 所有必需字段存在
3. confidence值在合理范围
4. 枚举值在有效列表内
5. 异常检测逻辑正确执行

### 降级处理

当检测到异常时：
1. 明确标记`anomaly_detected=true`
2. 说明异常原因
3. 提供具体处理建议
4. 强化免责声明
5. 建议专业医生介入

## 使用指南

### 集成方式

在API服务中集成System Prompt：

```python
import yaml

with open('api_service/prompts/system_prompt.txt', 'r', encoding='utf-8') as f:
    SYSTEM_PROMPT = f.read()

# 在调用文心API时使用
response = wenxin_api.chat(
    messages=[
        {"role": "user", "content": user_query},
        {"role": "assistant", "content": SYSTEM_PROMPT}
    ]
)
```

### 版本管理

System Prompt版本规则：
- 主版本号：重大架构变更
- 次版本号：新增规则或字段
- 修订号：bug修复或文字优化

当前版本：v1.0.0

### 持续优化

基于以下情况持续优化：
- 用户反馈（错误输出、遗漏字段）
- 医生审核意见
- 新的异常案例
- 诊断准确度监控

---

**文档维护**: Ralph Agent
**最后更新**: 2026-02-12
**审核状态**: 待医疗合规审查
