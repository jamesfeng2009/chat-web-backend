
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.crud.base import CRUDBase
from app.models.section import Section
from app.schemas.section import SectionCreate, SectionUpdate


class CRUDSection(CRUDBase[Section, SectionCreate, SectionUpdate]):
    def get_by_document(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[Section]:
        """
        获取文档的所有章节
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_document_all(
        self, 
        db: Session, 
        *, 
        doc_id: str
    ) -> list[Section]:
        """
        获取文档的所有章节（不分页）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .all()
        )

    def get_by_level(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        level: int
    ) -> list[Section]:
        """
        获取文档的特定层级的章节
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.level == level,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .all()
        )

    def get_by_order_index(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        order_index: int
    ) -> Section | None:
        """
        根据顺序获取章节
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.order_index == order_index,
                    self.model.deleted == False
                )
            )
            .first()
        )

    def get_next_order_index(
        self, 
        db: Session, 
        *, 
        doc_id: str
    ) -> int:
        """
        获取下一个顺序号
        """
        max_order = (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index.desc())
            .first()
        )
        
        return (max_order.order_index + 1) if max_order else 1

    def create_multiple(
        self,
        db: Session,
        *,
        objs_in: list[SectionCreate]
    ) -> list[Section]:
        """
        批量创建章节
        """
        db_objs = []
        for obj_in in objs_in:
            db_obj = self.model(**obj_in.dict())
            db.add(db_obj)
            db_objs.append(db_obj)

        db.commit()
        for db_obj in db_objs:
            db.refresh(db_obj)

        return db_objs

    def count_by_doc_id(self, db: Session, *, doc_id: str) -> int:
        """
        统计文档的章节数量
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.deleted == False
                )
            )
            .count()
        )

    def delete_by_doc_id(self, db: Session, *, doc_id: str) -> int:
        """
        删除文档的所有章节（软删除）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.deleted == False
                )
            )
            .update({"deleted": True}, synchronize_session=False)
        )


crud_section = CRUDSection(Section)