from pydantic import BaseModel, Field
from typing import Any

from datetime import datetime


class ClauseItemBase(BaseModel):
    title: str | None = Field(None, description="子项标题")
    order_index: int = Field(..., description="全局顺序")
    content: str | None = Field(None, description="子项内容")
    lang: str = Field(default="zh", description="文本语种")
    loc: dict[str, Any] | None = Field(None, description="定位信息")
    role: str = Field(default="CLAUSE", description="角色")
    region: str | None = Field(None, description="区域")
    nc_type: str | None = Field(None, description="非条款类型")


class ClauseItemCreate(ClauseItemBase):
    clause_id: str = Field(..., description="条款ID")
    parent_item_id: str | None = Field(None, description="父项ID")


class ClauseItemUpdate(BaseModel):
    title: str | None = Field(None, description="子项标题")
    order_index: int | None = Field(None, description="全局顺序")
    content: str | None = Field(None, description="子项内容")
    lang: str | None = Field(None, description="文本语种")
    loc: dict[str, Any] | None = Field(None, description="定位信息")
    role: str | None = Field(None, description="角色")
    region: str | None = Field(None, description="区域")
    nc_type: str | None = Field(None, description="非条款类型")


class ClauseItemResponse(ClauseItemBase):
    id: str
    clause_id: str
    parent_item_id: str | None
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime
    deleted: bool
    
    class Config:
        from_attributes = True


class ClauseItemListResponse(BaseModel):
    items: list[ClauseItemResponse]
    total: int
    page: int
    page_size: int


class ClauseItemWithChildrenResponse(ClauseItemResponse):
    children_items: list[ClauseItemResponse] = []