import os
import uuid
from sqlalchemy.orm import Session

from app.crud.document import crud_document
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.services.storage import storage_service
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class DocumentService:
    """
    文档管理服务
    """
    
    @staticmethod
    def upload_document(
        db: Session,
        file: BinaryIO,
        file_name: str,
        content_type: str,
        ingest_channel: str = "upload",
        metadata: [dict[str, any]] = None
    ) -> dict[str, any]:
        """
        上传文档
        
        Args:
            db: 数据库会话
            file: 文件对象
            file_name: 文件名
            content_type: MIME类型
            ingest_channel: 导入渠道
            metadata: 文档元数据
            
        Returns:
            包含文档信息的字典
        """
        try:
            # 保存文件
            file_ref = storage_service.save_file(
                file=file,
                file_name=file_name,
                content_type=content_type,
                metadata=metadata
            )
            
            # 检查是否已存在相同校验和的文档
            checksum = file_ref.get("checksum")
            existing_doc = crud_document.get_by_checksum(db, checksum=checksum)
            
            if existing_doc:
                logger.info(f"Document with checksum {checksum} already exists: {existing_doc.id}")
                # 删除刚上传的重复文件
                storage_service.delete_file(file_ref)
                
                return {
                    "document_id": existing_doc.id,
                    "name": existing_doc.name,
                    "file_type": existing_doc.file_type,
                    "size": existing_doc.file_ref.get("file_size", 0),
                    "status": existing_doc.status,
                    "message": "Document already exists",
                    "duplicate": True
                }
            
            # 获取文件扩展名
            file_ext = os.path.splitext(file_name)[1].lower()
            file_type_map = {
                ".pdf": "pdf",
                ".docx": "docx",
                ".txt": "txt",
                ".md": "md",
                ".html": "html"
            }
            file_type = file_type_map.get(file_ext, "unknown")
            
            # 创建文档记录
            document_data = DocumentCreate(
                name=file_name,
                ingest_channel=ingest_channel,
                file_type=file_type,
                checksum=checksum,
                file_ref=file_ref,
                metadata=metadata or {}
            )
            
            document = crud_document.create(db, obj_in=document_data)
            
            return {
                "document_id": document.id,
                "name": document.name,
                "file_type": document.file_type,
                "size": file_ref.get("file_size", 0),
                "status": document.status,
                "message": "Document uploaded successfully",
                "duplicate": False
            }
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            raise
    
    @staticmethod
    def get_document(db: Session, document_id: str) -> [dict[str, any]]:
        """
        获取文档信息
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            
        Returns:
            文档信息或None
        """
        document = crud_document.get(db, id=document_id)
        if not document:
            return None
        
        return {
            "id": document.id,
            "name": document.name,
            "file_type": document.file_type,
            "ingest_channel": document.ingest_channel,
            "checksum": document.checksum,
            "status": document.status,
            "parse_status": document.parse_status,
            "structure_status": document.structure_status,
            "vector_status": document.vector_status,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "metadata": document.metadata,
            "file_ref": document.file_ref
        }
    
    @staticmethod
    def get_documents(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: [str] = None,
        owner_id: [str] = None
    ) -> dict[str, any]:
        """
        获取文档列表
        
        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数
            status: 状态过滤
            owner_id: 所有者过滤
            
        Returns:
            文档列表和总数
        """
        if owner_id:
            documents = crud_document.get_multi_by_owner(
                db, owner_id=owner_id, skip=skip, limit=limit, status=status
            )
            # 计算总数
            total = len(crud_document.get_multi_by_owner(
                db, owner_id=owner_id, skip=0, limit=10000, status=status
            ))
        elif status:
            documents = crud_document.get_multi_by_status(
                db, status=status, skip=skip, limit=limit
            )
            total = len(crud_document.get_multi_by_status(
                db, status=status, skip=0, limit=10000
            ))
        else:
            documents = crud_document.get_multi(db, skip=skip, limit=limit)
            total = len(crud_document.get_multi(db, skip=0, limit=10000))
        
        return {
            "items": [
                {
                    "id": doc.id,
                    "name": doc.name,
                    "file_type": doc.file_type,
                    "status": doc.status,
                    "parse_status": doc.parse_status,
                    "structure_status": doc.structure_status,
                    "vector_status": doc.vector_status,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat(),
                    "metadata": doc.metadata
                }
                for doc in documents
            ],
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }
    
    @staticmethod
    def update_document(
        db: Session,
        document_id: str,
        update_data: dict[str, any]
    ) -> [dict[str, any]]:
        """
        更新文档信息
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            update_data: 更新数据
            
        Returns:
            更新后的文档信息或None
        """
        document = crud_document.get(db, id=document_id)
        if not document:
            return None
        
        document = crud_document.update(db, db_obj=document, obj_in=update_data)
        
        return {
            "id": document.id,
            "name": document.name,
            "file_type": document.file_type,
            "status": document.status,
            "parse_status": document.parse_status,
            "structure_status": document.structure_status,
            "vector_status": document.vector_status,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "metadata": document.metadata
        }
    
    @staticmethod
    def update_document_status(
        db: Session,
        document_id: str,
        status: str,
        parse_status: [str] = None,
        structure_status: [str] = None,
        vector_status: [str] = None
    ) -> bool:
        """
        更新文档状态
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            status: 新状态
            parse_status: 解析状态
            structure_status: 结构化状态
            vector_status: 向量化状态
            
        Returns:
            是否更新成功
        """
        document = crud_document.get(db, id=document_id)
        if not document:
            return False
        
        crud_document.update_status(
            db,
            db_obj=document,
            status=status,
            parse_status=parse_status,
            structure_status=structure_status,
            vector_status=vector_status
        )
        
        return True
    
    @staticmethod
    def delete_document(db: Session, document_id: str) -> bool:
        """
        删除文档（逻辑删除）
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            
        Returns:
            是否删除成功
        """
        document = crud_document.get(db, id=document_id)
        if not document:
            return False
        
        # 删除文件
        if document.file_ref:
            storage_service.delete_file(document.file_ref)
        
        # 逻辑删除文档记录
        crud_document.remove(db, id=document.id)
        
        return True
    
    @staticmethod
    def get_file_content(db: Session, document_id: str) -> [bytes]:
        """
        获取文档文件内容
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            
        Returns:
            文件内容或None
        """
        document = crud_document.get(db, id=document_id)
        if not document or not document.file_ref:
            return None
        
        try:
            return storage_service.get_file(document.file_ref)
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None
    
    @staticmethod
    def search_documents(
        db: Session,
        keyword: str,
        skip: int = 0,
        limit: int = 100
    ) -> dict[str, any]:
        """
        搜索文档
        
        Args:
            db: 数据库会话
            keyword: 关键词
            skip: 跳过记录数
            limit: 返回记录数
            
        Returns:
            搜索结果和总数
        """
        documents = crud_document.search(db, keyword=keyword, skip=skip, limit=limit)
        total = len(crud_document.search(db, keyword=keyword, skip=0, limit=10000))
        
        return {
            "items": [
                {
                    "id": doc.id,
                    "name": doc.name,
                    "file_type": doc.file_type,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat(),
                    "metadata": doc.metadata
                }
                for doc in documents
            ],
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit
        }


# 全局文档服务实例
document_service = DocumentService()