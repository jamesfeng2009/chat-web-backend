from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session


from app.core.database import get_db
from app.schemas.vector import (
    VectorSearchRequest, VectorSearchResponse
)
from app.services.search import search_service
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/semantic", response_model=VectorSearchResponse)
async def semantic_search(
    request: VectorSearchRequest,
    db: Session = Depends(get_db)
):
    """
    语义搜索
    """
    try:
        result = search_service.semantic_search(
            collection=request.collection,
            query=request.query,
            embedding_model=request.embedding_model,
            limit=request.limit,
            filters=request.filters,
            include_content=request.include_content
        )
        
        return VectorSearchResponse(**result)
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/semantic")
async def semantic_search_get(
    collection: str = Query(..., description="向量集合名称"),
    query: str = Query(..., description="查询文本"),
    embedding_model: str = Query(default="text-embedding-3-large", description="向量模型"),
    limit: int = Query(default=10, ge=1, le=100, description="返回结果数"),
    filters: str | None = Query(default=None, description="过滤条件(JSON格式)"),
    include_content: bool = Query(default=True, description="是否包含内容"),
    db: Session = Depends(get_db)
):
    """
    语义搜索（GET方式）
    """
    try:
        # 解析过滤条件
        filter_dict = None
        if filters:
            import json
            try:
                filter_dict = json.loads(filters)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid filters JSON")
        
        result = search_service.semantic_search(
            collection=collection,
            query=query,
            embedding_model=embedding_model,
            limit=limit,
            filters=filter_dict,
            include_content=include_content
        )
        
        return VectorSearchResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similarity", response_model=VectorSearchResponse)
async def similarity_search(
    request: VectorSearchRequest,
    db: Session = Depends(get_db)
):
    """
    相似度搜索
    """
    try:
        result = search_service.similarity_search(
            collection=request.collection,
            query=request.query,
            embedding_model=request.embedding_model,
            limit=request.limit,
            filters=request.filters,
            include_content=request.include_content
        )
        
        return VectorSearchResponse(**result)
    except Exception as e:
        logger.error(f"Error in similarity search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/similarity")
async def similarity_search_get(
    collection: str = Query(..., description="向量集合名称"),
    query: str = Query(..., description="查询文本"),
    embedding_model: str = Query(default="text-embedding-3-large", description="向量模型"),
    limit: int = Query(default=10, ge=1, le=100, description="返回结果数"),
    filters: str | None = Query(default=None, description="过滤条件(JSON格式)"),
    include_content: bool = Query(default=True, description="是否包含内容"),
    db: Session = Depends(get_db)
):
    """
    相似度搜索（GET方式）
    """
    try:
        # 解析过滤条件
        filter_dict = None
        if filters:
            import json
            try:
                filter_dict = json.loads(filters)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid filters JSON")
        
        result = search_service.similarity_search(
            collection=collection,
            query=query,
            embedding_model=embedding_model,
            limit=limit,
            filters=filter_dict,
            include_content=include_content
        )
        
        return VectorSearchResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in similarity search: {e}")
        raise HTTPException(status_code=500, detail=str(e))