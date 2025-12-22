import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUpdate,
    DocumentUploadResponse
)
from app.services.document import document_service
from app.core.config import settings
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    ingest_channel: str = Form(default="upload"),
    metadata: str = Form(default="{}"),
    db: Session = Depends(get_db)
):
    """
    上传文档
    """
    # 检查文件大小
    if file.size and file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE} bytes"
        )
    
    # 检查文件类型
    if file.content_type not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed"
        )
    
    try:
        # 解析元数据
        import json
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            metadata_dict = {}
        
        # 上传文档
        result = document_service.upload_document(
            db=db,
            file=file.file,
            file_name=file.filename,
            content_type=file.content_type,
            ingest_channel=ingest_channel,
            metadata=metadata_dict
        )
        
        return DocumentUploadResponse(**result)
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    获取文档信息
    """
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse(**document)


@router.get("/", response_model=DocumentListResponse)
async def get_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    status: [str] = Query(None),
    owner_id: [str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    获取文档列表
    """
    result = document_service.get_documents(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        owner_id=owner_id
    )
    
    return DocumentListResponse(**result)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    update_data: DocumentUpdate,
    db: Session = Depends(get_db)
):
    """
    更新文档信息
    """
    document = document_service.update_document(
        db=db,
        document_id=document_id,
        update_data=update_data.dict(exclude_unset=True)
    )
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse(**document)


@router.put("/{document_id}/status")
async def update_document_status(
    document_id: str,
    status: str,
    parse_status: [str] = None,
    structure_status: [str] = None,
    vector_status: [str] = None,
    db: Session = Depends(get_db)
):
    """
    更新文档状态
    """
    success = document_service.update_document_status(
        db=db,
        document_id=document_id,
        status=status,
        parse_status=parse_status,
        structure_status=structure_status,
        vector_status=vector_status
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"message": "Status updated successfully"}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    删除文档
    """
    success = document_service.delete_document(db=db, document_id=document_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"message": "Document deleted successfully"}


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    下载文档
    """
    # 获取文档信息
    document = document_service.get_document(db, document_id=document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 获取文件内容
    file_content = document_service.get_file_content(db, document_id=document_id)
    if not file_content:
        raise HTTPException(status_code=404, detail="File content not found")
    
    from fastapi.responses import Response
    file_name = document.get("name", "document")
    file_type = document.get("file_type", "application/octet-stream")
    
    # 设置MIME类型
    mime_type_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
        "html": "text/html"
    }
    content_type = mime_type_map.get(file_type, "application/octet-stream")
    
    return Response(
        content=file_content,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={file_name}"}
    )


@router.get("/search/{keyword}")
async def search_documents(
    keyword: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: Session = Depends(get_db)
):
    """
    搜索文档
    """
    result = document_service.search_documents(
        db=db,
        keyword=keyword,
        skip=skip,
        limit=limit
    )
    
    return DocumentListResponse(**result)