from pydantic import BaseModel, Field

from datetime import datetime


class SectionBase(BaseModel):
    title: [str] = Field(None, description="章节标题")
    level: int = Field(..., description="大纲层级")
    order_index: int = Field(..., description="全局顺序")
    loc: [dict[str, any]] = Field(None, description="定位信息")
    role: [str] = Field(default="NON_CLAUSE", description="角色")
    region: [str] = Field(None, description="区域")
    nc_type: [str] = Field(None, description="非条款类型")


class SectionCreate(SectionBase):
    doc_id: str = Field(..., description="文档ID")


class SectionUpdate(BaseModel):
    title: [str] = Field(None, description="章节标题")
    level: [int] = Field(None, description="大纲层级")
    order_index: [int] = Field(None, description="全局顺序")
    loc: [dict[str, any]] = Field(None, description="定位信息")
    role: [str] = Field(None, description="角色")
    region: [str] = Field(None, description="区域")
    nc_type: [str] = Field(None, description="非条款类型")


class SectionResponse(SectionBase):
    id: str
    doc_id: str
    created_at: datetime
    updated_at: datetime
    deleted: bool
    
    class Config:
        from_attributes = True


class SectionListResponse(BaseModel):
    items: list[SectionResponse]
    total: int
    page: int
    page_size: int