# User Prompt Field Mapping Documentation

## Overview

This document describes the field mapping between the classification model outputs and the User Prompt template used for LLM diagnosis.

## Model Output Fields

### ClassificationResult Structure

The classification model output has the following structure:

```python
{
    "tongue_color": {
        "prediction": str,      # Predicted tongue color
        "confidence": float,    # Confidence score [0, 1]
        "description": str      # Feature description
    },
    "coating_color": {
        "prediction": str,
        "confidence": float,
        "description": str
    },
    "tongue_shape": {
        "prediction": str,
        "confidence": float,
        "description": str
    },
    "coating_quality": {
        "prediction": str,
        "confidence": float,
        "description": str
    },
    "special_features": {
        "red_dots": {
            "present": bool,
            "confidence": float,
            "description": str
        },
        "cracks": {
            "present": bool,
            "confidence": float,
            "description": str
        },
        "teeth_marks": {
            "present": bool,
            "confidence": float,
            "description": str
        }
    },
    "health_status": {
        "prediction": str,
        "confidence": float,
        "description": str
    },
    "raw_scores": {  # Optional
        "tongue_color": List[float],
        "coating_color": List[float],
        # ... other raw scores
    }
}
```

## Field Mappings

### 1. Tongue Color (舌色)

| Index | Prediction | Description |
|-------|-----------|-------------|
| 0     | 淡红舌 (Normal Red) | 舌色淡红，气血调和，多为正常或轻症 |
| 1     | 红舌 (Red) | 舌色红，热证表现，实热或虚热 |
| 2     | 绛紫舌 (Crimson/Purple) | 舌色绛紫，热盛或气血瘀滞 |
| 3     | 淡白舌 (Pale White) | 舌色淡白，虚证表现，气血两虚或阳虚 |

### 2. Coating Color (苔色)

| Index | Prediction | Description |
|-------|-----------|-------------|
| 0     | 白苔 (White) | 苔色白，寒证、表证或虚寒 |
| 1     | 黄苔 (Yellow) | 苔色黄，里证、热证或脾胃湿热 |
| 2     | 黑苔 (Black) | 苔色黑，里寒极盛或肾气虚衰 |
| 3     | 花剥苔 (Peeling) | 苔色花剥，胃气阴伤或肝肾阴虚 |

### 3. Tongue Shape (舌形)

| Index | Prediction | Description |
|-------|-----------|-------------|
| 0     | 正常 (Normal) | 舌体适中，无异常 |
| 1     | 胖大舌 (Swollen) | 舌体胖大，脾虚、湿盛或阳虚水肿 |
| 2     | 瘦薄舌 (Thin) | 舌体瘦薄，气血两虚或阴虚火旺 |

### 4. Coating Quality (苔质)

| Index | Prediction | Description |
|-------|-----------|-------------|
| 0     | 薄苔 (Thin) | 苔质薄，胃气充盈或表证 |
| 1     | 厚苔 (Thick) | 苔质厚，里证、湿盛或食积 |
| 2     | 腐苔 (Curdy) | 苔质腐，胃气蕴热或食积 |
| 3     | 腻苔 (Greasy) | 苔质腻，湿热困脾或湿热 |

### 5. Special Features (特殊特征)

| Field | Name | Description |
|-------|------|-------------|
| red_dots | 红点 (Red Dots) | 红点为热毒蕴结或血热表现 |
| cracks | 裂纹 (Cracks) | 裂纹提示阴血不足或血瘀 |
| teeth_marks | 齿痕 (Teeth Marks) | 齿痕为脾虚湿盛表现 |

### 6. Health Status (健康状态)

| Prediction | Description |
|-----------|-------------|
| 健康舌 (Healthy) | 舌象整体正常，无明显病理特征 |
| 不健康舌 (Unhealthy) | 舌象显示异常征象 |

## UserInfo Structure

Optional user information that can be included in the prompt:

```python
{
    "age": int,              # Age in years
    "gender": str,           # Gender
    "symptoms": List[str],   # Self-reported symptoms
    "medical_history": List[str],  # Past medical history
    "chief_complaint": str   # Main complaint
}
```

## Template Selection Logic

The UserPromptBuilder automatically selects the appropriate template based on:

1. **Healthy Template**: Used when health_status is "健康舌" with confidence > 0.7
2. **Simplified Template**: Used when any feature has confidence < 0.5
3. **Base Template**: Default template for normal cases

## Prompt Variables

The following variables are dynamically filled in the template:

| Variable | Source | Format |
|----------|--------|--------|
| {tongue_color_prediction} | tongue_color.prediction | String |
| {tongue_color_confidence} | tongue_color.confidence | Percentage (e.g., 92%) |
| {tongue_color_description} | tongue_color.description | String |
| {coating_color_prediction} | coating_color.prediction | String |
| {coating_color_confidence} | coating_color.confidence | Percentage |
| {coating_color_description} | coating_color.description | String |
| {tongue_shape_prediction} | tongue_shape.prediction | String |
| {tongue_shape_confidence} | tongue_shape.confidence | Percentage |
| {tongue_shape_description} | tongue_shape.description | String |
| {coating_quality_prediction} | coating_quality.prediction | String |
| {coating_quality_confidence} | coating_quality.confidence | Percentage |
| {coating_quality_description} | coating_quality.description | String |
| {special_features_section} | special_features | Multi-line string |
| {health_status_prediction} | health_status.prediction | String |
| {health_status_confidence} | health_status.confidence | Percentage |
| {health_status_description} | health_status.description | String |
| {user_info_section} | user_info | Multi-line string |

## Usage Examples

### Example 1: Basic Usage

```python
from api_service.prompts.user_prompt_template import create_user_prompt

# Model output from classification
model_output = {
    "tongue_color": {"prediction": "淡红舌", "confidence": 0.92, "description": "舌色淡红，气血调和"},
    "coating_color": {"prediction": "白苔", "confidence": 0.88, "description": "苔色薄白"},
    "tongue_shape": {"prediction": "正常", "confidence": 0.90, "description": "舌形适中"},
    "coating_quality": {"prediction": "薄苔", "confidence": 0.85, "description": "苔质薄白"},
    "special_features": {
        "red_dots": {"present": False, "confidence": 0.0, "description": "无明显红点"},
        "cracks": {"present": False, "confidence": 0.0, "description": "无明显裂纹"},
        "teeth_marks": {"present": False, "confidence": 0.0, "description": "无明显齿痕"}
    },
    "health_status": {"prediction": "健康舌", "confidence": 0.91, "description": "舌象正常"}
}

# Generate user prompt
user_prompt = create_user_prompt(model_output)
```

### Example 2: With User Information

```python
user_info = {
    "age": 45,
    "gender": "男",
    "symptoms": ["疲劳", "失眠"],
    "medical_history": ["高血压"],
    "chief_complaint": "近期感觉疲劳乏力"
}

user_prompt = create_user_prompt(model_output, user_info=user_info)
```

### Example 3: Using Class Directly

```python
from api_service.prompts.user_prompt_template import UserPromptBuilder, ClassificationResult, UserInfo

# Create objects
result = ClassificationResult(
    tongue_color={"prediction": "淡白舌", "confidence": 0.85, "description": "气血不足"},
    coating_color={"prediction": "白苔", "confidence": 0.82, "description": "阳虚表现"},
    tongue_shape={"prediction": "胖大舌", "confidence": 0.88, "description": "脾肾阳虚"},
    coating_quality={"prediction": "薄苔", "confidence": 0.80, "description": "苔质薄白"},
    special_features={
        "red_dots": {"present": False, "confidence": 0.0, "description": ""},
        "cracks": {"present": False, "confidence": 0.0, "description": ""},
        "teeth_marks": {"present": True, "confidence": 0.75, "description": "脾虚表现"}
    },
    health_status={"prediction": "不健康舌", "confidence": 0.83, "description": "脾肾阳虚"}
)

info = UserInfo(age=50, gender="女", symptoms=["畏寒", "乏力"])

# Build prompt
builder = UserPromptBuilder()
prompt = builder.build_prompt(result, info)
```

## Validation

The prompt builder validates:

1. **Required fields**: All prediction fields must be present
2. **Confidence range**: Confidence values must be between 0 and 1
3. **Boolean fields**: Special feature `present` fields must be boolean
4. **Encoding**: All strings must be UTF-8 encoded

## Error Handling

- Missing fields: Uses default values ("未知", 0.0, "")
- Invalid confidence: Clamps to [0, 1] range
- Missing description: Uses default description from mapping
- None user_info: Returns "未提供用户信息"

## Integration with API Service

To integrate with the FastAPI service:

```python
from api_service.prompts.user_prompt_template import create_user_prompt
from api_service.prompts.system_prompt import load_system_prompt

# In your endpoint
async def diagnose(image_upload):
    # 1. Get classification result from model
    classification = await classify_image(image_upload)

    # 2. Build user prompt
    user_prompt = create_user_prompt(
        classification_result=classification,
        user_info=request.user_info
    )

    # 3. Load system prompt
    system_prompt = load_system_prompt()

    # 4. Call Wenxin API
    response = await wenxin_api.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    return response
```

## File Location

- Template Module: `api_service/prompts/user_prompt_template.py`
- This Documentation: `api_service/prompts/FIELD_MAPPING.md`
- System Prompt: `api_service/prompts/system_prompt.txt`
- Few-shot Examples: `api_service/prompts/few_shot_examples.json`
