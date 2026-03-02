"""
Extract tongue diagnosis content from PDF and add to RAG knowledge base
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# PDF content - tongue diagnosis sections extracted from the document
pdf_tongue_content = {
    "metadata": {
        "title": "24考研中诊背诵资料-舌诊部分",
        "description": "中医诊断学考研资料中的舌诊相关内容",
        "source": "24考研中诊背诵资料.pdf",
        "created_at": "2026-03-01"
    },
    "documents": [
        {
            "category": "舌诊基本原理",
            "content": """
舌诊原理
1. 舌与经络相连: 手少阴心经之别系舌本，足太阴脾经连舌本、散舌下，足少阴肾经挟舌本，足厥阴肝经络舌本。
2. 舌与脏腑相连: 舌为心之苗，脾之外候，苔乃胃气之所熏蒸。
3. 舌面脏腑分部: 舌尖对应上焦（心肺），舌中对应中焦（脾胃），舌根对应下焦（肾），舌边对应肝胆。
4. 舌诊原理: 脏腑精气上荣于舌，脏腑病变可反映于舌象。
"""
        },
        {
            "category": "正常舌象",
            "content": """
正常舌象（淡红舌、薄白苔）
1. 淡红舌: 舌色淡红润泽，为心血充足、胃气旺盛之象。
2. 薄白苔: 舌苔薄白而润，为胃气充盈、阳气充足之象。
3. 柔软灵活: 舌体柔软，运动灵活，为气血充沛之象。
4. 不燥不腻: 舌面润泽而不燥，苔不厚腻，为津液正常之象。
5. 正常舌象意义: 心血充足、胃气旺盛、气血调和、阳气充足。
"""
        },
        {
            "category": "望舌质-舌色",
            "content": """
望舌质-舌色
1. 淡红舌: 舌色淡红润泽。主病: 正常舌象或轻病。
2. 淡白舌: 舌色较正常浅淡。主病: 气血两虚、阳虚。
   - 淡白而瘦: 气血两虚
   - 淡白而胖: 阳虚水停
   - 淡白湿润: 阳虚寒盛
3. 红舌: 舌色较正常深红。主病: 热证。
   - 舌红苔黄: 实热
   - 舌红少苔: 虚热
   - 舌红绛: 热入营血
4. 绛舌: 舌色深红。主病: 热盛营血、阴虚火旺。
5. 紫舌: 舌色青紫。主病: 气血瘀滞、阳气暴脱。
   - 绛紫: 热盛血瘀
   - 淡紫: 寒凝血瘀
   - 瘀斑瘀点: 气滞血瘀
6. 青舌: 舌色青。主病: 寒盛、阳虚、血瘀。
"""
        },
        {
            "category": "望舌质-舌形",
            "content": """
望舌质-舌形
1. 老嫩:
   - 老舌: 舌质纹理粗糙，形色坚敛苍老。主病: 实证。
   - 嫩舌: 舌质纹理细腻，形色浮胖娇嫩。主病: 虚证。
2. 胖瘦:
   - 胖大舌: 舌体比正常大。主病: 水湿痰饮、阳虚、气虚。
   - 肿胀舌: 舌体肿大。主病: 心脾热盛、中毒。
   - 瘦薄舌: 舌体比正常小。主病: 气血两虚、阴虚火旺。
3. 点刺:
   - 红点: 舌蕈状乳头红点。主病: 热毒蕴结、血热。
   - 芒刺: 舌面刺状突起。主病: 脏腑热极、营血热盛。
4. 裂纹:
   - 裂纹舌: 舌面裂沟。主病: 热盛伤津、阴血亏损、脾虚湿浸。
5. 齿痕:
   - 齿痕舌: 舌边缘有牙齿压迫痕迹。主病: 脾虚、气虚、湿盛。
6. 舌下络脉:
   - 舌下络脉青紫曲张: 气血瘀滞。
   - 舌下络脉细短: 气血不足。
"""
        },
        {
            "category": "望舌质-舌态",
            "content": """
望舌质-舌态
1. 痿软舌: 舌体软弱无力，不能自由伸缩。主病: 气血俱虚、阴液枯竭。
2. 强硬舌: 舌体失柔，板硬强直。主病: 热入心包、高热伤津、风痰阻络。
3. 歪斜舌: 舌体偏于一侧。主病: 中风或中风先兆。
4. 颤动舌: 舌体不自主震颤。主病: 气血两虚、阳虚、热极生风。
5. 吐舌和弄舌:
   - 吐舌: 舌伸长吐出口外。主病: 心脾有热、疫毒攻心。
   - 弄舌: 舌反复吞吐口外。主病: 动风先兆、智能发育不良。
6. 短缩舌: 舌体紧缩不能伸长。主病: 寒凝筋脉、热盛伤津、气血俱虚。
7. 舌纵: 舌体伸长不收。主病: 实热内炽、气虚。
"""
        },
        {
            "category": "望舌苔-苔质",
            "content": """
望舌苔-苔质
1. 苔之厚薄:
   - 薄苔: 透过舌苔能隐约见到舌质。主病: 正常舌象、表证、轻病。
   - 厚苔: 透过舌苔不能见到舌质。主病: 里证、病重、痰湿、食积。
2. 苔之润燥:
   - 润苔: 舌面润泽。主病: 正常、津液未伤。
   - 滑苔: 舌面水分过多。主病: 水湿、痰饮。
   - 燥苔: 舌面干燥。主病: 热盛伤津、阴液亏损。
   - 糙苔: 舌面粗糙如砂石。主病: 热盛伤津重证。
3. 苔之腐腻:
   - 腐苔: 苔质颗粒粗大疏松。主病: 食积、痰浊。
   - 腻苔: 苔质颗粒细腻致密。主病: 湿浊、痰饮、食积。
4. 苔之剥落:
   - 剥苔: 舌苔部分脱落。主病: 胃气不足、胃阴损伤。
   - 花剥苔: 苔剥落呈花斑状。主病: 胃气阴两虚。
   - 镜面舌: 苔全部脱落，舌面光滑如镜。主病: 胃阴枯竭。
   - 地图舌: 苔剥落呈地图状边缘隆起。主病: 气阴两虚。
5. 苔之偏全:
   - 全苔: 苔布满全舌。主病: 邪气散漫、湿痰阻滞。
   - 偏苔: 苔仅见于舌的某处。主病: 舌苔偏外=邪在表，舌苔偏内=邪在里。
6. 苔之真假:
   - 真苔: 苔有根，紧贴舌面。主病: 胃气尚存。
   - 假苔: 苔无根，似浮涂舌面。主病: 胃气受损。
7. 苔之消长:
   - 苔由少变多: 病进。
   - 苔由多变少: 病退。
"""
        },
        {
            "category": "望舌苔-苔色",
            "content": """
望舌苔-苔色
1. 白苔:
   - 薄白苔: 正常舌象、表证、寒证。
   - 白厚苔: 寒邪入里、寒湿、痰饮。
   - 白糙苔: 燥热伤津。
   - 白滑苔: 寒湿、痰饮。
   - 白腻苔: 寒湿、痰浊、食积。
2. 黄苔:
   - 淡黄苔: 里热轻证。
   - 深黄苔: 里热重证。
   - 焦黄苔: 热极。
   - 黄滑苔: 阳虚热蕴。
   - 黄腻苔: 湿热、痰热、食积化热。
   - 黄糙苔: 邪热伤津、燥结。
3. 灰黑苔:
   - 灰苔: 里热、里寒之重证。
   - 黑苔: 里热、里寒之极重证。
   - 灰黑润滑苔: 阳虚寒盛、痰饮内停。
   - 灰黑干燥苔: 热盛伤津、阴液亏损。
4. 绿苔、霉酱苔:
   - 绿苔: 湿热郁蒸。
   - 霉酱苔: 湿热夹痰、宿食湿浊。
"""
        },
        {
            "category": "舌象综合分析",
            "content": """
舌象综合分析
1. 舌质与舌苔结合分析:
   - 淡红舌+薄白苔=正常或轻病
   - 淡白舌+白苔=气血两虚或阳虚
   - 红舌+黄苔=实热证
   - 红绛舌+少苔或无苔=阴虚火旺
   - 青紫舌+苔润=寒凝血瘀
   - 瘦薄红舌+少苔=阴虚火旺
   - 胖大淡舌+齿痕=脾虚湿盛
   - 胖大淡舌+白滑苔=阳虚水停
2. 舌质舌苔综合判断:
   - 舌质正气强弱→判断正气盛衰
   - 舌苔邪气性质→判断病邪性质
   - 舌质舌苔变化→判断病位深浅
3. 舌诊注意事项:
   - 光线充足，自然光为佳
   - 伸舌自然，舌体放松
   - 先看舌苔，后看舌质
   - 排除染苔、假苔
   - 结合四诊合参
"""
        }
    ]
}

# Save to JSON first
output_dir = Path("C:/Users/Administrator/Desktop/shangzhan/ai_shezhen/images")
output_path = output_dir / "pdf_tongue_diagnosis_extracted.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(pdf_tongue_content, f, ensure_ascii=False, indent=2)

print(f"PDF舌诊内容已提取并保存到: {output_path}")

# Import to RAG
from api_service.core.vector_db import VectorDatabaseManager
from api_service.core.rag_config import rag_settings

print("\n初始化向量数据库管理器...")
vector_db = VectorDatabaseManager()

# Prepare documents and metadata
all_texts = []
all_metadatas = []
all_ids = []

doc_count = 0
for doc in pdf_tongue_content['documents']:
    category = doc['category']
    content = doc['content']

    print(f"\n处理类别: {category}")

    # Split content into individual items (by lines and numbers)
    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('---') or line.startswith('#'):
            continue

        # Skip section headers that are just category names
        if category.replace('望舌质-', '').replace('望舌苔-', '') in line:
            continue

        all_texts.append(line)
        all_metadatas.append({
            'category': category,
            'source': '24考研中诊背诵资料.pdf',
            'knowledge_type': 'tongue_diagnosis',
            'created_at': pdf_tongue_content['metadata']['created_at']
        })
        all_ids.append(f"pdf_{category}_{doc_count}")
        doc_count += 1

print(f"\n总计待添加文档数: {len(all_texts)}")

# Add documents to vector database
print("\n正在添加文档到向量数据库...")
success = vector_db.add_documents(
    texts=all_texts,
    metadatas=all_metadatas,
    ids=all_ids
)

if success:
    print(f"\n{'='*60}")
    print(f"成功将 {len(all_texts)} 条PDF舌诊内容添加到RAG知识库！")
    print(f"{'='*60}")
    print(f"\n知识库统计:")
    print(f"- 新增文档数: {len(all_texts)}")
    print(f"- 内容来源: 24考研中诊背诵资料.pdf")
    print(f"- 向量DB路径: {rag_settings.VECTOR_DB_PATH}")
    print(f"- Collection: {rag_settings.COLLECTION_NAME}")
else:
    print(f"\n添加文档失败")
    sys.exit(1)

# Test search
print("\n执行测试搜索...")
try:
    results = vector_db.search(
        query="淡白舌主什么病",
        top_k=3,
        min_score=0.3
    )

    print(f"\n测试搜索返回 {len(results)} 条结果:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. 相似度: {result['similarity']:.2%}")
        print(f"   类别: {result['metadata'].get('category', 'N/A')}")
        print(f"   来源: {result['metadata'].get('source', 'N/A')}")
        print(f"   内容: {result['document'][:100]}...")

except Exception as e:
    print(f"测试搜索失败: {e}")

print(f"\n{'='*60}")
print("PDF舌诊内容导入RAG知识库完成！")
print(f"{'='*60}")
