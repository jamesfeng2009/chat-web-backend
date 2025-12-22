"""
向量搜索API接口
提供语义搜索、相似度搜索和混合搜索功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.vector_ingestion import VectorIngestionService
from app.core.config import settings


router = APIRouter()


class VectorSearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询文本")
    collection_name: str = Field("mirrors_clause_vectors", description="向量集合名称")
    limit: int = Field(10, description="返回结果数量限制")
    filter_expr: [str] = Field(None, description="过滤表达式")
    output_fields: [list[str]] = Field(None, description="返回字段列表")
    search_params: [dict[str, any]] = Field(None, description="搜索参数")


class HybridSearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询文本")
    keywords: [list[str]] = Field(None, description="关键词列表")
    collection_name: str = Field("mirrors_clause_vectors", description="向量集合名称")
    limit: int = Field(10, description="返回结果数量限制")
    filter_expr: [str] = Field(None, description="过滤表达式")
    output_fields: [list[str]] = Field(None, description="返回字段列表")
    search_params: [dict[str, any]] = Field(None, description="搜索参数")
    semantic_weight: float = Field(0.7, description="语义搜索权重，范围0-1")
    keyword_weight: float = Field(0.3, description="关键词搜索权重，范围0-1")


def get_vector_service() -> VectorIngestionService:
    """获取向量化服务实例"""
    # 直接创建 VectorIngestionService，不使用 MilvusClient
    # VectorIngestionService 内部会自己处理 pymilvus 连接
    # 这里可以注入embedding服务，目前使用默认实现
    embedding_service = None
    return VectorIngestionService(embedding_service)


@router.post("/semantic_search")
async def semantic_search(
    request: VectorSearchRequest,
    vector_service: VectorIngestionService = Depends(get_vector_service)
):
    """
    语义搜索接口
    
    根据查询文本的语义相似度搜索相关条款
    
    Args:
        request: 搜索请求
    
    Returns:
        搜索结果
    """
    try:
        result = await vector_service.search_vectors(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语义搜索失败: {str(e)}")


@router.post("/hybrid_search")
async def hybrid_search(
    request: HybridSearchRequest,
    vector_service: VectorIngestionService = Depends(get_vector_service)
):
    """
    混合搜索接口
    
    结合语义搜索和关键词搜索，提供更准确的搜索结果
    
    Args:
        request: 搜索请求
    
    Returns:
        搜索结果
    """
    try:
        # 确保权重总和为1
        total_weight = request.semantic_weight + request.keyword_weight
        if abs(total_weight - 1.0) > 0.01:
            # 标准化权重
            request.semantic_weight = request.semantic_weight / total_weight
            request.keyword_weight = request.keyword_weight / total_weight
        
        # 语义搜索
        semantic_request = VectorSearchRequest(
            query=request.query,
            collection_name=request.collection_name,
            limit=request.limit,
            filter_expr=request.filter_expr,
            output_fields=request.output_fields,
            search_params=request.search_params
        )
        semantic_result = await vector_service.search_vectors(semantic_request)
        
        # 关键词搜索（这里简化处理，实际应该实现真正的关键词搜索）
        keyword_results = []
        if request.keywords:
            # 实际实现中，这里应该基于关键词搜索文本内容
            # 现在只是占位实现
            pass
        
        # 合并结果
        merged_results = _merge_search_results(
            semantic_result, keyword_results, 
            request.semantic_weight, request.keyword_weight, 
            request.limit
        )
        
        return {
            "success": True,
            "query": request.query,
            "keywords": request.keywords,
            "total": len(merged_results),
            "results": merged_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"混合搜索失败: {str(e)}")


@router.get("/clause/{clause_id}")
async def get_clause_by_id(
    clause_id: str,
    collection_name: str = Query("mirrors_clause_vectors", description="向量集合名称"),
    vector_service: VectorIngestionService = Depends(get_vector_service)
):
    """
    根据条款ID获取详情
    
    Args:
        clause_id: 条款ID
        collection_name: 向量集合名称
    
    Returns:
        条款详情
    """
    try:
        # 构建过滤表达式
        filter_expr = f"clause_id == '{clause_id}'"
        
        # 构建搜索请求
        search_request = VectorSearchRequest(
            query="",  # 空查询，只用于过滤
            collection_name=collection_name,
            limit=1,
            filter_expr=filter_expr
        )
        
        result = await vector_service.search_vectors(search_request)
        
        if not result.get("success") or not result.get("results"):
            raise HTTPException(status_code=404, detail=f"未找到条款: {clause_id}")
        
        return {
            "success": True,
            "clause": result["results"][0]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取条款失败: {str(e)}")


@router.get("/document/{doc_id}/clauses")
async def get_document_clauses(
    doc_id: str,
    collection_name: str = Query("mirrors_clause_vectors", description="向量集合名称"),
    vector_service: VectorIngestionService = Depends(get_vector_service)
):
    """
    获取文档的所有条款
    
    Args:
        doc_id: 文档ID
        collection_name: 向量集合名称
    
    Returns:
        文档条款列表
    """
    try:
        # 构建过滤表达式
        filter_expr = f"doc_id == '{doc_id}' && unit_type == 'CLAUSE'"
        
        # 构建搜索请求
        search_request = VectorSearchRequest(
            query="",  # 空查询，只用于过滤
            collection_name=collection_name,
            limit=1000,  # 设置一个较大的限制
            filter_expr=filter_expr
        )
        
        result = await vector_service.search_vectors(search_request)
        
        return {
            "success": True,
            "doc_id": doc_id,
            "total": result.get("total", 0),
            "clauses": result.get("results", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档条款失败: {str(e)}")


@router.get("/document/{doc_id}/clause_items")
async def get_document_clause_items(
    doc_id: str,
    clause_id: [str] = Query(None, description="指定条款ID，只返回该条款的子项"),
    collection_name: str = Query("mirrors_clause_vectors", description="向量集合名称"),
    vector_service: VectorIngestionService = Depends(get_vector_service)
):
    """
    获取文档的条款子项
    
    Args:
        doc_id: 文档ID
        clause_id: 可选，指定条款ID
        collection_name: 向量集合名称
    
    Returns:
        文档条款子项列表
    """
    try:
        # 构建过滤表达式
        filter_expr = f"doc_id == '{doc_id}' && unit_type == 'CLAUSE_ITEM'"
        
        if clause_id:
            filter_expr += f" && clause_id == '{clause_id}'"
        
        # 构建搜索请求
        search_request = VectorSearchRequest(
            query="",  # 空查询，只用于过滤
            collection_name=collection_name,
            limit=1000,  # 设置一个较大的限制
            filter_expr=filter_expr
        )
        
        result = await vector_service.search_vectors(search_request)
        
        return {
            "success": True,
            "doc_id": doc_id,
            "clause_id": clause_id,
            "total": result.get("total", 0),
            "clause_items": result.get("results", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档条款子项失败: {str(e)}")


def _merge_search_results(
    semantic_result: dict[str, any],
    keyword_results: list[dict[str, any]],
    semantic_weight: float,
    keyword_weight: float,
    limit: int
) -> list[dict[str, any]]:
    """
    合并语义搜索和关键词搜索结果
    
    Args:
        semantic_result: 语义搜索结果
        keyword_results: 关键词搜索结果
        semantic_weight: 语义搜索权重
        keyword_weight: 关键词搜索权重
        limit: 返回结果数量限制
    
    Returns:
        合并后的结果
    """
    # 这里简化处理，实际实现应该更复杂
    merged_results = []
    
    # 处理语义搜索结果
    if semantic_result.get("success") and semantic_result.get("results"):
        for item in semantic_result["results"]:
            # 计算综合分数
            distance = item.get("distance", 1.0)
            # 将距离转换为相似度分数（0-1）
            semantic_score = 1.0 - min(1.0, max(0.0, distance))
            
            item["semantic_score"] = semantic_score
            item["keyword_score"] = 0.0
            item["combined_score"] = semantic_score * semantic_weight
            
            merged_results.append(item)
    
    # 处理关键词搜索结果
    for item in keyword_results:
        # 计算综合分数
        keyword_score = item.get("score", 1.0)
        
        item["semantic_score"] = 0.0
        item["keyword_score"] = keyword_score
        item["combined_score"] = keyword_score * keyword_weight
        
        merged_results.append(item)
    
    # 按综合分数排序
    merged_results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    
    # 限制返回数量
    return merged_results[:limit]