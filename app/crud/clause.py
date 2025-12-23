
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.crud.base import CRUDBase
from app.models.clause import Clause
from app.schemas.clause import ClauseCreate, ClauseUpdate


class CRUDClause(CRUDBase[Clause, ClauseCreate, ClauseUpdate]):
    def get_by_document(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[Clause]:
        """
        获取文档的所有条款
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
    ) -> list[Clause]:
        """
        获取文档的所有条款（不分页）
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

    def get_by_section(
        self, 
        db: Session, 
        *, 
        section_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[Clause]:
        """
        获取章节的所有条款
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.section_id == section_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_without_embedding(
        self, 
        db: Session, 
        *, 
        skip: int = 0,
        limit: int = 100
    ) -> list[Clause]:
        """
        获取尚未向量化的条款
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.embedding_id.is_(None),
                    self.model.deleted == False
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_without_embedding_by_document(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[Clause]:
        """
        获取特定文档中尚未向量化的条款
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.doc_id == doc_id,
                    self.model.embedding_id.is_(None),
                    self.model.deleted == False
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order_index(
        self,
        db: Session,
        *,
        doc_id: str,
        order_index: int
    ) -> Clause | None:
        """
        根据顺序获取条款
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

    def update_embedding(
        self, 
        db: Session, 
        *, 
        db_obj: Clause,
        embedding_id: str
    ) -> Clause:
        """
        更新条款的向量信息
        """
        update_data = {
            "embedding_id": embedding_id
        }
        return self.update(db, db_obj=db_obj, obj_in=update_data)

    def update_embedding_id(
        self,
        db: Session,
        *,
        id: str,
        embedding_id: str
    ) -> Clause | None:
        """
        通过ID更新条款的向量ID
        """
        db_obj = self.get(db, id=id)
        if not db_obj:
            return None
            
        update_data = {"embedding_id": embedding_id}
        return self.update(db, db_obj=db_obj, obj_in=update_data)

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
        objs_in: list[ClauseCreate]
    ) -> list[Clause]:
        """
        批量创建条款
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
        统计文档的条款数量
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
        删除文档的所有条款（软删除）
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


crud_clause = CRUDClause(Clause)