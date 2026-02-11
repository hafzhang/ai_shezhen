# 百度AI服务API对接详解

## 一、账号注册与密钥获取

### 1.1 百度智能云账号注册

**步骤**：
1. 访问 https://cloud.baidu.com/
2. 点击"注册"按钮
3. 填写手机号、密码完成注册
4. 实名认证（个人/企业）

### 1.2 开通所需服务

#### 服务一：千帆大模型平台（文心一言）

**用途**：生成智能诊断建议

**开通步骤**：
```
1. 访问 https://qianfan.cloud.baidu.com/
2. 登录百度账号
3. 进入"控制台" → "应用列表"
4. 点击"创建应用"
5. 填写应用信息：
   - 应用名称：AI舌诊系统
   - 应用描述：用于舌诊健康建议
6. 创建成功后获取：
   - API Key
   - Secret Key
```

#### 服务二：图像识别服务（可选）

**用途**：图像分类、物体检测

**开通步骤**：
```
1. 访问 https://cloud.baidu.com/product/imagerecognition
2. 点击"立即使用"
3. 开通服务
4. 获取API密钥
```

#### 服务三：EasyDL（可选）

**用途**：定制化模型训练

**开通步骤**：
```
1. 访问 https://cloud.baidu.com/product/easydl
2. 选择"图像分类"
3. 创建数据集、训练模型
4. 发布为API服务
```

### 1.3 密钥配置

将获取的密钥保存到配置文件：

```json
{
  "baidu": {
    "api_key": "你的API Key",
    "secret_key": "你的Secret Key",
    "app_id": "你的应用ID"
  }
}
```

## 二、认证流程详解

### 2.1 OAuth 2.0认证

百度API使用OAuth 2.0认证，需要先获取Access Token。

**请求方式**：POST

**请求地址**：
```
https://aip.baidubce.com/oauth/2.0/token
```

**请求参数**：

| 参数 | 必填 | 类型 | 说明 |
|-----|-----|------|------|
| grant_type | 是 | string | 固定值"client_credentials" |
| client_id | 是 | string | API Key |
| client_secret | 是 | string | Secret Key |

**请求示例**：
```bash
curl -X POST "https://aip.baidubce.com/oauth/2.0/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=你的API Key" \
  -d "client_secret=你的Secret Key"
```

**返回示例**：
```json
{
  "access_token": "24.xxxxxxxx.xxxxxxx.xxxxxx",
  "expires_in": 2592000,
  "refresh_token": "25.xxxxxxxx.xxxxxx.xxxxxx",
  "session_key": "xxxxx",
  "scope": "public smart_app_speech"
}
```

**重要说明**：
- Access Token有效期为30天
- 过期后需要重新获取
- 建议缓存Token，避免频繁请求

### 2.2 Python实现认证

```python
import requests
import time
import json

class BaiduAuth:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.expires_at = 0
        self.token_file = "token_cache.json"

    def get_token(self):
        """获取Access Token，带缓存"""
        # 尝试从缓存读取
        if self._load_cached_token():
            if self.expires_at > time.time() + 300:  # 提前5分钟刷新
                return self.access_token

        # 获取新Token
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }

        response = requests.post(url, params=params)
        result = response.json()

        if "access_token" in result:
            self.access_token = result["access_token"]
            self.expires_at = time.time() + result["expires_in"]
            self._save_cached_token()
            return self.access_token
        else:
            raise Exception(f"获取Token失败: {result}")

    def _load_cached_token(self):
        """从缓存加载Token"""
        try:
            with open(self.token_file, 'r') as f:
                data = json.load(f)
                self.access_token = data.get("access_token")
                self.expires_at = data.get("expires_at", 0)
                return True
        except:
            return False

    def _save_cached_token(self):
        """保存Token到缓存"""
        with open(self.token_file, 'w') as f:
            json.dump({
                "access_token": self.access_token,
                "expires_at": self.expires_at
            }, f)


# 使用示例
auth = BaiduAuth("你的API Key", "你的Secret Key")
token = auth.get_token()
print(f"Access Token: {token}")
```

## 三、文心一言API详解

### 3.1 API端点

**可用的文心模型**：

| 模型 | 端点 | 特点 | 适用场景 |
|-----|------|------|---------|
| ERNIE-Bot 4.0 | /chat/ernie-4.0-8k | 最强能力 | 复杂推理 |
| ERNIE-Bot 3.5 | /chat/ernie-3.5-8k | 性价比高 | 通用对话 |
| ERNIE-Speed | /chat/ernie-speed | 响应快速 | 实时交互 |
| ERNIE-Tiny | /chat/ernie-tiny | 轻量级 | 移动端 |

**完整URL格式**：
```
https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/[模型端点]?access_token=[TOKEN]
```

### 3.2 请求参数

**公共参数**：

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| messages | 数组 | 是 | 对话消息列表 |
| temperature | 数字 | 否 | 温度参数(0-1)，控制随机性 |
| top_p | 数字 | 否 | 核采样参数(0-1) |
| penalty_score | 数字 | 否 | 重复惩罚(1-2) |
| stream | 布尔 | 否 | 是否流式输出 |
| user_id | 字符串 | 否 | 用户标识 |

**messages格式**：
```json
{
  "messages": [
    {"role": "user", "content": "用户消息"},
    {"role": "assistant", "content": "助手回复"},
    {"role": "user", "content": "新的用户消息"}
  ]
}
```

### 3.3 舌诊场景的提示词设计

**系统角色设定**：
```
你是一位经验丰富的中医医师，擅长通过舌象分析健康状况。
请根据用户提供的舌象特征，给出专业的分析和调理建议。
注意：你的建议仅供参考，不能替代专业医师的诊断。
```

**分析提示词模板**：
```
请根据以下舌象分析结果，给出中医健康评估：

舌象特征：
- 舌质颜色：{tongue_color}
- 舌苔情况：{coating}
- 舌形形态：{shape}
- 其他特征：{other_features}

请按以下格式回复：
1. 舌象分析（解释各特征的意义）
2. 综合判断（可能的体质或证型）
3. 调理建议（饮食、作息、运动等）
4. 注意事项（提醒就医的情况）
```

### 3.4 完整调用示例

```python
import requests
import json

class ErnieBot:
    def __init__(self, api_key, secret_key, model="ernie-speed"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.model = model
        self.auth = BaiduAuth(api_key, secret_key)
        self.base_url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop"

    def chat(self, messages, temperature=0.7, top_p=0.9):
        """发送对话请求"""
        token = self.auth.get_token()
        url = f"{self.base_url}/chat/{self.model}"

        headers = {"Content-Type": "application/json"}
        data = {
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p
        }
        params = {"access_token": token}

        response = requests.post(url, headers=headers, json=data, params=params)
        return response.json()

    def analyze_tongue(self, tongue_features):
        """分析舌象特征"""
        system_prompt = """你是一位经验丰富的中医医师，擅长通过舌象分析健康状况。
请根据用户提供的舌象特征，给出专业的分析和调理建议。
注意：你的建议仅供参考，不能替代专业医师的诊断。"""

        user_prompt = f"""请根据以下舌象分析结果，给出中医健康评估：

舌象特征：
- 舌质颜色：{tongue_features.get('tongue_color', '未知')}
- 舌苔情况：{tongue_features.get('coating', '未知')}
- 舌形形态：{tongue_features.get('shape', '未知')}
- 其他特征：{tongue_features.get('other', '无')}

请按以下格式回复：
1. 舌象分析（解释各特征的意义）
2. 综合判断（可能的体质或证型）
3. 调理建议（饮食、作息、运动等）
4. 注意事项（提醒就医的情况）"""

        messages = [
            {"role": "user", "content": system_prompt + "\n\n" + user_prompt}
        ]

        result = self.chat(messages)

        if "result" in result:
            return result["result"]
        else:
            return f"分析失败: {result}"


# 使用示例
ernie = ErnieBot("你的API Key", "你的Secret Key")

# 模拟舌象分析结果
tongue_result = {
    "tongue_color": "红舌",
    "coating": "薄黄苔",
    "shape": "舌尖有红点",
    "other": "舌体略干"
}

# 获取诊断建议
suggestion = ernie.analyze_tongue(tongue_result)
print(suggestion)
```

## 四、图像识别API详解

### 4.1 通用物体识别

**API地址**：
```
https://aip.baidubce.com/rest/2.0/image-classify/v1/advanced_general
```

**请求参数**：

| 参数 | 必填 | 类型 | 说明 |
|-----|-----|------|------|
| image | 是 | string | 图像base64编码 |
| baike_num | 否 | number | 返回百科信息数量 |

**请求示例**：
```python
def classify_image(image_path, access_token):
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()

    url = "https://aip.baidubce.com/rest/2.0/image-classify/v1/advanced_general"
    params = {"access_token": access_token}
    data = {"image": image_data}

    response = requests.post(url, params=params, data=data)
    return response.json()
```

### 4.2 EasyDL自定义模型API

**预测API格式**：
```
https://aip.baidubce.com/rpc/2.0/ai_custom/v1/classification/[模型ID]
```

**使用步骤**：
1. 在EasyDL训练模型
2. 发布模型获取API地址和模型ID
3. 使用模型ID调用预测接口

**请求示例**：
```python
def predict_with_easydl(image_path, model_id, access_token):
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()

    url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/classification/{model_id}"
    params = {"access_token": access_token}
    data = {"image": image_data}

    response = requests.post(url, params=params, json=data)
    return response.json()
```

## 五、PaddlePaddle本地部署

### 5.1 环境安装

```bash
# CPU版本
pip install paddlepaddle==2.6.0

# GPU版本（CUDA 11.2）
pip install paddlepaddle-gpu==2.6.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu112/

# 图像分割套件
pip install paddleseg

# 图像分类套件
pip install paddleclas
```

### 5.2 PaddleSeg图像分割

**使用预训练模型**：
```python
from paddleseg import PaddleSegModel

# 初始化模型
model = PaddleSegModel(
    model_type='seg',  # 分割模型
    backbone='hrnet_w18_small',  # 骨干网络
    num_classes=2  # 类别数（舌体/背景）
)

# 预测
result = model.predict('tongue_image.jpg')

# 可视化
model.visualize('tongue_image.jpg', result, 'output.png')
```

### 5.3 PaddleClas图像分类

**使用预训练模型**：
```python
from paddleclas import PaddleClas

# 初始化分类器
clas = PaddleClas(
    model_name='ResNet50',  # 模型名称
    use_gpu=False  # 是否使用GPU
)

# 预测
result = clas.predict('tongue_image.jpg')

# 输出结果
for item in result:
    print(f"类别: {item['class_name']}")
    print(f"置信度: {item['score']}")
```

### 5.4 自定义训练

**数据准备**：
```
data/
├── train/
│   ├── 淡白舌/
│   ├── 红舌/
│   └── ...
└── val/
    ├── 淡白舌/
    ├── 红舌/
    └── ...
```

**训练配置**（config.yaml）：
```yaml
model:
  name: ResNet50
  num_classes: 5

data:
  train_dir: data/train
  val_dir: data/val
  batch_size: 32
  image_size: 224

optimizer:
  name: Adam
  learning_rate: 0.001

train:
  epochs: 50
  save_dir: output/
```

**训练命令**：
```bash
python train.py --config config.yaml
```

## 六、错误处理与调试

### 6.1 常见错误码

| 错误码 | 说明 | 解决方法 |
|-------|------|---------|
| 1 | API Key不存在 | 检查API Key是否正确 |
| 2 | API Key已过期 | 重新申请密钥 |
| 3 | 调用次数超限 | 检查账户余额或升级套餐 |
| 18 | QPS超限 | 降低请求频率 |
| 19 | 请求过长 | 减少请求内容 |
| 110 | Access Token无效 | 重新获取Token |
| 111 | Access Token过期 | 刷新Token |
| 282000 | 内部错误 | 重试或联系客服 |

### 6.2 错误处理示例

```python
class APIError(Exception):
    """API错误"""
    pass

def safe_api_call(func):
    """API调用装饰器，处理常见错误"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            return None
        except KeyError as e:
            print(f"响应格式错误: {e}")
            return None
        except Exception as e:
            print(f"未知错误: {e}")
            return None
    return wrapper

@safe_api_call
def call_ernie_api(messages):
    """带错误处理的API调用"""
    # 实际调用逻辑
    pass
```

### 6.3 调试技巧

**1. 开启详细日志**：
```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

**2. 保存请求响应**：
```python
def debug_request(url, data):
    """调试请求"""
    print(f"请求URL: {url}")
    print(f"请求数据: {json.dumps(data, ensure_ascii=False)[:200]}...")

    response = requests.post(url, json=data)

    print(f"响应状态: {response.status_code}")
    print(f"响应内容: {response.text[:500]}...")

    return response
```

**3. 使用测试工具**：
- Postman：测试API接口
- API Explorer：百度提供的在线测试工具

## 七、性能优化建议

### 7.1 减少API调用成本

**1. 结果缓存**：
```python
import hashlib

def cache_key(image_data):
    """生成缓存键"""
    return hashlib.md5(image_data).hexdigest()

# 使用Redis等缓存结果
cached_result = cache.get(cache_key(image_data))
if cached_result:
    return cached_result
```

**2. 批量处理**：
```python
def batch_analyze(images):
    """批量分析"""
    results = []
    for img in images:
        result = analyze_image(img)
        results.append(result)
    return results
```

**3. 本地预处理**：
- 图像压缩后上传
- 裁剪无用区域
- 使用本地模型做初步筛选

### 7.2 提高响应速度

**1. 使用更快的模型**：
- ERNIE-Speed 替代 ERNIE-Bot 4.0
- 使用量化模型

**2. 异步调用**：
```python
import asyncio

async def async_analyze(images):
    """异步分析多个图片"""
    tasks = [analyze_image(img) for img in images]
    results = await asyncio.gather(*tasks)
    return results
```

**3. 连接池**：
```python
session = requests.Session()
# 复用连接，减少握手开销
```

## 八、费用与配额

### 8.1 文心一言计费

| 模型 | 价格（元/千Token） | 免费额度 |
|-----|-------------------|---------|
| ERNIE-Bot 4.0 | 0.120 | - |
| ERNIE-Bot 3.5 | 0.012 | 100万Token/月 |
| ERNIE-Speed | 0.004 | 100万Token/月 |
| ERNIE-Tiny | 0.0008 | 200万Token/月 |

**估算**：
- 简单诊断：约500-1000 Token
- 每次成本：0.002-0.12元
- 月度（1000次）：2-120元

### 8.2 免费额度获取

**新用户**：
- 注册即送免费额度
- 完成认证增加额度
- 参与活动获得额外额度

**学生认证**：
- 学生可获得更多免费资源

## 九、安全注意事项

### 9.1 密钥安全

```
⚠️ 重要提示：
1. 不要将API Key提交到公开仓库
2. 使用环境变量存储密钥
3. 定期轮换密钥
4. 设置IP白名单限制
```

### 9.2 数据安全

```
✅ 建议措施：
1. 敏感数据脱敏处理
2. 使用HTTPS加密传输
3. 不存储用户原图
4. 遵守隐私保护法规
```

## 十、参考资源

**官方文档**：
- 千帆大模型平台：https://cloud.baidu.com/doc/WENXINWORKSHOP/
- EasyDL：https://cloud.baidu.com/doc/EASYDL/
- PaddlePaddle：https://www.paddlepaddle.org.cn/

**SDK下载**：
- Python SDK：pip install baidu-aip
- Java/Go/PHP等：查看官方文档

**社区支持**：
- 百度AI社区：https://ai.baidu.com/
- GitHub：https://github.com/PaddlePaddle

---

**文档更新时间**：2026年2月
