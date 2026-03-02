"""
Add TCM tongue diagnosis knowledge to RAG vector database
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import RAG modules
from api_service.core.vector_db import VectorDatabaseManager
from api_service.core.rag_config import rag_settings

# Load the knowledge base JSON
knowledge_path = Path("C:/Users/Administrator/Desktop/shangzhan/ai_shezhen/api_service/knowledge/tcm_tongue_diagnosis_rag.json")

with open(knowledge_path, "r", encoding="utf-8") as f:
    knowledge_data = json.load(f)

print(f"Loaded knowledge base: {knowledge_data['metadata']['title']}")
print(f"Categories: {', '.join(knowledge_data['metadata']['categories'])}")

# Initialize vector database manager
print("\nInitializing vector database manager...")
vector_db = VectorDatabaseManager()

# Prepare documents and metadata
all_texts = []
all_metadatas = []
all_ids = []

doc_count = 0
for doc in knowledge_data['documents']:
    category = doc['category']
    content = doc['content']
    item_count = doc['item_count']

    print(f"\nProcessing category: {category} ({item_count} items)")

    # Split content into individual items (by newlines)
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('---') or line.startswith('#'):
            continue

        # Skip section headers
        if category.replace('公式', '').replace('歌诀', '') in line:
            continue

        all_texts.append(line)
        all_metadatas.append({
            'category': category,
            'source': '小红书中医科普资料',
            'knowledge_type': 'tongue_diagnosis',
            'created_at': knowledge_data['metadata']['created_at']
        })
        all_ids.append(f"{category}_{doc_count}")
        doc_count += 1

print(f"\nTotal documents to add: {len(all_texts)}")

# Add documents to vector database
print("\nAdding documents to vector database...")
success = vector_db.add_documents(
    texts=all_texts,
    metadatas=all_metadatas,
    ids=all_ids
)

if success:
    print(f"\n{'='*60}")
    print(f"Successfully added {len(all_texts)} documents to RAG knowledge base!")
    print(f"{'='*60}")
    print(f"\nKnowledge base statistics:")
    print(f"- Total documents: {len(all_texts)}")
    print(f"- Categories: {len(knowledge_data['documents'])}")
    print(f"- Vector DB path: {rag_settings.VECTOR_DB_PATH}")
    print(f"- Collection: {rag_settings.COLLECTION_NAME}")
else:
    print(f"\nFailed to add documents to vector database")
    sys.exit(1)

# Verify by doing a test search
print("\nPerforming test search...")
try:
    results = vector_db.search(
        query="舌淡苔白是什么证型",
        top_k=3,
        min_score=0.3
    )

    print(f"\nTest search returned {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Similarity: {result['similarity']:.2%}")
        print(f"   Category: {result['metadata'].get('category', 'N/A')}")
        print(f"   Content: {result['document'][:100]}...")

except Exception as e:
    print(f"Test search failed: {e}")

print(f"\n{'='*60}")
print("RAG knowledge base setup complete!")
print(f"{'='*60}")
