
from pydantic import BaseModel, Field
from typing import Any


class ParagraphSpanBase(BaseModel):
    """段落基础模型"""
    owner_type: str = Field(..., description="Clause/ClauseItem")
    owner_id: str = Field(..., description="所属Clause或ClauseItem的ID")
    seq: int = Field(..., description="序号")
    raw_text: str = Field(..., description="原段")
    style: dict[str, Any] | None = Field(None, description="粗体/字号/缩进/列表级")
    loc: dict[str, Any] | None = Field(None, description="位置信息")

    # 业务标签
    role: str = Field("NON_CLAUSE", description="角色: CLAUSE/NON_CLAUSE")
    region: str | None = Field(None, description="区域: COVER/MAIN/APPENDIX/SIGN/TOC")
    nc_type: str | None = Field(None, description="非条款类型: 详细分类")
    content: str | None = Field(None, description="处理后的内容")


class ParagraphSpanCreate(ParagraphSpanBase):
    """创建段落模型"""
    id: str = Field(..., description="段落ID")


class ParagraphSpanUpdate(BaseModel):
    """更新段落模型"""
    owner_type: str | None = Field(None, description="Clause/ClauseItem")
    owner_id: str | None = Field(None, description="所属Clause或ClauseItem的ID")
    seq: int | None = Field(None, description="序号")
    raw_text: str | None = Field(None, description="原段")
    style: dict[str, Any] | None = Field(None, description="粗体/字号/缩进/列表级")
    loc: dict[str, Any] | None = Field(None, description="位置信息")

    # 业务标签
    role: str | None = Field(None, description="角色: CLAUSE/NON_CLAUSE")
    region: str | None = Field(None, description="区域: COVER/MAIN/APPENDIX/SIGN/TOC")
    nc_type: str | None = Field(None, description="非条款类型: 详细分类")
    content: str | None = Field(None, description="处理后的内容")


class ParagraphSpan(ParagraphSpanBase):
    """段落响应模型"""
    id: str
    
    class Config:
        orm_mode = True