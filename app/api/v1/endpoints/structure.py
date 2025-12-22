from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session


from app.core.database import get_db
from app.schemas.document import DocumentResponse
from app.services.document import document_service
from app.services.structure import structure_service
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{document_id}/structure")
async def structure_document(
    document_id: str,
    structure_type: str = "auto",
    options: [dict[str, any]] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    结构化文档
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 检查文档解析状态
    if document.get("parse_status") != "completed":
        raise HTTPException(status_code=400, detail="Document must be parsed before structuring")
    
    # 检查文档结构化状态
    if document.get("structure_status") == "processing":
        raise HTTPException(status_code=400, detail="Document is currently being structured")
    
    # 更新状态为处理中
    document_service.update_document_status(
        db=db,
        document_id=document_id,
        structure_status="processing"
    )
    
    # 异步处理结构化任务
    background_tasks.add_task(
        structure_service.structure_document,
        db=db,
        document_id=document_id,
        structure_type=structure_type,
        options=options or {}
    )
    
    return {"message": "Document structuring started", "document_id": document_id}


@router.get("/{document_id}/structure")
async def get_structure_result(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    获取结构化结果
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 获取结构化结果
    structure_result = structure_service.get_structure_result(db, document_id=document_id)
    
    return {
        "document_id": document_id,
        "structure_status": document.get("structure_status"),
        "structure_result": structure_result
    }


@router.get("/{document_id}/sections")
async def get_document_sections(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    获取文档的章节列表
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 获取章节列表
    sections = structure_service.get_document_sections(db, document_id=document_id)
    
    return {
        "document_id": document_id,
        "sections": sections
    }


@router.get("/{document_id}/clauses")
async def get_document_clauses(
    document_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    获取文档的条款列表
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 获取条款列表
    clauses = structure_service.get_document_clauses(
        db=db,
        document_id=document_id,
        skip=skip,
        limit=limit
    )
    
    return {
        "document_id": document_id,
        "clauses": clauses["items"],
        "total": clauses["total"],
        "page": clauses["page"],
        "page_size": clauses["page_size"]
    }


@router.get("/{document_id}/clauses/{clause_id}")
async def get_clause_detail(
    document_id: str,
    clause_id: str,
    db: Session = Depends(get_db)
):
    """
    获取条款详情（包含子项）
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 获取条款详情
    clause = structure_service.get_clause_detail(db, clause_id=clause_id)
    
    if not clause:
        raise HTTPException(status_code=404, detail="Clause not found")
    
    return clause