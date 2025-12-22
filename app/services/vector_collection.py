"""
向量集合管理服务
负责创建和管理Milvus向量集合
"""

from pymilvus import (
    connections, 
    FieldSchema, 
    CollectionSchema, 
    DataType, 
    Collection,
    utility
)

from app.core.logger import logger
from app.core.config import settings
from app.schemas.vector_collection import VectorCollectionCreate, VectorCollectionInfo


class VectorCollectionService:
    """向量集合管理服务"""
    
    def __init__(self):
        # 确保已连接到Milvus
        self._ensure_connection()
    
    def _ensure_connection(self):
        """确保Milvus连接已建立"""
        try:
            # 检查连接状态
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
    
    def create_collection(self, collection_data: VectorCollectionCreate) -> dict[str, any]:
        """
        创建新的向量集合
        
        Args:
            collection_data: 集合创建参数
            
        Returns:
            创建结果信息
        """
        try:
            collection_name = collection_data.name
            
            # 检查集合是否已存在
            if utility.has_collection(collection_name):
                logger.warning(f"集合已存在: {collection_name}")
                return {
                    "success": False,
                    "message": f"集合 {collection_name} 已存在",
                    "collection_name": collection_name
                }
            
            # 定义字段（FieldSchema）
            fields = [
                # 主键（Milvus 内部生成 AutoID）
                FieldSchema(
                    name="id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=True
                ),
                
                # 向量字段 （clause.content 或 clause_item.content 的 embedding）
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=collection_data.embedding_dimension
                ),
                
                # ----------------------- 元数据 -----------------------
                # 标识是 Clause 还是 ClauseItem
                FieldSchema(
                    name="unit_type",
                    dtype=DataType.VARCHAR,
                    max_length=16  # CLAUSE / CLAUSE_ITEM
                ),
                
                # 文档元数据
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
                
                # Section（章/节）
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
                
                # ---------------- Clause 字段 ----------------
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
                
                # ---------------- ClauseItem 字段 ----------------
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
                
                # ---------------- 文本内容（纯正文） ----------------
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=8192
                ),
                
                # ---------------- 业务字段 ----------------
                FieldSchema(
                    name="lang",
                    dtype=DataType.VARCHAR,
                    max_length=8  # zh / en / mixed
                ),
                FieldSchema(
                    name="role",
                    dtype=DataType.VARCHAR,
                    max_length=32  # CLAUSE / NON_CLAUSE
                ),
                FieldSchema(
                    name="region",
                    dtype=DataType.VARCHAR,
                    max_length=32  # MAIN / COVER / APPENDIX / SIGN
                ),
                FieldSchema(
                    name="nc_type",
                    dtype=DataType.VARCHAR,
                    max_length=64  # CLAUSE_BODY / SIGN_PAGE_BODY / ...
                ),
                
                # 定位信息 loc（json）
                FieldSchema(
                    name="loc",
                    dtype=DataType.JSON
                ),
            ]
            
            # 定义 Collection Schema
            schema = CollectionSchema(
                fields=fields, 
                description=collection_data.description or "向量集合",
                enable_dynamic_field=collection_data.options.get("enable_dynamic_fields", True)
            )
            
            # 创建 Milvus 集合
            shards_num = collection_data.options.get("shards_num", 2)
            collection = Collection(
                name=collection_name, 
                schema=schema, 
                shards_num=shards_num
            )
            
            # 创建索引（向量字段）
            index_params = {
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 8, "efConstruction": 64}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            
            logger.info(f"Milvus collection {collection_name} 创建成功！")
            
            return {
                "success": True,
                "message": f"集合 {collection_name} 创建成功",
                "collection_name": collection_name,
                "collection_info": {
                    "name": collection_name,
                    "description": collection_data.description,
                    "embedding_dimension": collection_data.embedding_dimension,
                    "options": collection_data.options
                }
            }
            
        except Exception as e:
            logger.error(f"创建向量集合失败: {str(e)}")
            return {
                "success": False,
                "message": f"创建向量集合失败: {str(e)}",
                "collection_name": collection_name
            }
    
    def list_collections(self) -> dict[str, any]:
        """
        列出所有向量集合
        
        Returns:
            集合列表信息
        """
        try:
            collection_names = utility.list_collections()
            collections_info = []
            
            for name in collection_names:
                try:
                    collection = Collection(name)
                    # 获取集合详细信息
                    info = {
                        "name": name,
                        "description": collection.description,
                        "num_entities": collection.num_entities,
                        "schema": collection.schema
                    }
                    collections_info.append(info)
                except Exception as e:
                    logger.warning(f"获取集合 {name} 信息失败: {str(e)}")
                    collections_info.append({
                        "name": name,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "message": f"获取到 {len(collections_info)} 个集合",
                "collections": collections_info,
                "total": len(collections_info)
            }
            
        except Exception as e:
            logger.error(f"列出向量集合失败: {str(e)}")
            return {
                "success": False,
                "message": f"列出向量集合失败: {str(e)}",
                "collections": [],
                "total": 0
            }
    
    def drop_collection(self, collection_name: str) -> dict[str, any]:
        """
        删除向量集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            删除结果信息
        """
        try:
            # 检查集合是否存在
            if not utility.has_collection(collection_name):
                logger.warning(f"集合不存在: {collection_name}")
                return {
                    "success": False,
                    "message": f"集合 {collection_name} 不存在",
                    "collection_name": collection_name
                }
            
            # 删除集合
            utility.drop_collection(collection_name)
            logger.info(f"向量集合 {collection_name} 删除成功")
            
            return {
                "success": True,
                "message": f"集合 {collection_name} 删除成功",
                "collection_name": collection_name
            }
            
        except Exception as e:
            logger.error(f"删除向量集合失败: {str(e)}")
            return {
                "success": False,
                "message": f"删除向量集合失败: {str(e)}",
                "collection_name": collection_name
            }
    
    def get_collection_info(self, collection_name: str) -> dict[str, any]:
        """
        获取向量集合详细信息
        
        Args:
            collection_name: 集合名称
            
        Returns:
            集合详细信息
        """
        try:
            # 检查集合是否存在
            if not utility.has_collection(collection_name):
                return {
                    "success": False,
                    "message": f"集合 {collection_name} 不存在",
                    "collection_name": collection_name
                }
            
            collection = Collection(collection_name)
            
            # 获取集合统计信息
            collection.load()
            stats = collection.get_stats()
            
            return {
                "success": True,
                "message": f"获取集合 {collection_name} 信息成功",
                "collection_name": collection_name,
                "collection_info": {
                    "name": collection_name,
                    "description": collection.description,
                    "schema": collection.schema,
                    "num_entities": collection.num_entities,
                    "index_info": collection.indexes,
                    "stats": stats
                }
            }
            
        except Exception as e:
            logger.error(f"获取集合信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取集合信息失败: {str(e)}",
                "collection_name": collection_name
            }