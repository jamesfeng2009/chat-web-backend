"""
向量集合相关的数据模型
"""

from pydantic import BaseModel, Field


class VectorCollectionCreate(BaseModel):
    """创建向量集合的请求模型"""
    name: str = Field(..., description="集合名（同时作为 Milvus collection_name）")
    description: [str] = Field(None, description="业务描述，写给人看的")
    embedding_dimension: int = Field(..., description="向量维度（比如 768/1024/1536，对应你选的 embedding 模型）")
    options: [dict[str, any]] = Field(
        default={
            "shards_num": 2,
            "enable_dynamic_fields": True,
            "consistency_level": "Session"
        },
        description="Milvus 集合选项"
    )


class VectorCollectionResponse(BaseModel):
    """向量集合响应模型"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="响应消息")
    collection_name: [str] = Field(None, description="集合名称")
    collection_info: [dict[str, any]] = Field(None, description="集合详细信息")


class VectorCollectionInfo(BaseModel):
    """向量集合信息模型"""
    name: str
    description: [str]
    embedding_dimension: int
    options: dict[str, any]
    created_at: [str] = None
    status: str = "active"


class VectorCollectionList(BaseModel):
    """向量集合列表响应模型"""
    collections: list[VectorCollectionInfo]
    total: int