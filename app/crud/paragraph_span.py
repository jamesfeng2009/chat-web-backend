
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.crud.base import CRUDBase
from app.models.paragraph_span import ParagraphSpan
from app.schemas.paragraph_span import ParagraphSpanCreate, ParagraphSpanUpdate


class CRUDParagraphSpan(CRUDBase[ParagraphSpan, ParagraphSpanCreate, ParagraphSpanUpdate]):
    def get_by_clause(
        self, 
        db: Session, 
        *, 
        clause_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ParagraphSpan]:
        """
        获取条款的所有段落
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.owner_type == "Clause",
                    self.model.owner_id == clause_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.seq)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_clause_all(
        self, 
        db: Session, 
        *, 
        clause_id: str
    ) -> list[ParagraphSpan]:
        """
        获取条款的所有段落（不分页）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.owner_type == "Clause",
                    self.model.owner_id == clause_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.seq)
            .all()
        )

    def get_by_clause_item(
        self, 
        db: Session, 
        *, 
        item_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ParagraphSpan]:
        """
        获取条款子项的所有段落
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.owner_type == "ClauseItem",
                    self.model.owner_id == item_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.seq)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_clause_item_all(
        self, 
        db: Session, 
        *, 
        item_id: str
    ) -> list[ParagraphSpan]:
        """
        获取条款子项的所有段落（不分页）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.owner_type == "ClauseItem",
                    self.model.owner_id == item_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.seq)
            .all()
        )
    
    def get_by_document(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        owner_type: [str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[ParagraphSpan]:
        """
        获取文档的所有段落
        """
        query = (
            db.query(self.model)
            .filter(
                and_(
                    self.model.deleted == False
                )
            )
        )
        
        # 通过关联查询获取文档ID
        if owner_type == "Clause":
            query = query.join(
                self.model.owner_clause
            ).filter(
                self.model.owner_clause.any(doc_id=doc_id)
            )
        elif owner_type == "ClauseItem":
            query = query.join(
                self.model.owner_clause
            ).join(
                self.model.owner_item
            ).filter(
                self.model.owner_clause.any(doc_id=doc_id)
            )
        else:
            # 获取文档的所有段落（Clause和ClauseItem）
            clause_query = db.query(self.model.id).join(
                self.model.owner_clause
            ).filter(
                self.model.owner_clause.any(doc_id=doc_id)
            )
            
            item_query = db.query(self.model.id).join(
                self.model.owner_item
            ).join(
                self.model.owner_clause
            ).filter(
                self.model.owner_clause.any(doc_id=doc_id)
            )
            
            query = query.filter(
                or_(
                    self.model.id.in_(clause_query),
                    self.model.id.in_(item_query)
                )
            )
        
        return query.order_by(self.model.seq).offset(skip).limit(limit).all()

    def get_by_region(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        region: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ParagraphSpan]:
        """
        获取文档中特定区域的段落
        """
        # 获取文档的所有段落
        spans = self.get_by_document(db, doc_id=doc_id, limit=10000)
        
        # 过滤特定区域
        filtered_spans = [
            span for span in spans 
            if span.region == region and not span.deleted
        ]
        
        # 排序和分页
        filtered_spans.sort(key=lambda x: x.seq)
        return filtered_spans[skip:skip+limit]

    def get_by_role(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        role: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ParagraphSpan]:
        """
        获取文档中特定角色的段落
        """
        # 获取文档的所有段落
        spans = self.get_by_document(db, doc_id=doc_id, limit=10000)
        
        # 过滤特定角色
        filtered_spans = [
            span for span in spans 
            if span.role == role and not span.deleted
        ]
        
        # 排序和分页
        filtered_spans.sort(key=lambda x: x.seq)
        return filtered_spans[skip:skip+limit]

    def get_by_nc_type(
        self, 
        db: Session, 
        *, 
        doc_id: str,
        nc_type: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ParagraphSpan]:
        """
        获取文档中特定nc_type的段落
        """
        # 获取文档的所有段落
        spans = self.get_by_document(db, doc_id=doc_id, limit=10000)
        
        # 过滤特定nc_type
        filtered_spans = [
            span for span in spans 
            if span.nc_type == nc_type and not span.deleted
        ]
        
        # 排序和分页
        filtered_spans.sort(key=lambda x: x.seq)
        return filtered_spans[skip:skip+limit]

    def create_multi(
        self, 
        db: Session, 
        *, 
        objs_in: list[ParagraphSpanCreate]
    ) -> list[ParagraphSpan]:
        """
        批量创建段落
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

    def update_labels(
        self, 
        db: Session, 
        *, 
        db_obj: ParagraphSpan,
        role: [str] = None,
        region: [str] = None,
        nc_type: [str] = None
    ) -> ParagraphSpan:
        """
        更新段落的标签信息
        """
        update_data = {}
        
        if role is not None:
            update_data["role"] = role
        
        if region is not None:
            update_data["region"] = region
        
        if nc_type is not None:
            update_data["nc_type"] = nc_type
        
        if update_data:
            return self.update(db, db_obj=db_obj, obj_in=update_data)
        
        return db_obj
    
    def get_next_seq(
        self, 
        db: Session, 
        *, 
        owner_type: str,
        owner_id: str
    ) -> int:
        """
        获取下一个序号
        """
        max_seq = (
            db.query(self.model)
            .filter(
                and_(
                    self.model.owner_type == owner_type,
                    self.model.owner_id == owner_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.seq.desc())
            .first()
        )
        
        return (max_seq.seq + 1) if max_seq else 1


crud_paragraph_span = CRUDParagraphSpan(ParagraphSpan)