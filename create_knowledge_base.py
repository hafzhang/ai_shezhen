"""
Create a structured knowledge base from extracted tongue diagnosis content
"""
import json
from pathlib import Path
from collections import defaultdict

# Read the extracted text
images_dir = Path("C:/Users/Administrator/Desktop/shangzhan/ai_shezhen/images")
json_path = images_dir / "extracted_text.json"

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Organize content by category
categories = defaultdict(list)

for filename, content in data.items():
    text = content.get("structured_lines", [])
    if not text:
        continue

    # Categorize based on filename
    if "100个中医诊断公式" in filename:
        if any("舌诊" in line for line in text):
            categories["舌诊诊断公式"].extend(text)
        elif any("脉诊" in line for line in text):
            categories["脉诊诊断公式"].extend(text)
        elif any("症状" in line for line in text):
            categories["症状诊断公式"].extend(text)
        elif any("寒热" in line for line in text):
            categories["寒热辨证公式"].extend(text)
        elif any("虚实" in line for line in text):
            categories["虚实辨证公式"].extend(text)
        elif any("月经" in line or "白带" in line or "关节" in line or "皮肤" in line for line in text):
            categories["妇科皮肤科诊断公式"].extend(text)
        elif any("五脏" in line for line in text):
            categories["五脏相关公式"].extend(text)
        elif any("六经" in line for line in text):
            categories["六经辨证公式"].extend(text)
        elif any("气血" in line for line in text):
            categories["气血津液公式"].extend(text)
        elif any("养生" in line for line in text):
            categories["养生调理公式"].extend(text)
        elif any("进阶" in line for line in text):
            categories["进阶诊断公式"].extend(text)
        else:
            categories["综合诊断公式"].extend(text)

    elif "万能舌诊公式" in filename:
        categories["舌象特征公式"].extend(text)

    elif "舌诊歌诀" in filename:
        if "基本" in "\n".join(text):
            categories["舌诊基本歌诀"].extend(text)
        else:
            categories["舌诊提升歌诀"].extend(text)

# Create markdown knowledge base
output_path = Path("C:/Users/Administrator/Desktop/shangzhan/ai_shezhen/api_service/knowledge/tcm_tongue_diagnosis_knowledge.md")
output_path.parent.mkdir(exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    f.write("# 中医舌诊诊断知识库\n\n")
    f.write("本知识库汇总了中医舌诊的核心诊断公式、歌诀和辨证方法。\n\n")
    f.write("---\n\n")

    # Write each category
    for category_name, items in categories.items():
        f.write(f"## {category_name}\n\n")

        # Group related items and remove duplicates while preserving order
        seen = set()
        unique_items = []
        for item in items:
            # Clean up the item
            item_clean = item.strip()
            # Skip empty items and headers
            if not item_clean or item_clean.endswith("来自小红书网页版"):
                continue
            # Skip section headers that are just category names
            if category_name.replace("公式", "").replace("歌诀", "") in item_clean:
                continue
            # Remove duplicates
            if item_clean not in seen:
                seen.add(item_clean)
                unique_items.append(item_clean)

        for item in unique_items:
            # Format as list item
            if item.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.",
                                "11.", "12.", "13.", "14.", "15.", "16.", "17.", "18.", "19.", "20.",
                                "21.", "22.", "23.", "24.", "25.", "26.", "27.", "28.", "29.", "30.",
                                "31.", "32.", "33.", "34.", "35.", "36.", "37.", "38.", "39.", "40.",
                                "41.", "42.", "43.", "44.", "45.", "46.", "47.", "48.", "49.", "50.",
                                "51.", "52.", "53.", "54.", "55.", "56.", "57.", "58.", "59.", "60.",
                                "61.", "62.", "63.", "64.", "65.", "66.", "67.", "68.", "69.", "70.")):
                f.write(f"{item}\n")
            else:
                f.write(f"- {item}\n")

        f.write("\n")

    # Add summary section
    f.write("---\n\n")
    f.write("## 知识库使用说明\n\n")
    f.write("本知识库包含以下内容：\n\n")
    f.write("1. **舌诊诊断公式**: 基于舌色、舌苔、舌形进行快速诊断的公式\n")
    f.write("2. **脉诊诊断公式**: 结合脉象与舌象的综合诊断方法\n")
    f.write("3. **症状诊断公式**: 根据症状组合进行辨证分析\n")
    f.write("4. **寒热辨证公式**: 区分寒证与热证的诊断要点\n")
    f.write("5. **虚实辨证公式**: 区分虚证与实证的诊断要点\n")
    f.write("6. **五脏相关公式**: 五脏（心肝脾肺肾）病变的诊断方法\n")
    f.write("7. **六经辨证公式**: 六经（太阳、阳明、少阳、太阴、少阴、厥阴）辨证\n")
    f.write("8. **气血津液公式**: 气、血、津液异常的诊断\n")
    f.write("9. **养生调理公式**: 根据舌象进行养生调理的建议\n")
    f.write("10. **进阶诊断公式**: 多症状综合分析的高级诊断方法\n")
    f.write("11. **舌象特征公式**: 舌质、舌苔、舌形各部位特征的详细说明\n")
    f.write("12. **舌诊歌诀**: 便于记忆的舌诊口诀\n\n")
    f.write("使用方法：根据患者的舌象特征，在相应章节查找匹配的公式，")
    f.write("结合脉象、症状进行综合辨证分析。\n\n")

print(f"Knowledge base created at: {output_path}")

# Create JSON format for RAG
rag_json_path = Path("C:/Users/Administrator/Desktop/shangzhan/ai_shezhen/api_service/knowledge/tcm_tongue_diagnosis_rag.json")

rag_data = {
    "metadata": {
        "title": "中医舌诊诊断知识库",
        "description": "汇总了中医舌诊的核心诊断公式、歌诀和辨证方法",
        "source": "小红书中医科普资料",
        "created_at": "2026-03-01",
        "categories": list(categories.keys())
    },
    "documents": []
}

for category_name, items in categories.items():
    # Remove duplicates
    seen = set()
    unique_items = []
    for item in items:
        item_clean = item.strip()
        if not item_clean or item_clean.endswith("来自小红书网页版"):
            continue
        if category_name.replace("公式", "").replace("歌诀", "") in item_clean:
            continue
        if item_clean not in seen:
            seen.add(item_clean)
            unique_items.append(item_clean)

    rag_data["documents"].append({
        "category": category_name,
        "content": "\n".join(unique_items),
        "item_count": len(unique_items)
    })

with open(rag_json_path, "w", encoding="utf-8") as f:
    json.dump(rag_data, f, ensure_ascii=False, indent=2)

print(f"RAG JSON created at: {rag_json_path}")
print(f"\nTotal categories: {len(categories)}")
print(f"Total documents: {len(rag_data['documents'])}")
