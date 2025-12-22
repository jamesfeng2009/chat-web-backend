"""
向量摄入服务
支持批量向量化并写入指定Milvus集合，利用动态字段特性
"""
import asyncio
from pymilvus import connections, Collection, utility

from app.core.logger import get_logger
from app.core.config import settings
from app.schemas.vector_ingestion import VectorIngestRequest, VectorIngestResponse, VectorIngestData, FailedItem


logger = get_logger(__name__)


class VectorIngestionService:
    """向量摄入服务 - 支持动态字段"""
    
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service
        self._ensure_connection()
    
    def _ensure_connection(self):
        """确保Milvus连接已建立"""
        try:
            if not connections.has_connection("default"):
                connections.connect(
                    alias="default", 
                    host=settings.milvus_host, 
                    port=settings.milvus_port
                )
                logger.info(f"已连接到Milvus: {settings.milvus_host}:{settings.milvus_port}")
        except Exception as e:
            logger.error(f"连接Milvus失败: {str(e)}")
            raise
    
    async def ingest_items_to_collection(self, collection_name: str, request: VectorIngestRequest) -> VectorIngestResponse:
        """
        批量向量化并写入指定集合
        
        Args:
            collection_name: 集合名称
            request: 向量摄入请求
            
        Returns:
            摄入结果
        """
        try:
            # 检查集合是否存在
            if not utility.has_collection(collection_name):
                return VectorIngestResponse(
                    code=1,
                    message=f"集合 {collection_name} 不存在",
                    data={}
                )
            
            # 获取集合对象
            collection = Collection(collection_name)
            
            # 提取请求参数
            embedding_model = request.embedding_model
            items = request.items
            
            if not items:
                return VectorIngestResponse(
                    code=0,
                    message="没有数据需要处理",
                    data=VectorIngestData(
                        collection=collection_name,
                        total=0,
                        succeeded=0,
                        failed=0,
                        failed_items=[]
                    ).dict()
                )
            
            # 验证必要字段
            failed_items = []
            valid_items = []
            for i, item in enumerate(items):
                if not item.content:
                    failed_items.append(FailedItem(index=i, reason="缺少content字段").dict())
                else:
                    valid_items.append(item)
            
            total_items = len(items)
            valid_count = len(valid_items)
            
            if valid_count == 0:
                return VectorIngestResponse(
                    code=0,
                    message="没有有效数据",
                    data=VectorIngestData(
                        collection=collection_name,
                        total=total_items,
                        succeeded=0,
                        failed=total_items,
                        failed_items=failed_items
                    ).dict()
                )
            
            # 拆出文本，准备向量化
            contents = [item.content for item in valid_items]
            
            # 准备嵌入向量
            embeddings = []
            
            # 如果item中已经提供了向量，使用提供的；否则计算
            if all(item.embedding is not None for item in valid_items):
                # 使用预计算的向量
                embeddings = [item.embedding for item in valid_items]
                logger.info(f"使用预计算向量，共 {len(embeddings)} 个")
            else:
                # 调用embedding模型计算向量
                logger.info(f"使用模型 {embedding_model} 计算向量，共 {len(contents)} 个")
                embeddings = await self._embed_texts(embedding_model, contents)
            
            # 组装Milvus插入数据
            columns = self._prepare_columns(valid_items, embeddings)
            
            # 插入Milvus
            try:
                # 获取集合的所有字段名，不包括自动生成的id
                field_names = [field.name for field in collection.schema.fields if field.name != "id"]
                insert_data = [columns.get(field_name, []) for field_name in field_names]
                
                # 执行插入
                insert_result = collection.insert(insert_data)
                
                # 刷新数据到存储（可选）
                # collection.flush()
                
                logger.info(f"成功插入 {len(valid_items)} 条数据到集合 {collection_name}")
                
                # 返回成功结果
                return VectorIngestResponse(
                    code=0,
                    message="ok" if len(failed_items) == 0 else "partial_failed",
                    data=VectorIngestData(
                        collection=collection_name,
                        total=total_items,
                        succeeded=valid_count,
                        failed=len(failed_items),
                        failed_items=failed_items
                    ).dict()
                )
            except Exception as e:
                logger.error(f"插入Milvus失败: {str(e)}")
                
                # 所有有效项都失败
                for i, item in enumerate(valid_items):
                    failed_items.append(FailedItem(index=i, reason=f"插入失败: {str(e)}").dict())
                
                return VectorIngestResponse(
                    code=1,
                    message="插入失败",
                    data=VectorIngestData(
                        collection=collection_name,
                        total=total_items,
                        succeeded=0,
                        failed=total_items,
                        failed_items=failed_items
                    ).dict()
                )
                
        except Exception as e:
            logger.error(f"向量摄入失败: {str(e)}")
            return VectorIngestResponse(
                code=1,
                message=f"向量摄入失败: {str(e)}",
                data={}
            )
    
    async def _embed_texts(self, model_name: str, texts: list[str]) -> list[list[float]]:
        """
        调用embedding服务
        
        Args:
            model_name: 模型名称，如 text-embedding-3-large
            texts: 文本列表
            
        Returns:
            对应的向量列表
        """
        if self.embedding_service:
            # 使用注入的embedding服务
            return await self.embedding_service.generate_batch(model_name, texts)
        else:
            # 默认实现（可以替换为实际的embedding API调用）
            # 这里返回随机向量作为示例，实际使用时应替换为真实调用
            logger.warning("使用默认embedding实现（随机向量），请注入真实embedding服务")
            import random
            dim = 1536  # 默认维度，应与集合匹配
            return [[random.random() for _ in range(dim)] for _ in texts]
    
    def _prepare_columns(self, items: list[any], embeddings: list[list[float]]) -> dict[str, List]:
        """
        准备列式数据
        
        Args:
            items: 有效项目列表
            embeddings: 对应的向量列表
            
        Returns:
            列式数据字典
        """
        columns = {
            "embedding": [],
            "unit_type": [],
            "doc_id": [],
            "doc_name": [],
            "section_id": [],
            "section_title": [],
            "section_level": [],
            "clause_id": [],
            "clause_title": [],
            "clause_order_index": [],
            "item_id": [],
            "parent_item_id": [],
            "item_order_index": [],
            "content": [],
            "lang": [],
            "role": [],
            "region": [],
            "nc_type": [],
            "score": [],
            "loc": [],
            "biz_tags": []
        }
        
        for item, vec in zip(items, embeddings):
            # 向量字段
            columns["embedding"].append(vec)
            
            # 类型字段
            columns["unit_type"].append(item.unit_type)
            
            # 文档级字段
            columns["doc_id"].append(item.doc_id)
            columns["doc_name"].append(item.doc_name)
            
            # 章节级字段
            columns["section_id"].append(item.section_id)
            columns["section_title"].append(item.section_title)
            columns["section_level"].append(item.section_level or 0)
            
            # 条款级字段
            columns["clause_id"].append(item.clause_id)
            columns["clause_title"].append(item.clause_title)
            columns["clause_order_index"].append(item.clause_order_index or 0)
            
            # 子项级字段
            columns["item_id"].append(item.item_id)
            columns["parent_item_id"].append(item.parent_item_id)
            columns["item_order_index"].append(item.item_order_index or 0)
            
            # 业务属性
            columns["lang"].append(item.lang)
            columns["role"].append(item.role)
            columns["region"].append(item.region)
            columns["nc_type"].append(item.nc_type)
            columns["score"].append(item.score)
            
            # 文本与定位
            columns["content"].append(item.content)
            columns["loc"].append(item.loc or {})
            columns["biz_tags"].append(item.biz_tags or {})
        
        return columns
    
    def _prepare_clause_item_vector_item(self, doc_id: str, item: dict[str, any], clauses: list[dict[str, any]], section_map: dict[str, any]) -> [dict[str, any]]:
        """准备条款子项向量项"""
        if not item or not item.get("content"):
            return None
        
        # 提取必要信息
        item_id = item.get("id")
        clause_id = item.get("clause_id")
        title = item.get("title", "")
        content = item.get("content", "")
        number_token = item.get("number_token", "")
        
        # 获取clause和section信息
        clause_title = ""
        section_id = None
        section_title = ""
        section_level = 0
        
        if clause_id:
            # 查找clause
            for clause in clauses:
                if clause.get("id") == clause_id:
                    clause_title = clause.get("title", "")
                    section_id = clause.get("section_id")
                    break
            
            # 根据section_id获取section信息
            if section_id and section_id in section_map:
                section = section_map[section_id]
                section_title = section.get("title", "")
                section_level = section.get("level", 0)
        
        # 构建用于向量化的文本
        vector_text = self._build_vector_text(title, number_token, content)
        
        return {
            "id": item_id,
            "unit_type": "CLAUSE_ITEM",
            "doc_id": doc_id,
            "doc_name": "",  # 需要从document获取，这里先留空
            "section_id": section_id,
            "section_title": section_title,
            "section_level": section_level,
            "clause_id": clause_id,
            "clause_title": clause_title,
            "clause_order_index": 0,  # 子项没有独立的order_index
            "item_id": item_id,
            "parent_item_id": item.get("parent_item_id"),
            "item_order_index": item.get("order_index", 0),
            "lang": item.get("lang", "zh"),
            "role": item.get("role", "CLAUSE"),
            "region": item.get("region", "MAIN"),
            "nc_type": item.get("nc_type"),
            "content": content,
            "vector_text": vector_text,  # 用于向量化的文本
            "loc": item.get("loc", {}),
            "score": item.get("score", 1)
        }
    
    def _build_vector_text(self, title: str, number_token: str, content: str) -> str:
        """构建用于向量化的文本"""
        parts = []
        
        if number_token:
            parts.append(number_token)
        
        if title:
            parts.append(title)
        
        if content:
            parts.append(content)
        
        return " ".join(parts)
    
    async def _generate_embeddings(self, vector_items: list[dict[str, any]]) -> list[list[float]]:
        """生成向量"""
        try:
            # 提取文本
            texts = [item.get("vector_text", "") for item in vector_items]
            
            # 调用embedding服务
            embeddings = await self.embedding_service.generate_batch(texts)
            
            return embeddings
        except Exception as e:
            logger.error(f"生成向量失败: {str(e)}")
            raise
    
    async def _insert_vectors(self, collection_name: str, vector_items: list[dict[str, any]], embeddings: list[list[float]]) -> dict[str, any]:
        """插入向量到Milvus"""
        try:
            # 准备数据
            insert_data = {
                "embedding": embeddings,
                "unit_type": [item.get("unit_type") for item in vector_items],
                "doc_id": [item.get("doc_id") for item in vector_items],
                "doc_name": [item.get("doc_name") for item in vector_items],
                "section_id": [item.get("section_id") for item in vector_items],
                "section_title": [item.get("section_title") for item in vector_items],
                "section_level": [item.get("section_level") for item in vector_items],
                "clause_id": [item.get("clause_id") for item in vector_items],
                "clause_title": [item.get("clause_title") for item in vector_items],
                "clause_order_index": [item.get("clause_order_index") for item in vector_items],
                "item_id": [item.get("item_id") for item in vector_items],
                "parent_item_id": [item.get("parent_item_id") for item in vector_items],
                "item_order_index": [item.get("item_order_index") for item in vector_items],
                "lang": [item.get("lang") for item in vector_items],
                "role": [item.get("role") for item in vector_items],
                "region": [item.get("region") for item in vector_items],
                "nc_type": [item.get("nc_type") for item in vector_items],
                "content": [item.get("content") for item in vector_items],
                "loc": [item.get("loc") for item in vector_items]
            }
            
            # 插入Milvus
            result = await self.milvus_client.insert(collection_name, insert_data)
            
            return {
                "success": True,
                "message": f"成功插入 {len(vector_items)} 个向量",
                "total": len(vector_items),
                "succeeded": len(vector_items),
                "failed": 0,
                "failed_items": [],
                "insert_ids": result.get("ids", [])
            }
        except Exception as e:
            logger.error(f"插入向量失败: {str(e)}")
            return {
                "success": False,
                "message": f"插入向量失败: {str(e)}",
                "total": len(vector_items),
                "succeeded": 0,
                "failed": len(vector_items),
                "failed_items": [{"index": i, "reason": str(e)} for i in range(len(vector_items))]
            }
    
    async def search_vectors(self, search_request: VectorSearchRequest) -> dict[str, any]:
        """
        向量搜索
        
        Args:
            search_request: 搜索请求
            
        Returns:
            搜索结果
        """
        try:
            # 生成查询向量
            query_embedding = await self.embedding_service.generate(search_request.query)
            
            # 准备搜索参数
            search_params = {
                "collection_name": search_request.collection_name,
                "query_vectors": [query_embedding],
                "top_k": search_request.limit,
                "expr": search_request.filter_expr,
                "output_fields": search_request.output_fields,
                "params": search_request.search_params
            }
            
            # 执行搜索
            result = await self.milvus_client.search(**search_params)
            
            # 格式化结果
            return self._format_search_result(result, search_request)
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return {
                "success": False,
                "message": f"向量搜索失败: {str(e)}",
                "results": []
            }
    
    def _format_search_result(self, milvus_result: Dict, search_request: VectorSearchRequest) -> dict[str, any]:
        """格式化搜索结果"""
        try:
            results = []
            
            if not milvus_result or "results" not in milvus_result:
                return {
                    "success": True,
                    "query": search_request.query,
                    "total": 0,
                    "results": []
                }
            
            # 处理每个搜索结果
            for hits in milvus_result["results"]:
                for hit in hits:
                    # 提取字段
                    fields = hit.get("entity", {})
                    result_item = {
                        "id": fields.get("id", ""),
                        "unit_type": fields.get("unit_type", ""),
                        "doc_id": fields.get("doc_id", ""),
                        "doc_name": fields.get("doc_name", ""),
                        "section_id": fields.get("section_id"),
                        "section_title": fields.get("section_title", ""),
                        "section_level": fields.get("section_level", 0),
                        "clause_id": fields.get("clause_id", ""),
                        "clause_title": fields.get("clause_title", ""),
                        "clause_order_index": fields.get("clause_order_index", 0),
                        "item_id": fields.get("item_id"),
                        "parent_item_id": fields.get("parent_item_id"),
                        "item_order_index": fields.get("item_order_index", 0),
                        "lang": fields.get("lang", "zh"),
                        "role": fields.get("role", ""),
                        "region": fields.get("region", ""),
                        "nc_type": fields.get("nc_type"),
                        "content": fields.get("content", ""),
                        "loc": fields.get("loc", {}),
                        "score": fields.get("score", 1),
                        "distance": hit.get("distance", 0.0)
                    }
                    results.append(result_item)
            
            return {
                "success": True,
                "query": search_request.query,
                "total": len(results),
                "results": results
            }
        except Exception as e:
            logger.error(f"格式化搜索结果失败: {str(e)}")
            return {
                "success": False,
                "message": f"格式化搜索结果失败: {str(e)}",
                "query": search_request.query,
                "total": 0,
                "results": []
            }
    
    async def batch_vectorize(self, vectors_data: list[dict[str, any]], collection_name: [str] = None) -> dict[str, any]:
        """
        批量向量化数据
        
        Args:
            vectors_data: 向量数据列表，每项包含 type, id, doc_id, content, metadata
            collection_name: 集合名称，如果不指定则使用默认集合
            
        Returns:
            批量向量化结果
        """
        try:
            target_collection = collection_name or self.default_collection_name
            
            # 准备向量项
            vector_items = []
            for data in vectors_data:
                vector_item = self._prepare_vector_item_from_data(data)
                if vector_item:
                    vector_items.append(vector_item)
            
            if not vector_items:
                return {
                    "success": True,
                    "message": "没有需要向量化的数据",
                    "total": 0,
                    "success_count": 0,
                    "results": []
                }
            
            # 生成嵌入向量
            texts = [item.get("vector_text", "") for item in vector_items]
            embeddings = await self.embedding_service.generate_batch(texts)
            
            # 插入向量
            result = await self._insert_vectors(target_collection, vector_items, embeddings)
            
            # 格式化结果
            results = []
            if result.get("success"):
                for i, item in enumerate(vector_items):
                    results.append({
                        "id": item.get("id"),
                        "type": item.get("unit_type"),
                        "success": True,
                        "embedding_id": str(i)
                    })
            else:
                for item in vector_items:
                    results.append({
                        "id": item.get("id"),
                        "type": item.get("unit_type"),
                        "success": False,
                        "error": result.get("message", "未知错误")
                    })
            
            return {
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "total": len(vectors_data),
                "success_count": len([r for r in results if r.get("success")]),
                "results": results
            }
        except Exception as e:
            logger.error(f"批量向量化失败: {str(e)}")
            return {
                "success": False,
                "message": f"批量向量化失败: {str(e)}",
                "total": len(vectors_data),
                "success_count": 0,
                "results": [{"id": data.get("id"), "type": data.get("type"), "success": False, "error": str(e)} for data in vectors_data]
            }
    
    def _prepare_vector_item_from_data(self, data: dict[str, any]) -> [dict[str, any]]:
        """从数据准备向量项"""
        if not data or not data.get("content"):
            return None
        
        # 提取元数据
        metadata = data.get("metadata", {})
        element_type = data.get("type", "unknown")
        element_id = data.get("id")
        doc_id = data.get("doc_id")
        content = data.get("content", "")
        
        # 根据类型确定字段
        if element_type == "clause":
            return {
                "id": element_id,
                "unit_type": "CLAUSE",
                "doc_id": doc_id,
                "doc_name": "",
                "section_id": metadata.get("section_id"),
                "section_title": metadata.get("section_title", ""),
                "section_level": metadata.get("section_level", 0),
                "clause_id": element_id,
                "clause_title": metadata.get("title", ""),
                "clause_order_index": metadata.get("order_index", 0),
                "item_id": None,
                "parent_item_id": None,
                "item_order_index": None,
                "lang": metadata.get("lang", "zh"),
                "role": metadata.get("role", "CLAUSE"),
                "region": metadata.get("region", "MAIN"),
                "nc_type": metadata.get("nc_type", "CLAUSE_BODY"),
                "content": content,
                "vector_text": content,
                "loc": metadata.get("loc", {})
            }
        elif element_type == "clause_item":
            return {
                "id": element_id,
                "unit_type": "CLAUSE_ITEM",
                "doc_id": doc_id,
                "doc_name": "",
                "section_id": metadata.get("section_id"),
                "section_title": metadata.get("section_title", ""),
                "section_level": metadata.get("section_level", 0),
                "clause_id": metadata.get("clause_id"),
                "clause_title": metadata.get("clause_title", ""),
                "clause_order_index": 0,
                "item_id": element_id,
                "parent_item_id": metadata.get("parent_item_id"),
                "item_order_index": metadata.get("order_index", 0),
                "lang": metadata.get("lang", "zh"),
                "role": metadata.get("role", "CLAUSE"),
                "region": metadata.get("region", "MAIN"),
                "nc_type": metadata.get("nc_type", "CLAUSE_BODY"),
                "content": content,
                "vector_text": content,
                "loc": metadata.get("loc", {})
            }
        
        return None

    async def delete_document_vectors(self, doc_id: str) -> dict[str, any]:
        """
        删除文档的所有向量
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除结果
        """
        try:
            # 构建过滤表达式
            filter_expr = f"doc_id == '{doc_id}'"
            
            # 删除向量
            result = await self.milvus_client.delete(
                collection_name=self.default_collection_name,
                expr=filter_expr
            )
            
            return {
                "success": True,
                "message": f"成功删除文档 {doc_id} 的所有向量",
                "deleted_count": result.get("deleted_count", 0)
            }
        except Exception as e:
            logger.error(f"删除文档向量失败: {str(e)}")
            return {
                "success": False,
                "message": f"删除文档向量失败: {str(e)}",
                "deleted_count": 0
            }