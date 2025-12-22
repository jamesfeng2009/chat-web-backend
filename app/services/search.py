import re
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.crud.clause import crud_clause
from app.crud.clause_item import crud_clause_item
from app.crud.document import crud_document
from app.services.embedding import embedding_service
from app.services.vector import vector_service
from app.core.logger import get_logger

logger = get_logger(__name__)


class SearchService:
    """搜索服务"""
    
    def __init__(self):
        self.embedding_service = embedding_service
        self.vector_service = vector_service
    
    def semantic_search(
        self,
        collection: str,
        query: str,
        embedding_model: str = "text-embedding-3-large",
        limit: int = 10,
        filters: [dict[str, any]] = None,
        include_content: bool = True
    ) -> dict[str, any]:
        """
        语义搜索
        
        Args:
            collection: 向量集合名称
            query: 查询文本
            embedding_model: 向量模型
            limit: 返回结果数
            filters: 过滤条件
            include_content: 是否包含内容
            
        Returns:
            搜索结果
        """
        try:
            # 生成查询向量
            query_vector = self.embedding_service.embed_text(query, embedding_model)
            
            # 构建过滤表达式
            expr = self._build_filter_expression(filters)
            
            # 执行向量搜索
            search_results = self.vector_service.search_vectors(
                collection_name=collection,
                query_vectors=[query_vector],
                limit=limit,
                expr=expr,
                output_fields=None if include_content else ["id", "unit_type", "doc_id", "clause_id", "item_id"]
            )
            
            # 格式化结果
            items = []
            for hits in search_results:
                for hit in hits:
                    item = self._format_search_result(hit, include_content)
                    items.append(item)
            
            # 聚合子项到条款
            aggregated_items = self._aggregate_items_to_clauses(items)
            
            return {
                "query": query,
                "total": len(aggregated_items),
                "items": aggregated_items
            }
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            raise
    
    def similarity_search(
        self,
        collection: str,
        query: str,
        embedding_model: str = "text-embedding-3-large",
        limit: int = 10,
        filters: [dict[str, any]] = None,
        include_content: bool = True
    ) -> dict[str, any]:
        """
        相似度搜索（与语义搜索相同，为了API区分）
        
        Args:
            collection: 向量集合名称
            query: 查询文本
            embedding_model: 向量模型
            limit: 返回结果数
            filters: 过滤条件
            include_content: 是否包含内容
            
        Returns:
            搜索结果
        """
        # 与语义搜索相同
        return self.semantic_search(
            collection=collection,
            query=query,
            embedding_model=embedding_model,
            limit=limit,
            filters=filters,
            include_content=include_content
        )
    
    def keyword_search(
        self,
        db: Session,
        query: str,
        limit: int = 10,
        filters: [dict[str, any]] = None,
        include_content: bool = True
    ) -> dict[str, any]:
        """
        关键词搜索
        
        Args:
            db: 数据库会话
            query: 查询文本
            limit: 返回结果数
            filters: 过滤条件
            include_content: 是否包含内容
            
        Returns:
            搜索结果
        """
        try:
            # 搜索条款
            clause_results = self._keyword_search_clauses(db, query, limit, filters)
            
            # 搜索子项
            item_results = self._keyword_search_items(db, query, limit, filters)
            
            # 合并结果
            all_results = clause_results + item_results
            
            # 格式化结果
            items = []
            for result in all_results:
                item = self._format_db_search_result(result, include_content)
                items.append(item)
            
            # 按相关性排序（这里简化为按标题匹配度排序）
            items.sort(key=lambda x: x.get("relevance", 0), reverse=True)
            
            # 聚合子项到条款
            aggregated_items = self._aggregate_items_to_clauses(items)
            
            return {
                "query": query,
                "total": len(aggregated_items),
                "items": aggregated_items[:limit]
            }
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            raise
    
    def hybrid_search(
        self,
        db: Session,
        collection: str,
        query: str,
        embedding_model: str = "text-embedding-3-large",
        limit: int = 10,
        filters: [dict[str, any]] = None,
        include_content: bool = True,
        semantic_weight: float = 0.7
    ) -> dict[str, any]:
        """
        混合搜索（语义+关键词）
        
        Args:
            db: 数据库会话
            collection: 向量集合名称
            query: 查询文本
            embedding_model: 向量模型
            limit: 返回结果数
            filters: 过滤条件
            include_content: 是否包含内容
            semantic_weight: 语义搜索权重
            
        Returns:
            搜索结果
        """
        try:
            # 执行语义搜索
            semantic_results = self.semantic_search(
                collection=collection,
                query=query,
                embedding_model=embedding_model,
                limit=limit * 2,  # 获取更多结果用于混合
                filters=filters,
                include_content=include_content
            )
            
            # 执行关键词搜索
            keyword_results = self.keyword_search(
                db=db,
                query=query,
                limit=limit * 2,  # 获取更多结果用于混合
                filters=filters,
                include_content=include_content
            )
            
            # 合并和重排序结果
            hybrid_results = self._merge_search_results(
                semantic_results, keyword_results, semantic_weight
            )
            
            return {
                "query": query,
                "total": len(hybrid_results["items"]),
                "items": hybrid_results["items"][:limit],
                "semantic_count": len(semantic_results["items"]),
                "keyword_count": len(keyword_results["items"])
            }
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            raise
    
    def _build_filter_expression(self, filters: [dict[str, any]]) -> [str]:
        """构建过滤表达式"""
        if not filters:
            return None
        
        conditions = []
        
        for key, value in filters.items():
            if key == "doc_id" and isinstance(value, str):
                conditions.append(f'doc_id == "{value}"')
            elif key == "doc_id" and isinstance(value, list):
                doc_ids = '", "'.join(value)
                conditions.append(f'doc_id in ["{doc_ids}"]')
            elif key == "unit_type" and isinstance(value, str):
                conditions.append(f'unit_type == "{value}"')
            elif key == "unit_type" and isinstance(value, list):
                unit_types = '", "'.join(value)
                conditions.append(f'unit_type in ["{unit_types}"]')
            elif key == "region" and isinstance(value, str):
                conditions.append(f'region == "{value}"')
            elif key == "region" and isinstance(value, list):
                regions = '", "'.join(value)
                conditions.append(f'region in ["{regions}"]')
        
        return " and ".join(conditions) if conditions else None
    
    def _format_search_result(self, hit: dict[str, any], include_content: bool) -> dict[str, any]:
        """格式化搜索结果"""
        entity = hit.get("entity", {})
        
        result = {
            "id": hit.get("id"),
            "score": hit.get("score"),
            "unit_type": entity.get("unit_type"),
            "doc_id": entity.get("doc_id"),
            "doc_name": entity.get("doc_name"),
            "clause_id": entity.get("clause_id"),
            "item_id": entity.get("item_id"),
            "title": None,
            "content": None,
            "metadata": {}
        }
        
        # 添加标题和内容
        if include_content:
            result["content"] = entity.get("content")
            
            # 根据类型设置标题
            if result["unit_type"] == "CLAUSE":
                result["title"] = entity.get("clause_title")
            else:
                result["title"] = entity.get("title")
        
        # 添加元数据
        for key in ["lang", "region", "nc_type", "loc"]:
            if key in entity:
                result["metadata"][key] = entity[key]
        
        return result
    
    def _format_db_search_result(self, result: dict[str, any], include_content: bool) -> dict[str, any]:
        """格式化数据库搜索结果"""
        item_type = result.get("type", "CLAUSE")
        
        item = {
            "id": result.get("id"),
            "score": result.get("relevance", 1.0),
            "unit_type": item_type,
            "doc_id": result.get("doc_id"),
            "doc_name": result.get("doc_name"),
            "clause_id": result.get("id") if item_type == "CLAUSE" else result.get("clause_id"),
            "item_id": result.get("id") if item_type == "CLAUSE_ITEM" else None,
            "title": result.get("title"),
            "content": None,
            "metadata": {}
        }
        
        # 添加内容
        if include_content:
            item["content"] = result.get("content")
        
        # 添加元数据
        for key in ["lang", "region", "nc_type", "loc"]:
            if key in result:
                item["metadata"][key] = result[key]
        
        return item
    
    def _aggregate_items_to_clauses(self, items: list[dict[str, any]]) -> list[dict[str, any]]:
        """聚合子项到条款"""
        clause_items = {}
        standalone_items = []
        
        # 分离条款和子项
        for item in items:
            if item.get("unit_type") == "CLAUSE":
                clause_id = item.get("clause_id")
                if clause_id not in clause_items or item.get("score", 0) > clause_items[clause_id].get("score", 0):
                    # 使用得分更高的结果
                    item["sub_items"] = []
                    clause_items[clause_id] = item
            elif item.get("unit_type") == "CLAUSE_ITEM":
                clause_id = item.get("clause_id")
                if clause_id in clause_items:
                    # 添加为子项
                    clause_items[clause_id]["sub_items"].append(item)
                else:
                    # 作为独立项
                    standalone_items.append(item)
        
        # 构建结果列表
        result = list(clause_items.values()) + standalone_items
        
        # 按得分排序
        result.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return result
    
    def _keyword_search_clauses(
        self,
        db: Session,
        query: str,
        limit: int,
        filters: [dict[str, any]]
    ) -> list[dict[str, any]]:
        """关键词搜索条款"""
        try:
            # 构建查询
            db_query = db.query(crud_clause.model).filter(crud_clause.model.deleted == False)
            
            # 添加文本搜索条件
            text_condition = or_(
                crud_clause.model.title.contains(query),
                crud_clause.model.content.contains(query)
            )
            db_query = db_query.filter(text_condition)
            
            # 添加过滤条件
            if filters:
                if "doc_id" in filters:
                    db_query = db_query.filter(crud_clause.model.doc_id == filters["doc_id"])
                if "region" in filters:
                    db_query = db_query.filter(crud_clause.model.region == filters["region"])
            
            # 执行查询
            clauses = db_query.limit(limit).all()
            
            # 格式化结果
            results = []
            for clause in clauses:
                # 计算相关性得分
                title_match = 1.0 if query.lower() in clause.title.lower() else 0.0
                content_match = 1.0 if query.lower() in clause.content.lower() else 0.0
                relevance = max(title_match, content_match)
                
                # 获取文档名称
                doc_name = ""
                if clause.doc_id:
                    doc = crud_document.get(db, id=clause.doc_id)
                    doc_name = doc.name if doc else ""
                
                result = {
                    "id": clause.id,
                    "type": "CLAUSE",
                    "doc_id": clause.doc_id,
                    "doc_name": doc_name,
                    "title": clause.title,
                    "content": clause.content,
                    "lang": clause.lang,
                    "region": clause.region,
                    "nc_type": clause.nc_type,
                    "relevance": relevance,
                    "loc": clause.loc
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in keyword search for clauses: {e}")
            return []
    
    def _keyword_search_items(
        self,
        db: Session,
        query: str,
        limit: int,
        filters: [dict[str, any]]
    ) -> list[dict[str, any]]:
        """关键词搜索子项"""
        try:
            # 构建查询
            db_query = db.query(crud_clause_item.model).filter(crud_clause_item.model.deleted == False)
            
            # 添加文本搜索条件
            text_condition = or_(
                crud_clause_item.model.title.contains(query),
                crud_clause_item.model.content.contains(query)
            )
            db_query = db_query.filter(text_condition)
            
            # 添加过滤条件
            if filters:
                if "doc_id" in filters:
                    # 关联查询文档ID
                    db_query = db_query.join(crud_clause.model).filter(crud_clause.model.doc_id == filters["doc_id"])
            
            # 执行查询
            items = db_query.limit(limit).all()
            
            # 格式化结果
            results = []
            for item in items:
                # 计算相关性得分
                title_match = 1.0 if query.lower() in (item.title or "").lower() else 0.0
                content_match = 1.0 if query.lower() in (item.content or "").lower() else 0.0
                relevance = max(title_match, content_match)
                
                # 获取文档和条款信息
                doc_name = ""
                clause_title = ""
                doc_id = ""
                clause_id = item.clause_id
                
                if clause_id:
                    clause = crud_clause.get(db, id=clause_id)
                    if clause:
                        doc_id = clause.doc_id
                        clause_title = clause.title
                        doc = crud_document.get(db, id=doc_id)
                        doc_name = doc.name if doc else ""
                
                result = {
                    "id": item.id,
                    "type": "CLAUSE_ITEM",
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "clause_id": clause_id,
                    "title": item.title,
                    "content": item.content,
                    "lang": item.lang,
                    "region": item.region,
                    "nc_type": item.nc_type,
                    "relevance": relevance,
                    "loc": item.loc,
                    "clause_title": clause_title
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in keyword search for items: {e}")
            return []
    
    def _merge_search_results(
        self,
        semantic_results: dict[str, any],
        keyword_results: dict[str, any],
        semantic_weight: float
    ) -> dict[str, any]:
        """合并搜索结果"""
        # 提取结果项
        semantic_items = semantic_results.get("items", [])
        keyword_items = keyword_results.get("items", [])
        
        # 合并结果，去重
        merged_items = {}
        
        # 处理语义搜索结果
        for item in semantic_items:
            key = f"{item.get('unit_type')}_{item.get('clause_id')}_{item.get('item_id')}"
            item["source"] = "semantic"
            item["semantic_score"] = item.get("score", 0)
            item["keyword_score"] = 0
            merged_items[key] = item
        
        # 处理关键词搜索结果
        for item in keyword_items:
            key = f"{item.get('unit_type')}_{item.get('clause_id')}_{item.get('item_id')}"
            item["source"] = "keyword"
            item["semantic_score"] = 0
            item["keyword_score"] = item.get("relevance", 0)
            
            if key in merged_items:
                # 合并已存在项
                existing_item = merged_items[key]
                existing_item["source"] = "both"
                existing_item["keyword_score"] = item.get("relevance", 0)
            else:
                merged_items[key] = item
        
        # 计算综合得分
        keyword_weight = 1.0 - semantic_weight
        for item in merged_items.values():
            semantic_score = item.get("semantic_score", 0)
            keyword_score = item.get("keyword_score", 0)
            item["score"] = semantic_score * semantic_weight + keyword_score * keyword_weight
            item["source"] = item.get("source", "unknown")
        
        # 排序
        sorted_items = sorted(
            merged_items.values(),
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        
        return {
            "items": sorted_items
        }


# 全局搜索服务实例
search_service = SearchService()