#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
向量数据库管理模块
Vector Database Management Module
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class VectorDatabaseManager:
    """向量数据库管理器"""

    def __init__(self, config=None):
        """
        初始化向量数据库管理器

        Args:
            config: RAG配置对象
        """
        from api_service.core.rag_config import rag_settings, get_vector_db_path

        self.config = config or rag_settings
        self.db_path = get_vector_db_path()
        self.collection_name = self.config.COLLECTION_NAME

        # 初始化向量数据库
        self._init_vector_db()

    def _init_vector_db(self):
        """初始化向量数据库"""
        db_type = self.config.VECTOR_DB_TYPE

        if db_type == "chroma":
            self._init_chromadb()
        elif db_type == "faiss":
            self._init_faiss()
        elif db_type == "pinecone":
            self._init_pinecone()
        else:
            raise ValueError(f"Unsupported vector database type: {db_type}")

    def _init_chromadb(self):
        """初始化ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建ChromaDB客户端
            self.client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # 获取或创建集合
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name,
                    embedding_function=None  # 我们将使用自定义嵌入函数
                )
                logger.info(f"Loaded existing collection: {self.collection_name}")
            except Exception as e:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "TCM Tongue Diagnosis Knowledge Base"}
                )
                logger.info(f"Created new collection: {self.collection_name}")

            logger.info("ChromaDB initialized successfully")

        except ImportError:
            logger.error("ChromaDB not installed. Install with: pip install chromadb")
            raise

    def _init_faiss(self):
        """初始化FAISS"""
        try:
            import faiss
            import numpy as np

            # 初始化FAISS索引
            dimension = self.config.EMBEDDING_DIMENSION
            self.index = faiss.IndexFlatL2(dimension)

            # 存储文档数据
            self.documents = []
            self.metadatas = []

            # 加载现有索引
            index_path = self.db_path / "faiss.index"
            if index_path.exists():
                self.index = faiss.read_index(str(index_path))

                # 加载文档数据
                docs_path = self.db_path / "documents.json"
                if docs_path.exists():
                    with open(docs_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.documents = data.get('documents', [])
                        self.metadatas = data.get('metadatas', [])

                logger.info("FAISS index loaded from disk")
            else:
                logger.info("New FAISS index created")

            logger.info("FAISS initialized successfully")

        except ImportError:
            logger.error("FAISS not installed. Install with: pip install faiss-cpu")
            raise

    def _init_pinecone(self):
        """初始化Pinecone"""
        try:
            import pinecone

            # 初始化Pinecone客户端
            api_key = os.getenv("PINECONE_API_KEY")
            if not api_key:
                raise ValueError("PINECONE_API_KEY environment variable not set")

            pinecone.init(api_key=api_key, environment=os.getenv("PINECONE_ENV", "us-east1"))

            # 获取或创建索引
            index_name = self.collection_name
            if index_name in pinecone.list_indexes():
                self.index = pinecone.Index(index_name)
                logger.info(f"Loaded existing Pinecone index: {index_name}")
            else:
                # 创建新索引
                pinecone.create_index(
                    name=index_name,
                    dimension=self.config.EMBEDDING_DIMENSION,
                    metric="cosine"
                )
                self.index = pinecone.Index(index_name)
                logger.info(f"Created new Pinecone index: {index_name}")

            logger.info("Pinecone initialized successfully")

        except ImportError:
            logger.error("Pinecone not installed. Install with: pip install pinecone-client")
            raise

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        添加文档到向量数据库

        Args:
            texts: 文本列表
            metadatas: 元数据列表
            ids: 文档ID列表 (可选)

        Returns:
            是否添加成功
        """
        try:
            db_type = self.config.VECTOR_DB_TYPE

            if db_type == "chroma":
                return self._add_chromadb_documents(texts, metadatas, ids)
            elif db_type == "faiss":
                return self._add_faiss_documents(texts, metadatas, ids)
            elif db_type == "pinecone":
                return self._add_pinecone_documents(texts, metadatas, ids)
            else:
                raise ValueError(f"Unsupported vector database type: {db_type}")

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False

    def _add_chromadb_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """添加文档到ChromaDB"""
        try:
            if ids is None:
                ids = [f"doc_{i}_{int(time.time())}" for i in range(len(texts))]

            self.collection.add(
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Added {len(texts)} documents to ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
            return False

    def _add_faiss_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """添加文档到FAISS"""
        try:
            import numpy as np

            # 生成嵌入向量
            embeddings = self._generate_embeddings(texts)

            # 添加到FAISS索引
            self.index.add(embeddings.astype('float32'))

            # 存储文档和元数据
            self.documents.extend(texts)
            self.metadatas.extend(metadatas)

            logger.info(f"Added {len(texts)} documents to FAISS")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents to FAISS: {e}")
            return False

    def _add_pinecone_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """添加文档到Pinecone"""
        try:
            import numpy as np

            if ids is None:
                ids = [f"doc_{i}_{int(time.time())}" for i in range(len(texts))]

            # 生成嵌入向量
            embeddings = self._generate_embeddings(texts)

            # 批量upsert
            vectors = []
            for i, (text, metadata, doc_id) in enumerate(zip(texts, metadatas, ids)):
                vectors.append({
                    "id": doc_id,
                    "values": embeddings[i].tolist(),
                    "metadata": metadata
                })

            self.index.upsert(vectors=vectors)

            logger.info(f"Added {len(texts)} documents to Pinecone")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents to Pinecone: {e}")
            return False

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        try:
            # 尝试使用本地嵌入模型
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.config.LOCAL_EMBEDDING_MODEL)
            embeddings = model.encode(texts, convert_to_numpy=True)

            return embeddings.tolist()

        except ImportError:
            logger.warning("sentence-transformers not available, using mock embeddings")
            # 返回随机嵌入 (仅用于测试)
            import numpy as np
            return np.random.rand(len(texts), self.config.EMBEDDING_DIMENSION).tolist()

    def search(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相关文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤条件
            min_score: 最小相似度分数

        Returns:
            搜索结果列表
        """
        try:
            db_type = self.config.VECTOR_DB_TYPE

            if db_type == "chroma":
                return self._search_chromadb(query, top_k, filters, min_score)
            elif db_type == "faiss":
                return self._search_faiss(query, top_k, filters, min_score)
            elif db_type == "pinecone":
                return self._search_pinecone(query, top_k, filters, min_score)
            else:
                raise ValueError(f"Unsupported vector database type: {db_type}")

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _search_chromadb(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = None
    ) -> List[Dict[str, Any]]:
        """在ChromaDB中搜索"""
        try:
            top_k = top_k or self.config.TOP_K_RESULTS
            min_score = min_score or self.config.MIN_SIMILARITY_SCORE

            # 生成查询嵌入
            query_embedding = self._generate_embeddings([query])[0]

            # 执行搜索
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filters
            )

            # 格式化结果
            formatted_results = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # 计算相似度分数
                similarity = 1.0 / (1.0 + distance)

                if similarity >= min_score:
                    formatted_results.append({
                        'document': doc,
                        'metadata': metadata,
                        'similarity': similarity,
                        'distance': distance
                    })

            logger.info(f"ChromaDB search returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            return []

    def _search_faiss(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = None
    ) -> List[Dict[str, Any]]:
        """在FAISS中搜索"""
        try:
            import numpy as np

            top_k = top_k or self.config.TOP_K_RESULTS
            min_score = min_score or self.config.MIN_SIMILARITY_SCORE

            # 生成查询嵌入
            query_embedding = self._generate_embeddings([query])[0]

            # 执行搜索
            distances, indices = self.index.search(
                np.array([query_embedding]).astype('float32'),
                top_k
            )

            # 格式化结果
            formatted_results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < len(self.documents):
                    # 计算相似度分数
                    similarity = 1.0 / (1.0 + distance)

                    if similarity >= min_score:
                        # 应用元数据过滤
                        if filters:
                            metadata = self.metadatas[idx]
                            if not all(k in metadata and v == metadata[k] for k, v in filters.items()):
                                continue

                        formatted_results.append({
                            'document': self.documents[idx],
                            'metadata': self.metadatas[idx] if idx < len(self.metadatas) else {},
                            'similarity': float(similarity),
                            'distance': float(distance)
                        })

            logger.info(f"FAISS search returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            return []

    def _search_pinecone(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = None
    ) -> List[Dict[str, Any]]:
        """在Pinecone中搜索"""
        try:
            top_k = top_k or self.config.TOP_K_RESULTS
            min_score = min_score or self.config.MIN_SIMILARITY_SCORE

            # 生成查询嵌入
            query_embedding = self._generate_embeddings([query])[0]

            # 执行搜索
            results = self.index.query(
                vector=query_embedding.tolist(),
                top_k=top_k,
                filter=filters,
                include_metadata=True
            )

            # 格式化结果
            formatted_results = []
            for match in results['matches']:
                similarity = match['score']
                if similarity >= min_score:
                    formatted_results.append({
                        'document': match.get('text', ''),
                        'metadata': match.get('metadata', {}),
                        'similarity': similarity,
                        'distance': 1.0 - similarity
                    })

            logger.info(f"Pinecone search returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            return []

    def delete_documents(self, ids: List[str]) -> bool:
        """
        删除文档

        Args:
            ids: 文档ID列表

        Returns:
            是否删除成功
        """
        try:
            db_type = self.config.VECTOR_DB_TYPE

            if db_type == "chroma":
                self.collection.delete(ids=ids)
            elif db_type == "faiss":
                # FAISS不支持删除单个文档，需要重建索引
                logger.warning("FAISS does not support individual document deletion")
                return False
            elif db_type == "pinecone":
                self.index.delete(ids=ids)

            logger.info(f"Deleted {len(ids)} documents")
            return True

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息

        Returns:
            统计信息字典
        """
        try:
            db_type = self.config.VECTOR_DB_TYPE

            if db_type == "chroma":
                count = self.collection.count()
                return {
                    'type': 'chroma',
                    'count': count,
                    'name': self.collection_name
                }
            elif db_type == "faiss":
                return {
                    'type': 'faiss',
                    'count': self.index.ntotal,
                    'dimension': self.index.d
                }
            elif db_type == "pinecone":
                stats = self.index.describe_index_stats()
                return {
                    'type': 'pinecone',
                    'count': stats.get('total_vector_count', 0),
                    'dimension': self.config.EMBEDDING_DIMENSION
                }

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {'error': str(e)}

    def reset_collection(self) -> bool:
        """
        重置集合

        Returns:
            是否重置成功
        """
        try:
            db_type = self.config.VECTOR_DB_TYPE

            if db_type == "chroma":
                self.client.delete_collection(self.collection_name)
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "TCM Tongue Diagnosis Knowledge Base"}
                )
            elif db_type == "faiss":
                import os
                # 删除索引文件
                index_path = self.db_path / "faiss.index"
                docs_path = self.db_path / "documents.json"

                if index_path.exists():
                    os.remove(index_path)
                if docs_path.exists():
                    os.remove(docs_path)

                # 重新初始化
                self._init_faiss()
            elif db_type == "pinecone":
                self.index.delete(delete_all=True)

            logger.info(f"Reset collection: {self.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            return False


# 全局向量数据库管理器实例
_vector_db_manager = None


def get_vector_db_manager():
    """获取向量数据库管理器实例"""
    global _vector_db_manager
    if _vector_db_manager is None:
        _vector_db_manager = VectorDatabaseManager()
    return _vector_db_manager