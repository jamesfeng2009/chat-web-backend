"""
文档解析API接口
处理基于新数据结构的文档解析和结构化
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logger import logger
from app.services.document_structure import DocumentStructureService
from app.services.vector_ingestion import VectorIngestionService
from app.models.document import Document
from app.crud.document import document as document_crud
from app.crud.section import section as section_crud
from app.crud.clause import clause as clause_crud
from app.crud.clause_item import clause_item as clause_item_crud
from app.crud.paragraph_span import crud_paragraph_span
from app.schemas.document import DocumentCreate
from app.schemas.section import SectionCreate
from app.schemas.clause import ClauseCreate
from app.schemas.clause_item import ClauseItemCreate
from app.schemas.paragraph_span import ParagraphSpanCreate
from app.core.config import settings


router = APIRouter()


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


@router.post("/parse_structured_document")
async def parse_structured_document(
    doc_data: dict[str, any],
    db: Session = Depends(get_db),
    structure_service: DocumentStructureService = Depends(get_document_structure_service),
    vector_service: VectorIngestionService = Depends(get_vector_service)
):
    """
    解析结构化文档接口
    
    基于提供的数据结构解析文档，支持多级嵌套结构
    
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
        db: 数据库会话
        structure_service: 文档结构化服务
        vector_service: 向量化服务
    
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
        
        # 处理文档结构
        structured_result = structure_service.parse_document_structure(
            doc_id=doc_id,
            structure_data=structure,
            metadata=metadata
        )
        
        # 批量创建sections
        sections = structured_result.get("sections", [])
        if sections:
            section_crud.create_multi(db, objs_in=sections)
            logger.info(f"创建{len(sections)}个章节")
        
        # 批量创建clauses
        clauses = structured_result.get("clauses", [])
        if clauses:
            clause_crud.create_multi(db, objs_in=clauses)
            logger.info(f"创建{len(clauses)}个条款")
        
        # 批量创建clause_items
        clause_items = structured_result.get("clause_items", [])
        if clause_items:
            clause_item_crud.create_multi(db, objs_in=clause_items)
            logger.info(f"创建{len(clause_items)}个条款子项")
        
        # 向量化处理
        vectorization_enabled = doc_data.get("vectorization", True)
        vectors_data = []
        if vectorization_enabled and (clauses or clause_items):
            # 准备向量化数据
            vectors_data = []
            
            # 处理条款
            for clause in clauses:
                if clause.content:
                    vectors_data.append({
                        "type": "clause",
                        "id": clause.id,
                        "doc_id": doc_id,
                        "content": clause.content,
                        "metadata": {
                            "title": clause.title,
                            "number_token": clause.number_token,
                            "role": clause.role,
                            "region": clause.region,
                            "nc_type": clause.nc_type
                        }
                    })
            
            # 处理条款子项
            for item in clause_items:
                if item.content:
                    vectors_data.append({
                        "type": "clause_item",
                        "id": item.id,
                        "doc_id": doc_id,
                        "content": item.content,
                        "metadata": {
                            "title": item.title,
                            "number_token": item.number_token,
                            "role": item.role,
                            "region": item.region,
                            "nc_type": item.nc_type
                        }
                    })
            
            # 批量向量化
            if vectors_data:
                vector_result = await vector_service.batch_vectorize(vectors_data)
                logger.info(f"向量化{len(vectors_data)}个条款和子项，成功{vector_result.get('success_count', 0)}个")
                
                # 更新数据库中的embedding_id
                for vector_info in vector_result.get("results", []):
                    if vector_info.get("success") and vector_info.get("embedding_id"):
                        element_type = vector_info["type"]
                        element_id = vector_info["id"]
                        embedding_id = vector_info["embedding_id"]
                        
                        if element_type == "clause":
                            clause_crud.update_embedding_id(db, id=element_id, embedding_id=embedding_id)
                        elif element_type == "clause_item":
                            clause_item_crud.update_embedding_id(db, id=element_id, embedding_id=embedding_id)
        
        # 更新文档状态
        document_crud.update_status(
            db, 
            db_obj=db_doc, 
            status="completed",
            parse_status="completed",
            structure_status="completed",
            vector_status="completed" if vectorization_enabled else "skipped"
        )
        
        return {
            "success": True,
            "message": f"文档处理成功: {doc_id}",
            "doc_id": doc_id,
            "statistics": {
                "sections": len(sections),
                "clauses": len(clauses),
                "clause_items": len(clause_items),
                "vectorized": len(vectors_data) if vectorization_enabled else 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")


@router.post("/parse_structured_document_async")
async def parse_structured_document_async(
    doc_data: dict[str, any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    异步解析结构化文档接口
    
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
        structure_service = get_document_structure_service()
        vector_service = get_vector_service()
        
        background_tasks.add_task(
            _process_document_async, 
            doc_data, 
            structure_service, 
            vector_service
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
    structure_service: DocumentStructureService,
    vector_service: VectorIngestionService
):
    """异步处理文档的内部函数"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # 调用同步处理函数
        await parse_structured_document(
            doc_data=doc_data,
            db=db,
            structure_service=structure_service,
            vector_service=vector_service
        )
    finally:
        db.close()


@router.get("/get_document_structure/{doc_id}")
async def get_document_structure(
    doc_id: str,
    db: Session = Depends(get_db)
):
    """
    获取文档结构
    
    Args:
        doc_id: 文档ID
        db: 数据库会话
    
    Returns:
        文档结构数据
    """
    try:
        # 检查文档是否存在
        doc = document_crud.get(db, id=doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
        
        # 获取章节、条款和子项
        sections = section_crud.get_by_document(db, doc_id=doc_id)
        clauses = clause_crud.get_by_document(db, doc_id=doc_id)
        clause_items = clause_item_crud.get_by_document(db, doc_id=doc_id)
        
        # 构建层次结构
        result = {
            "metadata": {
                "id": doc.id,
                "title": doc.name,
                "type": doc.type,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "file_url": doc.file_url,
                "drafters": doc.drafters,
                "status": doc.status,
                "parse_status": doc.parse_status,
                "structure_status": doc.structure_status,
                "vector_status": doc.vector_status
            },
            "statistics": {
                "sections": len(sections),
                "clauses": len(clauses),
                "clause_items": len(clause_items)
            },
            "sections": [section.to_dict() for section in sections],
            "clauses": [clause.to_dict() for clause in clauses],
            "clause_items": [item.to_dict() for item in clause_items]
        }
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档结构失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档结构失败: {str(e)}")