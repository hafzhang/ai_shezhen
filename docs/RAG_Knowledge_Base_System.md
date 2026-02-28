# RAG向量知识库系统 - 完整实现方案

## 系统概述

RAG (Retrieval-Augmented Generation) 向量知识库系统为舌诊智能诊断提供深度中医知识支撑，结合大语言模型进行专业分析，并支持详细的PDF报告生成与下载。

## 架构设计

```
舌诊图像识别
    ↓
特征提取 (舌色/苔色/舌形/特殊特征)
    ↓
向量知识库检索
    ├─ 中医理论知识
    ├─ 舌诊诊断理论
    ├─ 证型分析理论
    ├─ 健康指导建议
    ├─ 临床案例研究
    └─ 中药知识库
    ↓
大语言模型深度分析 (智谱AI GLM-4)
    ├─ 舌象特征解读
    ├─ 证型辨证分析
    ├─ 中医理论解释
    └─ 个性化健康建议
    ↓
PDF报告生成与下载
    ├─ 详细的舌象分析
    ├─ 专业证型诊断
    ├─ 个性化养生建议
    ├─ 风险评估报告
    └─ 参考文献引用
```

## 核心组件

### 1. 向量数据库 (Vector Database)

**技术选型**: ChromaDB / FAISS / Pinecone

**功能**:
- 存储和索引中医知识文档
- 支持语义搜索和相似度匹配
- 高效的向量嵌入和检索

**支持的向量嵌入模型**:
- sentence-transformers (本地)
- OpenAI text-embedding-ada-002 (云服务)

### 2. 知识库分类

系统包含6大知识类别：

| 类别 | 说明 | 文档数量 |
|------|------|----------|
| 中医理论 | 基础理论、舌诊原理 | 4个 |
| 舌诊理论 | 舌色/苔色/舌形分析 | 6个 |
| 证型分析 | 各证型的舌象特征与治疗 | 4个 |
| 健康指导 | 饮食/运动/情绪调理 | 4个 |
| 案例研究 | 临床诊断案例 | 2个 |
| 中药知识 | 常用中药理论 | 3个 |

### 3. RAG流水线 (RAG Pipeline)

**检索阶段**:
1. 基于舌象特征生成查询
2. 向量检索相关文档
3. 应用过滤条件 (类别、相似度阈值)
4. 排序和选择最相关文档

**生成阶段**:
1. 构建包含检索文档的上下文
2. 调用大语言模型进行深度分析
3. 生成结构化的JSON格式诊断结果
4. 提供推理过程和参考来源

### 4. PDF报告生成

**报告结构**:
1. **报告头部**
   - 患者基本信息
   - 报告生成时间

2. **舌象特征分析**
   - 舌色分析与中医理论解释
   - 苔色分析与临床意义
   - 舌形分析与体质关系
   - 特殊特征分析

3. **证型诊断**
   - 主要证型 (置信度)
   - 次要证型
   - 诊断依据
   - 详细中医理论解释

4. **健康调理建议**
   - 饮食指导 (原则/推荐/禁忌/季节建议)
   - 生活方式 (运动/睡眠/日常/环境)
   - 情绪调节 (情绪管理/压力管理/正念练习)

5. **风险评估**
   - 当前健康状态
   - 潜在风险因素
   - 改善建议

6. **医学免责声明**
   - 重要医疗免责条款
   - 版权信息

## API端点

### 知识库管理

```
POST /api/v2/rag/knowledge-base/documents
- 添加单个文档到知识库

POST /api/v2/rag/knowledge-base/upload
- 上传文件到知识库

POST /api/v2/rag/knowledge-base/batch
- 批量添加文档

GET /api/v2/rag/knowledge-base/stats
- 获取知识库统计信息

DELETE /api/v2/rag/knowledge-base/reset
- 重置知识库
```

### 知识检索

```
POST /api/v2/rag/search
- 搜索知识库
- 参数: query, top_k, category, min_similarity
```

### RAG分析

```
POST /api/v2/rag/analyze
- 执行RAG深度分析
- 参数: query, tongue_features, user_info, top_k, category
- 返回: 完整的诊断分析结果 (JSON格式)
```

### PDF报告

```
POST /api/v2/rag/report/generate
- 生成PDF报告
- 参数: diagnosis_data, user_info, filename

GET /api/v2/rag/report/list
- 列出可用的PDF报告

GET /api/v2/rag/report/download/{filename}
- 下载PDF报告
```

## 数据结构

### 诊断结果JSON格式

```json
{
  "tongue_analysis": {
    "tongue_color": {
      "observation": "观察到的舌色特征",
      "tcm_interpretation": "中医理论解释",
      "clinical_significance": "临床意义"
    },
    "coating_analysis": {
      "observation": "观察到的苔色特征",
      "tcm_interpretation": "中医理论解释",
      "clinical_significance": "临床意义"
    },
    "tongue_shape_analysis": {
      "observation": "观察到的舌形特征",
      "tcm_interpretation": "中医理论解释",
      "clinical_significance": "临床意义"
    },
    "special_features_analysis": {
      "observations": ["特殊特征1", "特殊特征2"],
      "tcm_interpretation": "综合中医理论解释",
      "clinical_significance": "综合临床意义"
    }
  },
  "syndrome_diagnosis": {
    "primary_syndrome": "主要证型",
    "secondary_syndromes": ["次要证型1", "次要证型2"],
    "confidence": 0.85,
    "diagnosis_basis": "诊断依据",
    "tcm_theory_explanation": "详细中医理论解释"
  },
  "health_recommendations": {
    "dietary_guidance": {
      "principle": "饮食调理原则",
      "recommended_foods": ["推荐食物1", "推荐食物2"],
      "avoid_foods": ["禁忌食物1", "禁忌食物2"],
      "seasonal_advice": "季节性建议"
    },
    "lifestyle_guidance": {
      "exercise": ["运动建议1", "运动建议2"],
      "sleep": "睡眠作息建议",
      "daily_routine": "日常生活建议",
      "environment": "生活环境建议"
    },
    "emotional_guidance": {
      "mood_regulation": "情绪调节建议",
      "stress_management": "压力管理方法",
      "mindfulness": "正念练习建议"
    }
  },
  "risk_assessment": {
    "current_health_status": "当前健康状态评估",
    "potential_risks": ["潜在风险1", "潜在风险2"],
    "recommendations": ["建议1", "建议2"]
  },
  "references_used": [
    "参考的知识来源1",
    "参考的知识来源2"
  ],
  "medical_disclaimer": "重要医学免责声明"
}
```

## 使用流程

### 1. 初始化知识库

```bash
# 运行知识库初始化脚本
python init_rag_knowledge_base.py
```

### 2. 添加自定义知识

```bash
# 通过API添加文档
curl -X POST http://192.168.51.194:8000/api/v2/rag/knowledge-base/documents \
  -H "Content-Type: application/json" \
  -d '{
    "text": "您的中医知识内容",
    "metadata": {"source": "自定义来源"},
    "category": "tcm_theory"
  }'
```

### 3. 执行RAG分析

```bash
# 通过API进行深度分析
curl -X POST http://192.168.51.194:8000/api/v2/rag/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query": "舌色红，苔黄腻，舌尖红点",
    "tongue_features": {
      "tongue_color": "红舌",
      "coating_color": "黄腻苔",
      "special_features": ["舌尖红点"]
    },
    "user_info": {
      "name": "张三",
      "age": 35,
      "gender": "male"
    },
    "top_k": 5,
    "category": "tongue_diagnosis"
  }'
```

### 4. 生成PDF报告

```bash
# 通过API生成PDF报告
curl -X POST http://192.168.51.194:8000/api/v2/rag/report/generate \
  -H "Content-Type: application/json" \
  -d '{
    "diagnosis_data": {...诊断数据...},
    "user_info": {
      "name": "张三",
      "age": 35,
      "gender": "male"
    },
    "filename": "tongue_diagnosis_report.pdf"
  }'
```

### 5. 下载PDF报告

```bash
# 通过API下载PDF报告
curl -O http://192.168.51.194:8000/api/v2/rag/report/download/tongue_diagnosis_report.pdf
```

## 系统配置

### .env配置

```env
# 向量数据库配置
VECTOR_DB_TYPE=chroma
VECTOR_DB_PATH=api_service/data/vector_db
COLLECTION_NAME=tcm_knowledge_base

# 嵌入模型配置
LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384

# RAG配置
RAG_LLM_PROVIDER=zhipu
RAG_LLM_MODEL=glm-4-plus
RAG_LLM_TEMPERATURE=0.3
RAG_LLM_MAX_TOKENS=4000
TOP_K_RESULTS=5
MIN_SIMILARITY_SCORE=0.6

# PDF报告配置
PDF_REPORT_PATH=api_service/data/reports
```

## 依赖安装

```bash
# 核心依赖
pip install chromadb
pip install sentence-transformers
pip install reportlab

# 可选依赖 (如果使用其他向量数据库)
pip install faiss-cpu
pip install pinecone-client

# LLM依赖
pip install httpx
```

## 文件结构

```
AI_shezhen/
├── api_service/
│   ├── core/
│   │   ├── rag_config.py          # RAG配置
│   │   ├── vector_db.py            # 向量数据库管理
│   │   ├── rag_pipeline.py         # RAG流水线
│   │   └── pdf_generator.py        # PDF报告生成
│   ├── app/api/v2/
│   │   └── rag.py                   # RAG API端点
│   └── data/
│       ├── vector_db/              # 向量数据库存储
│       └── reports/                # PDF报告存储
├── docs/
│   └── RAG_Knowledge_Base_System.md  # RAG系统文档
└── init_rag_knowledge_base.py        # 知识库初始化脚本
```

## 特性优势

### 1. 智能检索
- 基于语义相似度的精准匹配
- 支持多维度过滤 (类别、相似度)
- 高效的向量索引和检索

### 2. 深度分析
- 结合中医理论和临床案例
- 大语言模型生成专业解释
- 提供推理过程和参考来源

### 3. 专业报告
- 结构化PDF格式
- 完整的诊断分析
- 个性化健康建议

### 4. 持续学习
- 支持动态添加知识
- 多种知识类别管理
- 知识库统计和监控

## 应用场景

### 1. 深度舌诊诊断
- 基于舌象特征的深度分析
- 结合中医理论的证型辨证
- 提供详细的病理解释

### 2. 个性化健康指导
- 基于体质的饮食建议
- 生活方式改善指导
- 情绪调节方法推荐

### 3. 健康风险评估
- 识别潜在健康风险
- 提供预防性建议
- 长期健康监测

### 4. 教育和研究
- 中医知识普及
- 临床案例学习
- 研究数据支持

## 安全注意事项

1. **医疗免责**: 系统分析仅提供中医调理建议，不能替代专业医疗诊断
2. **数据隐私**: 用户数据和诊断结果需要加密存储
3. **内容审核**: 知识库内容需要专业审核
4. **使用限制**: 明确使用范围和限制

## 下一步

1. 安装依赖包
2. 初始化知识库
3. 启动API服务
4. 测试RAG分析功能
5. 验证PDF报告生成

通过这个RAG向量知识库系统，用户可以获得：
- 更深度的舌诊专业分析
- 基于中医理论的知识支撑
- 详细的个性化PDF报告
- 可下载的专业诊断文档