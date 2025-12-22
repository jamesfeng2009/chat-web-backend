from pydantic import BaseModel, Field



class VectorCollectionCreate(BaseModel):
    name: str = Field(..., description="集合名称")
    description: [str] = Field(None, description="业务描述")
    embedding_dimension: int = Field(..., description="向量维度")
    options: [dict[str, any]] = Field(
        default={
            "shards_num": 2,
            "enable_dynamic_fields": True,
            "consistency_level": "Session"
        },
        description="集合选项"
    )


class VectorCollectionResponse(BaseModel):
    name: str
    description: [str]
    embedding_dimension: int
    created_at: [str]
    status: str


class VectorCollectionListResponse(BaseModel):
    collections: list[VectorCollectionResponse]
    total: int


class VectorItemBase(BaseModel):
    unit_type: str = Field(..., description="单元类型: CLAUSE/CLAUSE_ITEM")
    doc_id: str = Field(..., description="文档ID")
    doc_name: str = Field(..., description="文档名称")
    section_id: [str] = Field(None, description="章节ID")
    section_title: [str] = Field(None, description="章节标题")
    section_level: [int] = Field(None, description="章节层级")
    clause_id: [str] = Field(None, description="条款ID")
    clause_title: [str] = Field(None, description="条款标题")
    clause_order_index: [int] = Field(None, description="条款顺序")
    item_id: [str] = Field(None, description="子项ID")
    parent_item_id: [str] = Field(None, description="父项ID")
    item_order_index: [int] = Field(None, description="子项顺序")
    lang: str = Field(default="zh", description="文本语种")
    role: str = Field(..., description="角色")
    region: [str] = Field(None, description="区域")
    nc_type: [str] = Field(None, description="非条款类型")
    content: str = Field(..., description="文本内容")
    loc: [dict[str, any]] = Field(None, description="定位信息")
    embedding: [list[float]] = Field(None, description="向量数据")
    biz_tags: [dict[str, any]] = Field(None, description="业务标签")


class VectorIngestRequest(BaseModel):
    embedding_model: str = Field(..., description="向量模型")
    batch_size: [int] = Field(100, description="批量大小")
    upsert: [bool] = Field(False, description="是否更新")
    async: [bool] = Field(False, description="是否异步处理")
    items: list[VectorItemBase] = Field(..., description="向量数据列表")


class VectorIngestResponse(BaseModel):
    collection: str
    total: int
    succeeded: int
    failed: int
    failed_items: list[dict[str, any]]
    job_id: [str] = None  # 异步任务ID


class VectorSearchRequest(BaseModel):
    collection: str = Field(..., description="集合名称")
    query: str = Field(..., description="查询文本")
    embedding_model: str = Field(default="text-embedding-3-large", description="向量模型")
    limit: int = Field(default=10, description="返回结果数")
    filters: [dict[str, any]] = Field(None, description="过滤条件")
    include_content: bool = Field(default=True, description="是否包含内容")


class VectorSearchResponse(BaseModel):
    query: str
    total: int
    items: list[dict[str, any]]