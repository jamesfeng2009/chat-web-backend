from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Float, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Clause(BaseModel):
    __tablename__ = "clauses"

    # 关联文档和章节
    doc_id = Column(String(64), ForeignKey("documents.id"), nullable=False, comment="文档ID")
    section_id = Column(String(64), ForeignKey("sections.id"), nullable=True, comment="章节ID, 可为空")
    
    # 条款树结构
    parent_clause_id = Column(String(64), ForeignKey("clauses.id"), nullable=True, comment="父条款ID")
    
    # 条款信息
    number_token = Column(String(64), nullable=True, comment="条款编号，如'第七条'、'7.1'、'7.1.1'")
    title = Column(String(512), nullable=True, comment="条款标题文字，不含编号")
    content = Column(Text, nullable=False, comment="纯正文，不含子项文本")
    lang = Column(String(8), default="zh", comment="文本语种")
    order_index = Column(Integer, nullable=False, comment="全局顺序")
    
    # 向量信息
    embedding_id = Column(String(64), comment="Milvus中的向量ID")
    
    # 定位信息
    loc = Column(JSON, comment="定位信息: 字符区间、页段、样式线索")
    
    # 业务标签
    role = Column(String(32), default="CLAUSE", comment="角色: CLAUSE/NON_CLAUSE")
    region = Column(String(32), comment="区域: COVER/MAIN/APPENDIX/SIGN/TOC")
    nc_type = Column(String(64), comment="非条款类型: TITLE/PARTIES/CLAUSE_BODY/null")
    score = Column(Integer, comment="条款置信度: 1-4")
    
    # 关联关系
    document = relationship("Document", back_populates="clauses")
    section = relationship("Section", back_populates="clauses")
    parent_clause = relationship("Clause", remote_side="Clause.id")
    children = relationship("Clause", cascade="all, delete-orphan")
    items = relationship("ClauseItem", back_populates="clause", cascade="all, delete-orphan")
    spans = relationship("ParagraphSpan", back_populates="owner_clause", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Clause(id={self.id}, doc_id={self.doc_id}, title='{self.title}')>"