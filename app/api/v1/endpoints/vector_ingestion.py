"""
向量摄入API接口
支持批量向量化并写入指定Milvus集合
"""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.services.vector_ingestion import VectorIngestionService
from app.schemas.vector_ingestion import (
    VectorIngestRequest, 
    VectorIngestResponse,
    VectorIngestData,
    FailedItem
)

router = APIRouter()


def get_vector_ingestion_service() -> VectorIngestionService:
    """获取向量摄入服务实例"""
    # 这里可以注入embedding服务
    # embedding_service = SomeEmbeddingService()
    # return VectorIngestionService(embedding_service=embedding_service)
    return VectorIngestionService()


@router.post("/{collection_name}/ingest", response_model=VectorIngestResponse)
async def ingest_vectors(
    collection_name: str = Path(..., description="集合名称"),
    request: VectorIngestRequest = ...,
    service: VectorIngestionService = Depends(get_vector_ingestion_service)
):
    """
    批量向量化并写入指定集合
    
    Args:
        collection_name: 集合名称，如 mirrors_clause_vectors
        request: 向量摄入请求
            - embedding_model: 使用的embedding模型
            - items: 向量摄入项列表
            
    Returns:
        向量摄入结果
    """
    try:
        # 调用服务处理请求
        result = await service.ingest_items_to_collection(collection_name, request)
        
        # 记录处理结果
        if result.code == 0:
            data = result.data
            total = data.get("total", 0)
            succeeded = data.get("succeeded", 0)
            failed = data.get("failed", 0)
            
            if failed == 0:
                logger.info(f"成功处理集合 {collection_name} 的向量摄入: 总数 {total}, 成功 {succeeded}")
            else:
                logger.warning(f"部分处理失败 集合 {collection_name}: 总数 {total}, 成功 {succeeded}, 失败 {failed}")
        else:
            logger.error(f"向量摄入失败: {result.message}")
        
        return result
        
    except Exception as e:
        logger.error(f"向量摄入处理异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"向量摄入处理异常: {str(e)}")