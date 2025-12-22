"""
文档LLM处理API接口
整合文档解析、LLM标注、结构化和向量化等功能
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logger import logger
from app.services.document_processing import DocumentProcessingService
from app.services.llm_labeling import LLMLabelingService
from app.services.document_structure import DocumentStructureService
from app.services.vector_ingestion import VectorIngestionService
from app.services.vector_collection import VectorCollectionService
from app.models.document import Document
from app.crud.document import document as document_crud
from app.crud.section import section as section_crud
from app.crud.clause import clause as clause_crud
from app.crud.clause_item import clause_item_crud
from app.schemas.document import DocumentCreate
from app.core.config import settings


router = APIRouter()


def get_llm_service() -> LLMLabelingService:
    """获取LLM标注服务实例"""
    return LLMLabelingService()


def get_document_structure_service() -> DocumentStructureService:
    """获取文档结构化服务实例"""
    return DocumentStructureService()


def get_vector_service() -> VectorIngestionService:
    """获取向量化服务实例"""
    # 直接创建 VectorIngestionService，不使用 MilvusClient
    # VectorIngestionService 内部会自己处理 pymilvus 连接
    # 这里可以注入embedding服务，目前使用默认实现
    embedding_service = None
    return VectorIngestionService(embedding_service)


def get_document_processing_service(
    llm_service: LLMLabelingService = Depends(get_llm_service),
    structure_service: DocumentStructureService = Depends(get_document_structure_service),
    vector_service: VectorIngestionService = Depends(get_vector_service)
) -> DocumentProcessingService:
    """获取文档处理服务实例"""
    return DocumentProcessingService(
        llm_service=llm_service,
        structure_service=structure_service,
        vector_service=vector_service
    )


def get_vector_collection_service() -> VectorCollectionService:
    """获取向量集合服务实例"""
    return VectorCollectionService()


@router.post("/process_document_v1")
async def process_document_v1(
    doc_data: dict[str, any],
    db: Session = Depends(get_db),
    processing_service: DocumentProcessingService = Depends(get_document_processing_service)
):
    """
    处理文档 (v1格式 - 从原始段落开始)
    
    Args:
        doc_data: 包含文档信息的字典
            - metadata: 文档元数据
                - id: 文档ID
                - title: 文档标题
                - type: 文档类型
                - created_at: 创建时间
                - file_url: 文件下载链接
                - drafters: 起草人信息
            - segments: 文档段落列表
                - id: 段落ID
                - order_index: 顺序索引
                - text: 段落文本
                - page: 页码（可选）
            - options: 处理选项
                - window_size: 滑动窗口大小，默认10
                - overlap: 窗口重叠大小，默认2
                - vectorize: 是否向量化，默认true
                - collection_name: 向量集合名称，可选
        db: 数据库会话
        processing_service: 文档处理服务
        
    Returns:
        处理结果
    """
    try:
        # 验证必需字段
        metadata = doc_data.get("metadata")
        if not metadata or "id" not in metadata:
            raise HTTPException(status_code=400, detail="缺少文档元数据或文档ID")
        
        segments = doc_data.get("segments", [])
        if not segments:
            raise HTTPException(status_code=400, detail="缺少文档段落数据")
        
        doc_id = metadata["id"]
        options = doc_data.get("options", {})
        
        # 检查文档是否已存在
        existing_doc = document_crud.get(db, id=doc_id)
        if existing_doc:
            logger.info(f"文档已存在，将更新: {doc_id}")
            # 这里可以选择更新或返回错误
            # 目前选择删除现有数据并重新创建
            document_crud.remove(db, id=doc_id)
        
        # 创建文档记录
        doc_create = DocumentCreate(
            id=metadata["id"],
            name=metadata.get("title", ""),
            type=metadata.get("type"),
            ingest_channel="api",
            file_type="unknown",  # 从文件URL推断或默认值
            file_url=metadata.get("file_url"),
            rich_content=None,  # 已在结构化数据中
            drafters=metadata.get("drafters"),
            metadata=metadata
        )
        
        db_doc = document_crud.create(db, obj_in=doc_create)
        logger.info(f"创建文档记录: {db_doc.id}")
        
        # 处理文档
        result = await processing_service.process_document_v1(
            doc_id=doc_id,
            segments=segments,
            metadata=metadata,
            options=options
        )
        
        if result["success"]:
            # 保存结构化数据到数据库
            structured_data = result["data"]["structured_data"]
            
            # 批量创建sections
            sections = structured_data.get("sections", [])
            if sections:
                section_crud.create_multi(db, objs_in=sections)
                logger.info(f"创建{len(sections)}个章节")
            
            # 批量创建clauses
            clauses = structured_data.get("clauses", [])
            if clauses:
                clause_crud.create_multi(db, objs_in=clauses)
                logger.info(f"创建{len(clauses)}个条款")
            
            # 批量创建clause_items
            clause_items = structured_data.get("clause_items", [])
            if clause_items:
                clause_item_crud.create_multi(db, objs_in=clause_items)
                logger.info(f"创建{len(clause_items)}个条款子项")
            
            # 更新文档状态
            document_crud.update_status(
                db, 
                db_obj=db_doc, 
                status="completed",
                parse_status="completed",
                structure_status="completed",
                vector_status="completed" if result["steps"]["vectorization"]["success"] else "skipped"
            )
            
            return {
                "success": True,
                "message": f"文档处理成功: {doc_id}",
                "doc_id": doc_id,
                "statistics": {
                    "segments": len(segments),
                    "sections": len(sections),
                    "clauses": len(clauses),
                    "clause_items": len(clause_items),
                    "vectorized": result["steps"]["vectorization"].get("succeeded", 0) if result["steps"]["vectorization"]["success"] else 0
                },
                "steps": result["steps"]
            }
        else:
            # 处理失败
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")


@router.post("/process_document_v2")
async def process_document_v2(
    doc_data: dict[str, any],
    db: Session = Depends(get_db),
    processing_service: DocumentProcessingService = Depends(get_document_processing_service)
):
    """
    处理文档 (v2格式 - 从预结构化数据开始)
    
    Args:
        doc_data: 包含文档信息的字典
            - metadata: 文档元数据
                - id: 文档ID
                - title: 文档标题
                - type: 文档类型
                - created_at: 创建时间
                - file_url: 文件下载链接
                - drafters: 起草人信息
            - structure: 文档结构数据
                - id: 元素ID
                - level: 层级
                - page: 页码
                - title: 标题
                - title_tags: 标题标签
                - content: 内容
                - content_tags: 内容标签
                - children: 子元素列表
            - options: 处理选项
                - vectorize: 是否向量化，默认true
                - collection_name: 向量集合名称，可选
        db: 数据库会话
        processing_service: 文档处理服务
        
    Returns:
        处理结果
    """
    try:
        # 验证必需字段
        metadata = doc_data.get("metadata")
        if not metadata or "id" not in metadata:
            raise HTTPException(status_code=400, detail="缺少文档元数据或文档ID")
        
        structure = doc_data.get("structure")
        if not structure:
            raise HTTPException(status_code=400, detail="缺少文档结构数据")
        
        doc_id = metadata["id"]
        options = doc_data.get("options", {})
        
        # 检查文档是否已存在
        existing_doc = document_crud.get(db, id=doc_id)
        if existing_doc:
            logger.info(f"文档已存在，将更新: {doc_id}")
            # 这里可以选择更新或返回错误
            # 目前选择删除现有数据并重新创建
            document_crud.remove(db, id=doc_id)
        
        # 创建文档记录
        doc_create = DocumentCreate(
            id=metadata["id"],
            name=metadata.get("title", ""),
            type=metadata.get("type"),
            ingest_channel="api",
            file_type="unknown",  # 从文件URL推断或默认值
            file_url=metadata.get("file_url"),
            rich_content=None,  # 已在结构化数据中
            drafters=metadata.get("drafters"),
            metadata=metadata
        )
        
        db_doc = document_crud.create(db, obj_in=doc_create)
        logger.info(f"创建文档记录: {db_doc.id}")
        
        # 处理文档
        result = await processing_service.process_document_v2(
            doc_id=doc_id,
            structure_data=structure,
            metadata=metadata,
            options=options
        )
        
        if result["success"]:
            # 保存结构化数据到数据库
            structured_data = result["data"]["structured_data"]
            
            # 批量创建sections
            sections = structured_data.get("sections", [])
            if sections:
                section_crud.create_multi(db, objs_in=sections)
                logger.info(f"创建{len(sections)}个章节")
            
            # 批量创建clauses
            clauses = structured_data.get("clauses", [])
            if clauses:
                clause_crud.create_multi(db, objs_in=clauses)
                logger.info(f"创建{len(clauses)}个条款")
            
            # 批量创建clause_items
            clause_items = structured_data.get("clause_items", [])
            if clause_items:
                clause_item_crud.create_multi(db, objs_in=clause_items)
                logger.info(f"创建{len(clause_items)}个条款子项")
            
            # 更新文档状态
            document_crud.update_status(
                db, 
                db_obj=db_doc, 
                status="completed",
                parse_status="completed",
                structure_status="completed",
                vector_status="completed" if result["steps"]["vectorization"]["success"] else "skipped"
            )
            
            return {
                "success": True,
                "message": f"文档处理成功: {doc_id}",
                "doc_id": doc_id,
                "statistics": {
                    "sections": len(sections),
                    "clauses": len(clauses),
                    "clause_items": len(clause_items),
                    "vectorized": result["steps"]["vectorization"].get("succeeded", 0) if result["steps"]["vectorization"]["success"] else 0
                },
                "steps": result["steps"]
            }
        else:
            # 处理失败
            raise HTTPException(status_code=500, detail=result["message"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")


@router.post("/process_document_v2_async")
async def process_document_v2_async(
    doc_data: dict[str, any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    异步处理文档 (v2格式)
    
    Args:
        doc_data: 包含文档信息的字典
        background_tasks: 后台任务
        db: 数据库会话
        
    Returns:
        接收结果
    """
    try:
        # 验证必需字段
        metadata = doc_data.get("metadata")
        if not metadata or "id" not in metadata:
            raise HTTPException(status_code=400, detail="缺少文档元数据或文档ID")
        
        structure = doc_data.get("structure")
        if not structure:
            raise HTTPException(status_code=400, detail="缺少文档结构数据")
        
        doc_id = metadata["id"]
        
        # 添加后台任务
        processing_service = get_document_processing_service()
        
        background_tasks.add_task(
            _process_document_async, 
            doc_data, 
            processing_service
        )
        
        return {
            "success": True,
            "message": f"文档已加入处理队列: {doc_id}",
            "doc_id": doc_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加文档处理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"添加文档处理任务失败: {str(e)}")


async def _process_document_async(
    doc_data: dict[str, any], 
    processing_service: DocumentProcessingService
):
    """异步处理文档的内部函数"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # 判断是v1还是v2格式
        if "segments" in doc_data:
            # v1格式
            await process_document_v1(doc_data, db, processing_service)
        elif "structure" in doc_data:
            # v2格式
            await process_document_v2(doc_data, db, processing_service)
        else:
            logger.error(f"未知的文档格式: {doc_data}")
    finally:
        db.close()