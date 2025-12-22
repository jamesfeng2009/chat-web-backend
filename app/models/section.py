from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Section(BaseModel):
    __tablename__ = "sections"

    # 关联文档
    doc_id = Column(String(64), ForeignKey("documents.id"), nullable=False, comment="文档ID")
    
    # 树结构
    parent_id = Column(String(64), ForeignKey("sections.id"), nullable=True, comment="父section ID")
    
    # 章节信息
    title = Column(String(512), nullable=True, comment="标题文字，不含编号")
    content = Column(Text, nullable=True, comment="标题块内容（可选）")
    number_token = Column(String(64), nullable=True, comment="编号标记，如'第一章'、'1.'、'1.1'")
    level = Column(Integer, nullable=True, comment="大纲层级，从1起")
    order_index = Column(Integer, nullable=False, comment="全局顺序")
    
    # 定位信息
    loc = Column(JSON, comment="定位信息: 页码范围、字符偏移、样式提示等")
    
    # 关联关系
    document = relationship("Document", back_populates="sections")
    parent_section = relationship("Section", remote_side="Section.id")
    children = relationship("Section", cascade="all, delete-orphan")
    spans = relationship("ParagraphSpan", back_populates="owner_clause", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Section(id={self.id}, doc_id={self.doc_id}, title='{self.title}', level={self.level})>"