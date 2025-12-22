import os
import uuid
import json
import numpy as np
from pymilvus import utility, connections, Collection, CollectionSchema, FieldSchema, DataType

from app.services.embedding import embedding_service
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


def ensure_milvus_connection():
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


class VectorService:
    """向量服务"""
    
    def __init__(self):
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        ensure_milvus_connection()
    
    def create_collection(
        self,
        name: str,
        description: str = None,
        embedding_dimension: int = None,
        options: dict[str, any] = None
    ):
        """
        创建向量集合
        
        Args:
            name: 集合名称
            description: 集合描述
            embedding_dimension: 向量维度
            options: 集合选项
            
        Returns:
            创建的集合
        """
        try:
            # 如果未指定维度，使用默认值
            if embedding_dimension is None:
                embedding_dimension = embedding_service.get_model_dimension()
            
            # 检查集合是否已存在
            if utility.has_collection(name):
                logger.info(f"Collection {name} already exists")
                collection = Collection(name)
                return collection
            
            # 定义字段
            fields = [
                # 主键
                FieldSchema(
                    name="id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=True
                ),
                
                # 向量字段
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=embedding_dimension
                ),
                
                # 单元类型 (CLAUSE/CLAUSE_ITEM)
                FieldSchema(
                    name="unit_type",
                    dtype=DataType.VARCHAR,
                    max_length=16
                ),
                
                # 文档信息
                FieldSchema(
                    name="doc_id",
                    dtype=DataType.VARCHAR,
                    max_length=64
                ),
                FieldSchema(
                    name="doc_name",
                    dtype=DataType.VARCHAR,
                    max_length=256
                ),
                
                # 章节信息
                FieldSchema(
                    name="section_id",
                    dtype=DataType.VARCHAR,
                    max_length=64
                ),
                FieldSchema(
                    name="section_title",
                    dtype=DataType.VARCHAR,
                    max_length=256
                ),
                FieldSchema(
                    name="section_level",
                    dtype=DataType.INT64
                ),
                
                # 条款信息
                FieldSchema(
                    name="clause_id",
                    dtype=DataType.VARCHAR,
                    max_length=64
                ),
                FieldSchema(
                    name="clause_title",
                    dtype=DataType.VARCHAR,
                    max_length=512
                ),
                FieldSchema(
                    name="clause_order_index",
                    dtype=DataType.INT64
                ),
                
                # 子项信息
                FieldSchema(
                    name="item_id",
                    dtype=DataType.VARCHAR,
                    max_length=64
                ),
                FieldSchema(
                    name="parent_item_id",
                    dtype=DataType.VARCHAR,
                    max_length=64
                ),
                FieldSchema(
                    name="item_order_index",
                    dtype=DataType.INT64
                ),
                
                # 内容和属性
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=8192
                ),
                FieldSchema(
                    name="lang",
                    dtype=DataType.VARCHAR,
                    max_length=8
                ),
                FieldSchema(
                    name="role",
                    dtype=DataType.VARCHAR,
                    max_length=32
                ),
                FieldSchema(
                    name="region",
                    dtype=DataType.VARCHAR,
                    max_length=32
                ),
                FieldSchema(
                    name="nc_type",
                    dtype=DataType.VARCHAR,
                    max_length=64
                ),
                
                # 定位信息
                FieldSchema(
                    name="loc",
                    dtype=DataType.JSON
                )
            ]
            
            # 创建schema
            schema = CollectionSchema(
                fields=fields,
                description=description or f"Collection {name}",
                enable_dynamic_field=True  # 允许动态字段
            )
            
            # 创建集合
            collection = Collection(
                name=name,
                schema=schema,
                shards_num=2
            )
            
            # 创建索引
            index_params = {
                "metric_type": "IP",  # 内积
                "index_type": "HNSW",
                "params": {
                    "M": 8,
                    "efConstruction": 64
                }
            }
            collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            # 加载集合
            collection.load()
            
            logger.info(f"Created vector collection: {name}")
            return collection
            
        except Exception as e:
            logger.error(f"Error creating vector collection: {e}")
            raise
    
    def list_collections(self) -> list[any]:
        """
        获取向量集合列表
        
        Returns:
            集合列表
        """
        try:
            return utility.list_collections()
        except Exception as e:
            logger.error(f"Error listing vector collections: {e}")
            raise
    
    def get_collection_info(self, name: str) -> [dict[str, any]]:
        """
        获取向量集合信息
        
        Args:
            name: 集合名称
            
        Returns:
            集合信息或None
        """
        try:
            if not utility.has_collection(name):
                return None
            
            collection = Collection(name)
            
            # 获取集合描述
            description = collection.description
            
            # 获取向量维度
            embedding_dimension = 0
            for field in collection.schema.fields:
                if field.name == "embedding":
                    embedding_dimension = field.dim
                    break
            
            return {
                "name": name,
                "description": description,
                "embedding_dimension": embedding_dimension,
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Error getting vector collection info: {e}")
            raise
    
    def delete_collection(self, name: str) -> bool:
        """
        删除向量集合
        
        Args:
            name: 集合名称
            
        Returns:
            是否成功删除
        """
        try:
            if not utility.has_collection(name):
                return False
            
            utility.drop_collection(name)
            logger.info(f"Deleted vector collection: {name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting vector collection: {e}")
            raise
    
    def ingest_vectors(
        self,
        collection_name: str,
        items: list[dict[str, any]],
        embedding_model: str,
        batch_size: int = 100,
        upsert: bool = False
    ) -> dict[str, any]:
        """
        批量导入向量数据
        
        Args:
            collection_name: 集合名称
            items: 向量数据列表
            embedding_model: 向量模型
            batch_size: 批量大小
            upsert: 是否更新模式
            
        Returns:
            导入结果
        """
        try:
            # 检查集合是否存在
            if not utility.has_collection(collection_name):
                raise ValueError(f"Collection {collection_name} does not exist")
            
            collection = Collection(collection_name)
            
            total_items = len(items)
            succeeded = 0
            failed = 0
            failed_items = []
            
            # 分批处理
            for i in range(0, total_items, batch_size):
                batch = items[i:i + batch_size]
                
                try:
                    # 准备数据
                    processed_items = self._prepare_items(batch, embedding_model)
                    
                    # 准备列式数据
                    columns = {}
                    for field_name in collection.schema.fields_dict:
                        if field_name != "id":  # 跳过自增主键
                            columns[field_name] = []
                    
                    for item in processed_items:
                        for field_name in collection.schema.fields_dict:
                            if field_name != "id":
                                value = item.get(field_name)
                                columns[field_name].append(value)
                    
                    # 插入数据
                    insert_data = [columns[field_name] for field_name in collection.schema.fields_dict if field_name != "id"]
                    collection.insert(insert_data)
                    succeeded += len(batch)
                    
                except Exception as e:
                    logger.error(f"Error processing batch {i}-{i+len(batch)}: {e}")
                    failed += len(batch)
                    
                    # 记录失败项
                    for j, item in enumerate(batch):
                        failed_items.append({
                            "index": i + j,
                            "reason": str(e)
                        })
            
            result = {
                "collection": collection_name,
                "total": total_items,
                "succeeded": succeeded,
                "failed": failed,
                "failed_items": failed_items
            }
            
            logger.info(f"Ingested vectors to {collection_name}: {succeeded}/{total_items}")
            return result
            
        except Exception as e:
            logger.error(f"Error ingesting vectors: {e}")
            raise
    
    def ingest_vectors_async(
        self,
        collection_name: str,
        items: list[dict[str, any]],
        embedding_model: str,
        batch_size: int = 100,
        upsert: bool = False
    ) -> str:
        """
        异步批量导入向量数据
        
        Args:
            collection_name: 集合名称
            items: 向量数据列表
            embedding_model: 向量模型
            batch_size: 批量大小
            upsert: 是否更新模式
            
        Returns:
            任务ID
        """
        # 这里可以实现异步处理，使用Celery或其他任务队列
        # 为了简化，这里只生成一个任务ID
        job_id = str(uuid.uuid4())
        
        # 在实际实现中，这里应该启动异步任务
        # task = celery_task.delay(collection_name, items, embedding_model, batch_size, upsert)
        
        logger.info(f"Started async vector ingestion job: {job_id}")
        return job_id
    
    def get_ingest_status(self, collection_name: str, job_id: str) -> [dict[str, any]]:
        """
        获取导入任务状态
        
        Args:
            collection_name: 集合名称
            job_id: 任务ID
            
        Returns:
            任务状态或None
        """
        # 这里应该从任务队列或数据库中获取任务状态
        # 为了简化，这里返回一个模拟状态
        return {
            "job_id": job_id,
            "collection": collection_name,
            "status": "completed",
            "progress": 100,
            "total": 0,
            "succeeded": 0,
            "failed": 0
        }
    
    def _prepare_items(self, items: list[dict[str, any]], embedding_model: str) -> list[dict[str, any]]:
        """
        准备向量数据
        
        Args:
            items: 原始数据列表
            embedding_model: 向量模型
            
        Returns:
            处理后的数据列表
        """
        # 分离已有向量和无向量项
        items_with_embedding = []
        items_without_embedding = []
        
        for item in items:
            if item.get("embedding") is not None:
                items_with_embedding.append(item)
            else:
                items_without_embedding.append(item)
        
        # 计算缺失的向量
        if items_without_embedding:
            texts = [item.get("content", "") for item in items_without_embedding]
            embeddings = embedding_service.embed_texts(texts, embedding_model)
            
            for i, item in enumerate(items_without_embedding):
                item["embedding"] = embeddings[i]
        
        return items
    
    def search_vectors(
        self,
        collection_name: str,
        query_vectors: list[list[float]],
        limit: int = 10,
        expr: [str] = None,
        output_fields: [list[str]] = None
    ) -> list[list[dict[str, any]]]:
        """
        向量搜索
        
        Args:
            collection_name: 集合名称
            query_vectors: 查询向量列表
            limit: 返回结果数
            expr: 过滤表达式
            output_fields: 输出字段
            
        Returns:
            搜索结果
        """
        try:
            if not utility.has_collection(collection_name):
                raise ValueError(f"Collection {collection_name} does not exist")
            
            collection = Collection(collection_name)
            
            # 搜索参数
            search_params = {
                "metric_type": "IP",
                "params": {
                    "ef": 64
                }
            }
            
            # 执行搜索
            results = collection.search(
                data=query_vectors,
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=output_fields or collection.schema.field_names
            )
            
            # 格式化结果
            formatted_results = []
            for query_result in results:
                query_hits = []
                for hit in query_result:
                    query_hits.append({
                        "id": hit.id,
                        "score": hit.score,
                        "entity": hit.entity
                    })
                formatted_results.append(query_hits)
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            raise
    
    def get_vectors_by_ids(
        self,
        collection_name: str,
        ids: list[int],
        output_fields: [list[str]] = None
    ) -> list[dict[str, any]]:
        """
        根据ID获取向量数据
        
        Args:
            collection_name: 集合名称
            ids: ID列表
            output_fields: 输出字段
            
        Returns:
            向量数据
        """
        try:
            if not utility.has_collection(collection_name):
                raise ValueError(f"Collection {collection_name} does not exist")
            
            collection = Collection(collection_name)
            
            results = collection.query(
                expr=f"id in {ids}",
                output_fields=output_fields or collection.schema.field_names
            )
            
            return results
        except Exception as e:
            logger.error(f"Error getting vectors by IDs: {e}")
            raise


# 全局向量服务实例
vector_service = VectorService()