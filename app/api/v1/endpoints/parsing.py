from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session


from app.core.database import get_db
from app.schemas.document import DocumentResponse
from app.services.document import document_service
from app.services.parser import parser_service
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/{document_id}/parse")
async def parse_document(
    document_id: str,
    parser_type: str = "auto",
    options: [dict[str, any]] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    解析文档
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 检查文档状态
    if document.get("parse_status") == "processing":
        raise HTTPException(status_code=400, detail="Document is currently being parsed")
    
    # 更新状态为处理中
    document_service.update_document_status(
        db=db,
        document_id=document_id,
        parse_status="processing"
    )
    
    # 异步处理解析任务
    background_tasks.add_task(
        parser_service.parse_document,
        db=db,
        document_id=document_id,
        parser_type=parser_type,
        options=options or {}
    )
    
    return {"message": "Document parsing started", "document_id": document_id}


@router.get("/{document_id}/parse")
async def get_parse_result(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    获取解析结果
    """
    # 检查文档是否存在
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 获取解析结果
    parse_result = parser_service.get_parse_result(db, document_id=document_id)
    
    return {
        "document_id": document_id,
        "parse_status": document.get("parse_status"),
        "parse_result": parse_result
    }