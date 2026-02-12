# AI舌诊智能诊断系统 - API服务

基于FastAPI的舌诊AI系统RESTful API服务。

## 功能特点

- **舌体分割**: 使用BiSeNetV2模型进行精确的舌体区域提取
- **特征分类**: 使用PP-HGNetV2-B4模型进行多维度舌象特征识别
- **端到端诊断**: 完整的分割+分类+LLM诊断流程
- **便捷上传**: 支持multipart/form-data文件上传
- **自动文档**: Swagger/OpenAPI自动生成API文档

## 安装

### 1. 安装依赖

```bash
cd api_service
pip install -r requirements.txt
```

### 2. 配置环境变量

复制`.env.example`为`.env`并配置：

```bash
cp .env.example .env
```

关键配置项：
- `SEGMENT_MODEL_PATH`: 分割模型路径
- `CLASSIFY_MODEL_PATH`: 分类模型路径
- `BAIDU_API_KEY`: 文心一言API密钥（如需LLM诊断）
- `BAIDU_SECRET_KEY`: 文心一言密钥

### 3. 启动服务

```bash
python -m api_service.app.main
```

服务将启动在 `http://localhost:8000`

## API文档

启动服务后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API端点

### 健康检查

```
GET /api/v1/health
GET /health
```

返回服务状态和模型加载情况。

### 舌体分割

```
POST /api/v1/segment
```

**请求体**:
```json
{
  "image": "base64_encoded_image_data",
  "image_id": "optional_image_id",
  "return_overlay": true,
  "return_mask": true
}
```

**响应**:
```json
{
  "success": true,
  "result": {
    "mask": "base64_encoded_mask",
    "overlay": "base64_encoded_overlay",
    "tongue_area": 150000,
    "tongue_ratio": 0.35,
    "inference_time_ms": 45.2
  }
}
```

### 舌象分类

```
POST /api/v1/classify
```

**请求体**:
```json
{
  "image": "base64_encoded_image_data",
  "image_id": "optional_image_id",
  "crop_to_tongue": true
}
```

**响应**:
```json
{
  "success": true,
  "result": {
    "tongue_color": {
      "prediction": "淡红舌",
      "confidence": 0.85,
      "description": "气血调和"
    },
    "coating_color": {...},
    "tongue_shape": {...},
    "coating_quality": {...},
    "special_features": {
      "red_dots": {"present": false, "confidence": 0.0},
      "cracks": {"present": false, "confidence": 0.0},
      "teeth_marks": {"present": false, "confidence": 0.0}
    },
    "health_status": {...}
  },
  "inference_time_ms": 98.5
}
```

### 端到端诊断

```
POST /api/v1/diagnosis
```

**请求体**:
```json
{
  "image": "base64_encoded_image_data",
  "image_id": "optional_image_id",
  "user_info": {
    "age": 35,
    "gender": "女",
    "symptoms": ["乏力", "食欲不振"],
    "chief_complaint": "感觉疲劳"
  },
  "enable_llm_diagnosis": true,
  "enable_rule_fallback": true
}
```

**响应**:
```json
{
  "success": true,
  "segmentation": {...},
  "classification": {...},
  "diagnosis": {
    "syndrome_analysis": {...},
    "anomaly_detection": {...},
    "health_recommendations": {...},
    "confidence_analysis": {...},
    "disclaimer": {...}
  },
  "inference_time_ms": 245.8,
  "timing_breakdown": {
    "segmentation_ms": 45.2,
    "classification_ms": 98.5,
    "llm_ms": 102.1
  }
}
```

### 文件上传（便捷接口）

```
POST /api/v1/upload/segment
POST /api/v1/upload/classify
POST /api/v1/upload/diagnosis
```

使用multipart/form-data直接上传文件。

## 项目结构

```
api_service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI主应用
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           └── endpoints.py    # API端点定义
├── core/
│   ├── __init__.py
│   ├── config.py            # 配置管理
│   └── logging_config.py    # 日志配置
├── models/
│   ├── __init__.py
│   └── predictors.py       # 模型预测器包装
├── schemas/
│   ├── __init__.py
│   └── schemas.py          # Pydantic请求/响应模型
├── prompts/
│   ├── system_prompt.txt     # System Prompt
│   ├── few_shot_examples.json
│   └── user_prompt_template.py
├── config/
│   └── wenxin_config.yaml
├── requirements.txt
├── .env.example
└── README.md
```

## 开发

### 运行开发服务器

```bash
python -m api_service.app.main
```

启用热重载：
```bash
uvicorn api_service.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 测试

```bash
pytest api_service/tests/
```

## 配置说明

### 环境变量

主要配置项（见`.env.example`）：

- `API_HOST`: API监听地址（默认: 0.0.0.0）
- `API_PORT`: API监听端口（默认: 8000）
- `DEBUG`: 调试模式（默认: false）
- `ENABLE_API_DOCS`: 启用API文档（默认: true）

### 模型配置

- `SEGMENT_MODEL_PATH`: 分割模型权重路径
- `CLASSIFY_MODEL_PATH`: 分类模型权重路径
- `USE_FP16`: 使用FP16推理（默认: true）
- `INFERENCE_DEVICE`: 推理设备（cpu/gpu）

### 文心API配置

- `BAIDU_API_KEY`: 百度云API密钥
- `BAIDU_SECRET_KEY`: 百度云密钥
- `WENXIN_MODEL`: 使用的模型（默认: ERNIE-Speed）
- `API_CALL_TIMEOUT`: API调用超时（默认: 10秒）

## 监控和日志

### 日志文件

- API日志: `logs/api_service.log`
- 审计日志: `logs/audit.log`

### 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

## Docker部署

```bash
docker build -t tongue-diagnosis-api .
docker run -p 8000:8000 tongue-diagnosis-api
```

## 性能优化

- 使用FP16量化模型减少内存占用
- 启用GPU加速（需CUDA环境）
- 配置Redis缓存减少重复推理
- 使用异步任务队列（Celery）

## 安全注意事项

1. 生产环境设置 `DEBUG=false`
2. 配置正确的CORS源
3. 使用HTTPS部署
4. 配置API密钥认证
5. 定期清理敏感日志

## 故障排除

### 模型加载失败

检查模型路径是否正确：
```bash
ls models/deploy/segment_fp16/
ls models/deploy/classify_fp16/
```

### CUDA不可用

如使用CPU推理，设置：
```
INFERENCE_DEVICE=cpu
```

### API调用超时

增加文心API超时时间：
```
API_CALL_TIMEOUT=30
```

## 许可证

[根据项目实际情况填写]
