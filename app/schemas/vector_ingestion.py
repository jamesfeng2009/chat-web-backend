"""
向量摄入相关的数据模型
"""

from pydantic import BaseModel, Field


class VectorIngestItem(BaseModel):
    """向量摄入项模型"""
    unit_type: str = Field(..., description="单元类型: CLAUSE/CLAUSE_ITEM")
    
    # 文档级字段
    doc_id: str = Field(..., description="文档ID")
    doc_name: str = Field(..., description="文档名称")
    
    # 章节级字段
    section_id: [str] = Field(None, description="章节ID")
    section_title: [str] = Field(None, description="章节标题")
    section_level: [int] = Field(None, description="章节层级")
    
    # 条款级字段
    clause_id: [str] = Field(None, description="条款ID")
    clause_title: [str] = Field(None, description="条款标题")
    clause_order_index: [int] = Field(None, description="条款顺序")
    
    # 子项级字段
    item_id: [str] = Field(None, description="子项ID")
    parent_item_id: [str] = Field(None, description="父子项ID")
    item_order_index: [int] = Field(None, description="子项顺序")
    
    # 业务属性
    lang: str = Field("zh", description="语言")
    role: str = Field(..., description="角色: CLAUSE/NON_CLAUSE")
    region: str = Field(..., description="区域: MAIN/COVER/APPENDIX/SIGN")
    nc_type: [str] = Field(None, description="内容类型")
    score: [str] = Field(None, description="条款分数: 0-4")
    
    # 文本与定位
    content: str = Field(..., description="向量化源文本")
    loc: [dict[str, any]] = Field(None, description="定位信息")
    biz_tags: [dict[str, any]] = Field(None, description="业务标签")
    
    # 向量（可选）
    embedding: [list[float]] = Field(None, description="预计算的向量，可为null由服务端计算")


class VectorIngestRequest(BaseModel):
    """向量摄入请求模型"""
    embedding_model: str = Field(..., description="使用的embedding模型")
    items: list[VectorIngestItem] = Field(..., description="向量摄入项列表")


class VectorIngestResponse(BaseModel):
    """向量摄入响应模型"""
    code: int = Field(..., description="状态码: 0-成功")
    message: str = Field(..., description="响应消息")
    data: dict[str, any] = Field(..., description="响应数据")


class VectorIngestData(BaseModel):
    """向量摄入数据模型"""
    collection: str = Field(..., description="集合名称")
    total: int = Field(..., description="总数")
    succeeded: int = Field(..., description="成功数")
    failed: int = Field(..., description="失败数")
    failed_items: list[dict[str, any]] = Field([], description="失败项列表")


class FailedItem(BaseModel):
    """失败项模型"""
    index: int = Field(..., description="失败项索引")
    reason: str = Field(..., description="失败原因")