#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAG API endpoints
RAG API endpoints for knowledge base management and PDF report generation
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from api_service.core.rag_config import rag_settings
from api_service.core.vector_db import get_vector_db_manager
from api_service.core.rag_pipeline import get_rag_pipeline
from api_service.core.pdf_generator import get_pdf_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Knowledge Base"])


# ============================================================================
# Pydantic Models
# ============================================================================

class DocumentUpload(BaseModel):
    """文档上传模型"""
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    category: str = Field(..., description="知识类别: tcm_theory, tongue_diagnosis, syndrome_analysis, health_guidance, case_studies, herbal_medicine")


class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    category: Optional[str] = None
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0)


class RAGAnalysisRequest(BaseModel):
    """RAG分析请求模型"""
    query: str
    tongue_features: Dict[str, Any] = Field(default_factory=dict)
    user_info: Optional[Dict[str, Any]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    category: Optional[str] = None


class PDFReportRequest(BaseModel):
    """PDF报告请求模型"""
    diagnosis_data: Dict[str, Any]
    user_info: Optional[Dict[str, Any]] = None
    filename: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/health")
async def rag_health_check():
    """RAG服务健康检查"""
    return {
        "success": True,
        "status": "healthy",
        "vector_db_type": rag_settings.VECTOR_DB_TYPE,
        "embedding_model": rag_settings.LOCAL_EMBEDDING_MODEL,
        "llm_provider": rag_settings.RAG_LLM_PROVIDER,
        "llm_model": rag_settings.RAG_LLM_MODEL
    }


@router.get("/knowledge-base/stats")
async def get_knowledge_base_stats():
    """获取知识库统计信息"""
    try:
        vector_db = get_vector_db_manager()
        stats = vector_db.get_collection_stats()

        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-base/documents")
async def add_document(document: DocumentUpload):
    """添加文档到知识库"""
    try:
        vector_db = get_vector_db_manager()

        # 准备元数据
        metadata = {
            "category": document.category,
            "added_at": datetime.now().isoformat(),
            **document.metadata
        }

        # 添加文档
        success = vector_db.add_documents(
            texts=[document.text],
            metadatas=[metadata],
            ids=[f"doc_{datetime.now().timestamp()}"]
        )

        if success:
            return {
                "success": True,
                "message": "文档添加成功",
                "document_id": f"doc_{datetime.now().timestamp()}"
            }
        else:
            raise HTTPException(status_code=500, detail="文档添加失败")

    except Exception as e:
        logger.error(f"Failed to add document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-base/upload")
async def upload_knowledge_file(
    file: UploadFile = File(...),
    category: str = ...,
    description: Optional[str] = None
):
    """上传知识文件到知识库"""
    try:
        vector_db = get_vector_db_manager()

        # 读取文件内容
        content = await file.read()
        text = content.decode('utf-8')

        # 准备元数据
        metadata = {
            "category": category,
            "filename": file.filename,
            "file_size": len(content),
            "description": description or "",
            "added_at": datetime.now().isoformat()
        }

        # 添加文档
        success = vector_db.add_documents(
            texts=[text],
            metadatas=[metadata],
            ids=[f"doc_{file.filename}_{datetime.now().timestamp()}"]
        )

        if success:
            return {
                "success": True,
                "message": "文件上传成功",
                "filename": file.filename,
                "category": category
            }
        else:
            raise HTTPException(status_code=500, detail="文件上传失败")

    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_knowledge(request: QueryRequest):
    """搜索知识库"""
    try:
        vector_db = get_vector_db_manager()

        # 构建过滤条件
        filters = None
        if request.category:
            filters = {"category": request.category}

        # 执行搜索
        results = vector_db.search(
            query=request.query,
            top_k=request.top_k,
            filters=filters,
            min_score=request.min_similarity
        )

        return {
            "success": True,
            "query": request.query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def rag_analysis(request: RAGAnalysisRequest):
    """执行RAG分析"""
    try:
        rag_pipeline = get_rag_pipeline()

        # 构建查询
        if request.tongue_features:
            query = f"舌象特征分析：{request.tongue_features.get('summary', str(request.tongue_features))}"
            if request.user_info:
                user_summary = f"，用户信息：{request.user_info.get('name', '')}，年龄{request.user_info.get('age', '')}岁"
                query += user_summary
        else:
            query = request.query

        # 构建过滤条件
        filters = None
        if request.category:
            filters = {"category": request.category}

        # 执行RAG分析
        result = rag_pipeline.run_rag_pipeline(
            query=query,
            top_k=request.top_k,
            filters=filters
        )

        if result['success']:
            # 解析JSON响应
            import json
            try:
                # 提取JSON
                json_str = _extract_json_from_response(result['response'])
                if json_str:
                    diagnosis_data = json.loads(json_str)
                    result['parsed_response'] = diagnosis_data
            except Exception as e:
                logger.warning(f"Failed to parse JSON response: {e}")

            return result
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'RAG分析失败'))

    except Exception as e:
        logger.error(f"RAG analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/generate")
async def generate_pdf_report(request: PDFReportRequest, background_tasks: BackgroundTasks):
    """生成PDF报告"""
    try:
        pdf_generator = get_pdf_generator()

        # 生成PDF报告
        report_path = pdf_generator.generate_tongue_diagnosis_report(
            diagnosis_data=request.diagnosis_data,
            user_info=request.user_info,
            filename=request.filename
        )

        # 返回文件信息
        return {
            "success": True,
            "message": "PDF报告生成成功",
            "filename": Path(report_path).name,
            "path": report_path
        }
    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/download/{filename}")
async def download_pdf_report(filename: str):
    """下载PDF报告"""
    try:
        from api_service.core.rag_config import get_report_path

        report_path = get_report_path() / filename

        if not report_path.exists():
            raise HTTPException(status_code=404, detail="报告文件不存在")

        return FileResponse(
            path=str(report_path),
            media_type='application/pdf',
            filename=filename
        )
    except Exception as e:
        logger.error(f"Failed to download PDF report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/list")
async def list_pdf_reports():
    """列出可用的PDF报告"""
    try:
        from api_service.core.rag_config import get_report_path

        report_path = get_report_path()
        if not report_path.exists():
            return {
                "success": True,
                "reports": []
            }

        # 获取所有PDF文件
        pdf_files = list(report_path.glob("*.pdf"))

        # 按修改时间排序
        pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 准备文件信息
        reports = []
        for pdf_file in pdf_files:
            stat = pdf_file.stat()
            reports.append({
                "filename": pdf_file.name,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "download_url": f"/rag/report/download/{pdf_file.name}"
            })

        return {
            "success": True,
            "reports": reports,
            "count": len(reports)
        }
    except Exception as e:
        logger.error(f"Failed to list PDF reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/knowledge-base/reset")
async def reset_knowledge_base():
    """重置知识库"""
    try:
        vector_db = get_vector_db_manager()

        # 重置集合
        success = vector_db.reset_collection()

        if success:
            return {
                "success": True,
                "message": "知识库重置成功"
            }
        else:
            raise HTTPException(status_code=500, detail="知识库重置失败")

    except Exception as e:
        logger.error(f"Failed to reset knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-base/batch")
async def batch_add_documents(documents: List[DocumentUpload]):
    """批量添加文档到知识库"""
    try:
        vector_db = get_vector_db_manager()

        # 准备批量数据
        texts = [doc.text for doc in documents]
        metadatas = []
        ids = []

        for doc in documents:
            metadata = {
                "category": doc.category,
                "added_at": datetime.now().isoformat(),
                **doc.metadata
            }
            metadatas.append(metadata)
            ids.append(f"doc_{doc.category}_{datetime.now().timestamp()}_{hash(doc.text) % 10000}")

        # 批量添加文档
        success = vector_db.add_documents(
            texts=texts,
            metadatas=metadatas,
            ids=ids
        )

        if success:
            return {
                "success": True,
                "message": f"成功添加 {len(documents)} 个文档",
                "count": len(documents)
            }
        else:
            raise HTTPException(status_code=500, detail="批量添加文档失败")

    except Exception as e:
        logger.error(f"Failed to batch add documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_json_from_response(response: str) -> Optional[str]:
    """从响应中提取JSON"""
    import re

    patterns = [
        r'```json\s*(.*?)\s*```',
        r'\{.*\}',
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            json_str = match.group(1) if '{' not in match.group(0) else match.group(0)
            return json_str

    return None