from typing import Text
from sqlalchemy import Column, String, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ParagraphSpan(BaseModel):
    __tablename__ = "paragraph_spans"

    # 基本信息
    id = Column(String(64), primary_key=True)
    owner_type = Column(String(32), nullable=False, comment="Clause/ClauseItem")
    owner_id = Column(String(64), nullable=False, comment="所属Clause或ClauseItem的ID")
    seq = Column(Integer, nullable=False, comment="序号")
    
    # 内容信息
    raw_text = Column(Text, nullable=False, comment="原段")
    style = Column(JSON, comment="粗体/字号/缩进/列表级")
    loc = Column(JSON, comment="位置信息")
    
    # 业务标签
    role = Column(String(32), default="NON_CLAUSE", comment="角色: CLAUSE/NON_CLAUSE")
    region = Column(String(32), comment="区域: COVER/MAIN/APPENDIX/SIGN/TOC")
    nc_type = Column(String(64), comment="非条款类型: 详细分类")
    content = Column(Text, comment="处理后的内容")
    
    # 关联关系
    owner_clause = relationship("Clause", back_populates="spans", foreign_keys=[owner_id])
    owner_item = relationship("ClauseItem", back_populates="spans", foreign_keys=[owner_id])
    
    def __repr__(self):
        return f"<ParagraphSpan(id={self.id}, owner_type={self.owner_type}, owner_id={self.owner_id})>"