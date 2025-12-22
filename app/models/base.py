from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class BaseModel(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted = Column(Boolean, default=False)  # 逻辑删除
    
    def to_dict(self):
        """将模型对象转换为字典"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if value is not None:
                # 处理datetime类型
                if hasattr(value, 'isoformat'):
                    result[column.name] = value.isoformat()
                else:
                    result[column.name] = value
            else:
                result[column.name] = None
        return result