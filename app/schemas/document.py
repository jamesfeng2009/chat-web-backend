from pydantic import BaseModel, Field
from typing import Any

from datetime import datetime


class DocumentBase(BaseModel):
    name: str = Field(..., description="文档名称")
    ingest_channel: str = Field(default="upload", description="导入渠道")
    file_type: str = Field(..., description="文件类型")
    checksum: str | None = Field(None, description="文件校验和")
    file_ref: dict[str, Any] | None = Field(None, description="文件存储引用")
    metadata: dict[str, Any] | None = Field(None, description="文档元数据")


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    name: str | None = Field(None, description="文档名称")
    metadata: dict[str, Any] | None = Field(None, description="文档元数据")
    status: str | None = Field(None, description="处理状态")
    parse_status: str | None = Field(None, description="解析状态")
    structure_status: str | None = Field(None, description="结构化状态")
    vector_status: str | None = Field(None, description="向量化状态")


class DocumentResponse(DocumentBase):
    id: str
    created_at: datetime
    updated_at: datetime
    deleted: bool
    status: str
    parse_status: str
    structure_status: str
    vector_status: str
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentUploadResponse(BaseModel):
    document_id: str
    name: str
    file_type: str
    size: int
    status: str
    message: str