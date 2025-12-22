from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Text

from app.models.base import BaseModel


class ClauseItem(BaseModel):
    __tablename__ = "clause_items"

    # 关联条款
    clause_id = Column(String(64), ForeignKey("clauses.id"), nullable=False, comment="条款ID")
    parent_item_id = Column(String(64), ForeignKey("clause_items.id"), nullable=True, comment="父项ID, 形成树状")
    
    # 子项信息
    number_token = Column(String(64), nullable=True, comment="子项编号，如'(一)'、'1.'、'(a)'")
    title = Column(String(512), nullable=True, comment="子项标题，不含编号")
    content = Column(Text, nullable=True, comment="子项正文内容")
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
    clause = relationship("Clause", back_populates="items")
    parent_item = relationship("ClauseItem", remote_side="ClauseItem.id")
    children_items = relationship("ClauseItem", cascade="all, delete-orphan")
    spans = relationship("ParagraphSpan", back_populates="owner_item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ClauseItem(id={self.id}, clause_id={self.clause_id}, title='{self.title}')>"