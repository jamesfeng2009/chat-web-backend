"""
文档摘要 API 端点
实现时间线摘要、RAG摘要、全局概要三种摘要模式
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.services.document_summary import document_summary_service
from app.schemas.document_summary import (
    TimelineSummaryRequest,
    RAGSummaryRequest,
    GlobalSummaryRequest,
    TimelineSummaryResponse,
    RAGSummaryResponse,
    GlobalSummaryResponse,
    ErrorResponse
)
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/timeline",
    response_model=TimelineSummaryResponse,
    summary="时间线摘要",
    description="从文档中抽取时间事件，生成按时间顺序排列的摘要"
)
async def timeline_summary(
    request: TimelineSummaryRequest,
    db: deps.Database = Depends(deps.get_db)
):
    """
    时间线摘要

    抽取文档中的时间相关信息，包括：
    - 日期识别和规范化
    - 时间事件排序
    - 事件描述润色

    参数：
    - doc_ids: 文档ID列表

    返回：
    - 按时间顺序排列的事件列表
    """
    try:
        logger.info(f"收到时间线摘要请求，文档数量: {len(request.doc_ids)}")

        result = await document_summary_service.timeline_summary(
            doc_ids=request.doc_ids,
            db=db
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "时间线摘要失败")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"时间线摘要 API 错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}"
        )


@router.post(
    "/rag",
    response_model=RAGSummaryResponse,
    summary="自定义摘要（RAG）",
    description="根据用户查询，检索相关文档内容并生成摘要"
)
async def rag_summary(
    request: RAGSummaryRequest,
    db: deps.Database = Depends(deps.get_db)
):
    """
    自定义摘要（RAG 技术）

    根据用户的问题，从向量数据库检索相关内容，生成准确的摘要：
    - 语义搜索相关文档片段
    - 基于检索内容生成答案
    - 返回引用来源

    参数：
    - query: 用户查询/问题
    - doc_ids: 文档ID列表（可选，不提供则搜索所有文档）
    - collection_name: 向量集合名称
    - top_k: 返回相关片段数量

    返回：
    - 基于检索内容的准确摘要
    - 相关片段来源列表
    """
    try:
        logger.info(f"收到 RAG 摘要请求，查询: {request.query}")

        result = await document_summary_service.rag_summary(
            query=request.query,
            doc_ids=request.doc_ids,
            db=db,
            collection_name=request.collection_name or "mirrors_clause_vectors",
            top_k=request.top_k or 10
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "RAG 摘要失败")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG 摘要 API 错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}"
        )


@router.post(
    "/global",
    response_model=GlobalSummaryResponse,
    summary="全局概要",
    description="对多个文档生成全局概要，支持跨文档汇总和知识图谱构建"
)
async def global_summary(
    request: GlobalSummaryRequest,
    db: deps.Database = Depends(deps.get_db)
):
    """
    全局概要

    对多个文档生成统一的概要摘要：
    - 对每个文档生成内部摘要
    - 抽取重要实体
    - 生成跨文档的全局概览
    - 可选：构建实体关系图谱

    参数：
    - doc_ids: 文档ID列表
    - build_knowledge_graph: 是否构建知识图谱（默认：false）

    返回：
    - 各文档独立摘要
    - 实体列表
    - 全局概览（共同点、差异点）
    - 知识图谱（可选）
    """
    try:
        logger.info(f"收到全局概要请求，文档数量: {len(request.doc_ids)}")

        result = await document_summary_service.global_summary(
            doc_ids=request.doc_ids,
            db=db,
            build_knowledge_graph=request.build_knowledge_graph or False
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "全局概要失败")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"全局概要 API 错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查摘要服务状态"
)
async def health_check():
    """
    摘要服务健康检查
    """
    return {
        "service": "document-summary",
        "status": "healthy",
        "endpoints": {
            "timeline": "/timeline",
            "rag": "/rag",
            "global": "/global"
        }
    }
