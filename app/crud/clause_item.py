
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.crud.base import CRUDBase
from app.models.clause_item import ClauseItem
from app.schemas.clause_item import ClauseItemCreate, ClauseItemUpdate


class CRUDClauseItem(CRUDBase[ClauseItem, ClauseItemCreate, ClauseItemUpdate]):
    def get_by_clause(
        self, 
        db: Session, 
        *, 
        clause_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ClauseItem]:
        """
        获取条款的所有子项
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.clause_id == clause_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_clause_all(
        self, 
        db: Session, 
        *, 
        clause_id: str
    ) -> list[ClauseItem]:
        """
        获取条款的所有子项（不分页）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.clause_id == clause_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .all()
        )

    def get_by_parent(
        self, 
        db: Session, 
        *, 
        parent_item_id: str
    ) -> list[ClauseItem]:
        """
        获取父项下的所有子项
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.parent_item_id == parent_item_id,
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .all()
        )

    def get_root_items(
        self, 
        db: Session, 
        *, 
        clause_id: str
    ) -> list[ClauseItem]:
        """
        获取条款的根级子项（无父项的子项）
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.clause_id == clause_id,
                    self.model.parent_item_id.is_(None),
                    self.model.deleted == False
                )
            )
            .order_by(self.model.order_index)
            .all()
        )

    def get_without_embedding(
        self, 
        db: Session, 
        *, 
        skip: int = 0,
        limit: int = 100
    ) -> list[ClauseItem]:
        """
        获取尚未向量化的子项
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

    def get_without_embedding_by_clause(
        self, 
        db: Session, 
        *, 
        clause_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> list[ClauseItem]:
        """
        获取特定条款中尚未向量化的子项
        """
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.clause_id == clause_id,
                    self.model.embedding_id.is_(None),
                    self.model.deleted == False
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_embedding(
        self, 
        db: Session, 
        *, 
        db_obj: ClauseItem,
        embedding_id: str
    ) -> ClauseItem:
        """
        更新子项的向量信息
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
    ) -> [ClauseItem]:
        """
        通过ID更新子项的向量ID
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
        clause_id: str,
        parent_item_id: [str] = None
    ) -> int:
        """
        获取下一个顺序号
        """
        query = (
            db.query(self.model)
            .filter(
                and_(
                    self.model.clause_id == clause_id,
                    self.model.deleted == False
                )
            )
        )
        
        if parent_item_id:
            query = query.filter(self.model.parent_item_id == parent_item_id)
        else:
            query = query.filter(self.model.parent_item_id.is_(None))
            
        max_order = query.order_by(self.model.order_index.desc()).first()
        
        return (max_order.order_index + 1) if max_order else 1

    def create_multiple(
        self, 
        db: Session, 
        *, 
        objs_in: list[ClauseItemCreate]
    ) -> list[ClauseItem]:
        """
        批量创建子项
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

    def get_tree(
        self, 
        db: Session, 
        *, 
        clause_id: str
    ) -> list[dict]:
        """
        获取子项的树形结构
        """
        # 获取所有子项
        all_items = self.get_by_clause_all(db, clause_id=clause_id)
        
        # 构建字典映射
        items_dict = {item.id: item.dict() for item in all_items}
        
        # 构建树形结构
        root_items = []
        for item_id, item in items_dict.items():
            parent_id = item.get("parent_item_id")
            if parent_id and parent_id in items_dict:
                parent = items_dict[parent_id]
                if "children" not in parent:
                    parent["children"] = []
                parent["children"].append(item)
            else:
                root_items.append(item)
                
        return root_items


crud_clause_item = CRUDClauseItem(ClauseItem)