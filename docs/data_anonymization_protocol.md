# 数据脱敏流程协议

## 1. 概述

本文档描述AI舌诊智能诊断系统的数据脱敏流程，确保患者隐私数据的保护和合规性。

### 1.1 目的

- 保护患者隐私信息
- 符合《个人信息保护法》、《网络安全法》等法规要求
- 为医疗器械备案提供合规支持
- 建立可审计的数据处理流程

### 1.2 适用范围

- 舌诊图像数据集（shezhenv3-coco）
- 所有训练、验证、测试数据
- 导入系统的患者舌象图像

## 2. 敏感数据识别

### 2.1 EXIF敏感标签

以下EXIF标签被识别为敏感数据，必须在处理时删除：

| 标签类别 | 标签名称 | 风险级别 | 说明 |
|---------|---------|---------|------|
| **位置信息** | GPSInfo | 高 | GPS坐标可能暴露患者位置 |
| **设备信息** | Make, Model | 中 | 设备信息可能关联到特定用户 |
| **设备信息** | SerialNumber, CameraSerialNumber | 高 | 序列号可唯一标识设备 |
| **时间信息** | DateTime, DateTimeOriginal | 中 | 拍摄时间可能关联到个人活动 |
| **用户信息** | Artist, OwnerName | 高 | 直接标识个人身份 |
| **版权信息** | Copyright | 中 | 可能包含个人信息 |
| **描述信息** | ImageDescription, UserComment | 中 | 可能包含个人备注 |
| **Windows标签** | XPAuthor, XPComment, XPKeywords | 中 | Windows系统写入的用户信息 |

### 2.2 文件名敏感信息

原始文件名可能包含：
- 患者姓名或缩写
- 就诊日期
- 病历号
- 其他标识信息

**处理策略**: 使用SHA-256哈希替换文件名

## 3. 脱敏流程

### 3.1 流程图

```
原始图像 → EXIF分析 → EXIF清理 → 文件名哈希化（可选） → 验证 → 存储安全区域
    ↓           ↓
  记录日志   生成报告
```

### 3.2 详细步骤

#### 步骤1: EXIF分析

```bash
python datasets/tools/anonymize.py \
    --input shezhenv3-coco/train/images \
    --output datasets/processed/anonymized/train \
    --report-only \
    --report-output datasets/processed/exif_analysis_report.json
```

分析输出：
- 总图像数量
- 包含EXIF的图像数量
- 敏感标签分布统计
- 具体敏感信息详情

#### 步骤2: EXIF清理

```bash
python datasets/tools/anonymize.py \
    --input shezhenv3-coco/train/images \
    --output datasets/processed/anonymized/train \
    --report-output datasets/processed/anonymization_report.json
```

清理策略：
1. 读取原始图像数据（像素值）
2. 创建新图像对象，仅保留像素数据
3. 保存时不写入任何元数据

#### 步骤3: 文件名哈希化（如需要）

```bash
python datasets/tools/anonymize.py \
    --input shezhenv3-coco/train/images \
    --output datasets/processed/anonymized/train \
    --hash-filenames \
    --mapping-output datasets/processed/filename_mapping.json
```

哈希规则：
- 算法: SHA-256（取前16位）
- 盐值: `shezhen_anonymize_v1`
- 保留扩展名

#### 步骤4: COCO标注更新

当使用文件名哈希化时，需要同步更新COCO标注文件：

```python
from datasets.tools.anonymize import DataAnonymizer

anonymizer = DataAnonymizer(
    input_dir="shezhenv3-coco/train/images",
    output_dir="datasets/processed/anonymized/train",
    hash_filenames=True
)
# 处理图像后...
anonymizer.process_coco_annotations(
    Path("shezhenv3-coco/train/annotations/train.json"),
    Path("datasets/processed/anonymized/train/annotations/train.json")
)
```

### 3.3 验证检查

脱敏后需要进行以下验证：

1. **EXIF验证**: 确认输出图像不包含任何EXIF标签
2. **像素完整性**: 确认图像像素数据未被损坏
3. **映射完整性**: 确认文件名映射表正确生成
4. **标注一致性**: 确认COCO标注与新文件名对应

```bash
# 验证脚本
python -c "
from PIL import Image
from pathlib import Path

output_dir = Path('datasets/processed/anonymized/train')
for img_path in list(output_dir.glob('*.jpg'))[:10]:
    with Image.open(img_path) as img:
        exif = img._getexif()
        if exif:
            print(f'ERROR: {img_path.name} still has EXIF data')
        else:
            print(f'OK: {img_path.name} - no EXIF')
"
```

## 4. 审计与合规

### 4.1 日志记录

所有脱敏操作生成以下记录：

1. **脱敏报告** (`anonymization_report.json`)
   - 处理时间
   - 处理文件数量
   - 敏感标签统计
   - 错误日志

2. **文件名映射表** (`filename_mapping.json`)
   - 原始文件名 → 哈希文件名
   - 仅授权人员可访问
   - 定期归档

### 4.2 数据保留策略

| 数据类型 | 保留期限 | 存储位置 |
|---------|---------|---------|
| 原始数据 | 训练结束后删除 | 安全区域 |
| 脱敏数据 | 模型生命周期 | 生产环境 |
| 映射表 | 3年 | 审计服务器 |
| 操作日志 | 5年 | 日志服务器 |

### 4.3 合规检查清单

- [ ] 所有EXIF信息已清理
- [ ] 文件名已匿名化（如需要）
- [ ] 生成脱敏报告
- [ ] 映射表安全存储
- [ ] 操作日志完整
- [ ] 通过隐私审查

## 5. 安全措施

### 5.1 访问控制

- 原始数据仅限授权研究人员访问
- 映射表存储于独立安全区域
- 所有访问记录审计日志

### 5.2 数据传输

- 使用加密传输协议（HTTPS/SFTP）
- 传输前后验证数据完整性
- 禁止使用公共网络传输原始数据

### 5.3 异常处理

| 异常类型 | 处理方式 |
|---------|---------|
| EXIF读取失败 | 记录日志，继续处理 |
| 图像损坏 | 跳过并标记，不中断流程 |
| 写入失败 | 重试3次，失败则记录错误 |
| 存储空间不足 | 立即停止，通知管理员 |

## 6. 附录

### 6.1 相关法规

- 《中华人民共和国个人信息保护法》
- 《中华人民共和国网络安全法》
- 《医疗健康信息安全指南》
- 《医疗器械网络安全注册审查指导原则》

### 6.2 联系方式

- 数据安全负责人: [待填写]
- 合规审查负责人: [待填写]
- 技术支持: [待填写]

### 6.3 版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|-----|------|---------|------|
| 1.0 | 2026-02-11 | 初始版本 | Ralph Agent |

---

*本文档为AI舌诊智能诊断系统合规文档的一部分，未经授权不得外传。*
