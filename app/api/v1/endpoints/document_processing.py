"""
文档处理API接口
支持三管线LLM标注和向量摄入
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Body
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.services.document_processing import DocumentProcessingService
from app.schemas.vector_ingestion import VectorIngestItem

router = APIRouter()


class DocumentProcessingRequest(BaseModel):
    """文档处理请求模型"""
    document_content: str = Field(..., description="文档内容")
    doc_id: str = Field(..., description="文档ID")
    doc_name: str = Field(..., description="文档名称")
    embedding_model: str = Field("text-embedding-3-large", description="嵌入模型")
    collection_name: str = Field("mirrors_clause_vectors", description="向量集合名称")
    lang: str = Field("zh", description="语言代码")
    score_threshold: str = Field("1", description="条款分数阈值")


class DocumentLabelingRequest(BaseModel):
    """文档标注请求模型"""
    document_content: str = Field(..., description="文档内容")
    doc_id: str = Field(..., description="文档ID")
    doc_name: str = Field(..., description="文档名称")
    lang: str = Field("zh", description="语言代码")


class VectorIngestionRequest(BaseModel):
    """向量摄入请求模型"""
    items: list[VectorIngestItem] = Field(..., description="向量摄入项列表")
    embedding_model: str = Field("text-embedding-3-large", description="嵌入模型")
    collection_name: str = Field("mirrors_clause_vectors", description="向量集合名称")


def get_document_processing_service() -> DocumentProcessingService:
    """获取文档处理服务实例"""
    # 这里可以注入embedding服务
    # embedding_service = SomeEmbeddingService()
    # return DocumentProcessingService(embedding_service=embedding_service)
    return DocumentProcessingService()


@router.post("/process-document", response_model=dict[str, any])
async def process_document(
    request: DocumentProcessingRequest,
    service: DocumentProcessingService = Depends(get_document_processing_service)
):
    """
    处理文档：解析结构、LLM标注、向量化和存储
    
    Args:
        request: 文档处理请求
            
    Returns:
        处理结果
    """
    try:
        result = await service.process_document(
            document_content=request.document_content,
            doc_id=request.doc_id,
            doc_name=request.doc_name,
            embedding_model=request.embedding_model,
            collection_name=request.collection_name,
            lang=request.lang,
            score_threshold=request.score_threshold
        )
        
        # 记录处理结果
        if result["success"]:
            data = result["data"]
            total = data.get("total_segments", 0)
            clauses = len(data.get("clause_units", []))
            ingested = data.get("ingested", 0)
            
            logger.info(f"成功处理文档 {request.doc_name}: 段落 {total}, 条款 {clauses}, 摄入 {ingested}")
        else:
            logger.warning(f"文档处理部分或完全失败: {result['message']}")
        
        return result
        
    except Exception as e:
        logger.error(f"文档处理异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档处理异常: {str(e)}")


@router.post("/label-document", response_model=dict[str, any])
async def label_document(
    request: DocumentLabelingRequest,
    service: DocumentProcessingService = Depends(get_document_processing_service)
):
    """
    仅进行文档标注，不执行向量化和存储
    
    Args:
        request: 文档标注请求
            
    Returns:
        标注结果
    """
    try:
        result = await service.label_document_only(
            document_content=request.document_content,
            doc_id=request.doc_id,
            doc_name=request.doc_name,
            lang=request.lang
        )
        
        # 记录标注结果
        if result["success"]:
            data = result["data"]
            total = data.get("total_segments", 0)
            clauses = len(data.get("clause_units", []))
            
            logger.info(f"成功标注文档 {request.doc_name}: 段落 {total}, 条款 {clauses}")
        else:
            logger.warning(f"文档标注失败: {result['message']}")
        
        return result
        
    except Exception as e:
        logger.error(f"文档标注异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档标注异常: {str(e)}")


@router.post("/ingest-items", response_model=dict[str, any])
async def ingest_prepared_items(
    request: VectorIngestionRequest,
    service: DocumentProcessingService = Depends(get_document_processing_service)
):
    """
    向量化并存储预先准备好的条款项
    
    Args:
        request: 向量摄入请求
            
    Returns:
        摄入结果
    """
    try:
        result = await service.ingest_prepared_items(
            ingest_items=request.items,
            embedding_model=request.embedding_model,
            collection_name=request.collection_name
        )
        
        # 记录摄入结果
        if result["success"] and "data" in result:
            data = result.get("data", {})
            succeeded = data.get("succeeded", 0)
            
            logger.info(f"成功摄入条款项: 成功 {succeeded}")
        else:
            logger.warning(f"条款项摄入部分或完全失败: {result['message']}")
        
        return result
        
    except Exception as e:
        logger.error(f"条款项摄入异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"条款项摄入异常: {str(e)}")