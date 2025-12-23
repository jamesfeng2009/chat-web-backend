from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.crud.base import CRUDBase
from app.models.document import Document
from app.schemas.document import DocumentCreate, DocumentUpdate


class CRUDDocument(CRUDBase[Document, DocumentCreate, DocumentUpdate]):
    def get_by_checksum(self, db: Session, checksum: str) -> Document | None:
        """
        根据校验和获取文档
        """
        return db.query(self.model).filter(
            and_(
                self.model.checksum == checksum,
                self.model.deleted == False
            )
        ).first()

    def get_by_name(self, db: Session, name: str) -> Document | None:
        """
        根据名称获取文档
        """
        return db.query(self.model).filter(
            and_(
                self.model.name == name,
                self.model.deleted == False
            )
        ).first()

    def get_multi_by_owner(
        self,
        db: Session,
        *,
        owner_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None
    ) -> list[Document]:
        """
        获取多个文档，支持所有者过滤和状态过滤
        """
        query = db.query(self.model).filter(self.model.deleted == False)
        
        if owner_id:
            # 假设文档元数据中包含所有者信息
            query = query.filter(self.model.metadata["owner"].astext == owner_id)
            
        if status:
            query = query.filter(self.model.status == status)
            
        return query.offset(skip).limit(limit).all()

    def get_multi_by_status(
        self, 
        db: Session, 
        *, 
        status: str,
        skip: int = 0, 
        limit: int = 100
    ) -> list[Document]:
        """
        根据状态获取文档列表
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.status == status,
                    self.model.deleted == False
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_multi_by_status_list(
        self, 
        db: Session, 
        *, 
        statuses: list[str],
        skip: int = 0, 
        limit: int = 100
    ) -> list[Document]:
        """
        根据状态列表获取文档列表
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.status.in_(statuses),
                    self.model.deleted == False
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search(
        self, 
        db: Session, 
        *, 
        keyword: str,
        skip: int = 0, 
        limit: int = 100
    ) -> list[Document]:
        """
        搜索文档（按名称）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    or_(
                        self.model.name.contains(keyword),
                        self.model.metadata["description"].astext.contains(keyword) if self.model.metadata.isnot(None) else False
                    ),
                    self.model.deleted == False
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_status(
        self,
        db: Session,
        *,
        db_obj: Document,
        status: str,
        parse_status: str | None = None,
        structure_status: str | None = None,
        vector_status: str | None = None
    ) -> Document:
        """
        更新文档状态
        """
        update_data = {"status": status}
        
        if parse_status:
            update_data["parse_status"] = parse_status
            
        if structure_status:
            update_data["structure_status"] = structure_status
            
        if vector_status:
            update_data["vector_status"] = vector_status
            
        return self.update(db, db_obj=db_obj, obj_in=update_data)


crud_document = CRUDDocument(Document)