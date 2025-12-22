from sqlalchemy import Column, String, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    # 基本信息
    id = Column(String(64), primary_key=True, comment="文档ID，从外部传入")
    name = Column(String(512), nullable=False, comment="文档名称/标题")
    type = Column(String(64), nullable=True, comment="文档类型: 参考文本/模板等")
    ingest_channel = Column(String(32), default="upload", comment="导入渠道: web/batch/api")
    file_type = Column(String(32), nullable=False, comment="文件类型: pdf/docx/txt/md/html")
    checksum = Column(String(64), nullable=True, comment="文件SHA256校验和")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间（从外部传入）")
    
    # 文件存储信息
    file_url = Column(String(1024), nullable=True, comment="文档下载链接")
    rich_content = Column(Text, nullable=True, comment="文档富文本字符串")
    file_ref = Column(JSON, comment="文件存储引用, 如对象存储key、页数、MIME等")
    
    # 元数据
    drafters = Column(JSON, comment="起草人信息，如[{\"name\": \"zhangshuo\", \"status\": \"activate\"}]")
    metadata = Column(JSON, comment="文档元数据, 如其他业务字段")
    
    # 处理状态
    status = Column(String(32), default="uploaded", comment="状态: uploaded/parsed/structured/vectorized/failed")
    parse_status = Column(String(32), default="pending", comment="解析状态: pending/processing/completed/failed")
    structure_status = Column(String(32), default="pending", comment="结构化状态: pending/processing/completed/failed")
    vector_status = Column(String(32), default="pending", comment="向量化状态: pending/processing/completed/failed")
    
    # 关联关系
    sections = relationship("Section", back_populates="document", cascade="all, delete-orphan")
    clauses = relationship("Clause", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id={self.id}, name='{self.name}', status='{self.status}')>"