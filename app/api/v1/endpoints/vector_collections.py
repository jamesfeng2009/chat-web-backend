"""
向量集合管理API接口
提供Milvus向量集合的创建、查询、删除等功能
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logger import logger
from app.services.vector_collection import VectorCollectionService
from app.schemas.vector_collection import (
    VectorCollectionCreate,
    VectorCollectionResponse,
    VectorCollectionInfo,
    VectorCollectionList
)

router = APIRouter()


def get_vector_collection_service() -> VectorCollectionService:
    """获取向量集合服务实例"""
    return VectorCollectionService()


@router.post("/", response_model=VectorCollectionResponse)
async def create_vector_collection(
    collection_data: VectorCollectionCreate,
    service: VectorCollectionService = Depends(get_vector_collection_service)
):
    """
    创建新的向量集合
    
    Args:
        collection_data: 集合创建参数
        service: 向量集合服务
        
    Returns:
        创建结果
    """
    try:
        result = service.create_collection(collection_data)
        
        if result["success"]:
            return VectorCollectionResponse(
                success=True,
                message=result["message"],
                collection_name=result["collection_name"],
                collection_info=result.get("collection_info")
            )
        else:
            raise HTTPException(status_code=400, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建向量集合失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建向量集合失败: {str(e)}")


@router.get("/", response_model=VectorCollectionList)
async def list_vector_collections(
    service: VectorCollectionService = Depends(get_vector_collection_service)
):
    """
    列出所有向量集合
    
    Args:
        service: 向量集合服务
        
    Returns:
        集合列表
    """
    try:
        result = service.list_collections()
        
        if result["success"]:
            # 转换为响应模型
            collections = []
            for collection in result["collections"]:
                # 处理错误信息
                if "error" in collection:
                    collections.append(VectorCollectionInfo(
                        name=collection["name"],
                        description=f"错误: {collection['error']}",
                        embedding_dimension=0,
                        options={},
                        status="error"
                    ))
                else:
                    # 正常集合信息
                    collections.append(VectorCollectionInfo(
                        name=collection["name"],
                        description=collection.get("description", ""),
                        embedding_dimension=0,  # 需要从schema中获取，这里暂时设为0
                        options={},
                        status="active"
                    ))
            
            return VectorCollectionList(
                collections=collections,
                total=result["total"]
            )
        else:
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出向量集合失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出向量集合失败: {str(e)}")


@router.get("/{collection_name}")
async def get_vector_collection(
    collection_name: str,
    service: VectorCollectionService = Depends(get_vector_collection_service)
):
    """
    获取向量集合详细信息
    
    Args:
        collection_name: 集合名称
        service: 向量集合服务
        
    Returns:
        集合详细信息
    """
    try:
        result = service.get_collection_info(collection_name)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=404, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取集合信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取集合信息失败: {str(e)}")


@router.delete("/{collection_name}")
async def delete_vector_collection(
    collection_name: str,
    service: VectorCollectionService = Depends(get_vector_collection_service)
):
    """
    删除向量集合
    
    Args:
        collection_name: 集合名称
        service: 向量集合服务
        
    Returns:
        删除结果
    """
    try:
        result = service.drop_collection(collection_name)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "collection_name": result["collection_name"]
            }
        else:
            raise HTTPException(status_code=404, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除向量集合失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除向量集合失败: {str(e)}")