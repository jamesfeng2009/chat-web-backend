import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.services.document import DocumentService
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.crud.document import CRUDDocument


class TestDocumentService:
    """文档服务测试"""
    
    def test_upload_document_success(self, db_session, sample_document_content):
        """测试文档上传成功"""
        # 创建模拟的文件对象
        mock_file = Mock()
        mock_file.read.return_value = b"file content"
        mock_file.seek.return_value = 0
        mock_file.tell.return_value = len(b"file content")
        
        # 模拟文件存储服务
        with patch('app.services.document.storage_service.save_file') as mock_save:
            mock_save.return_value = {
                "file_name": "test.pdf",
                "file_size": 100,
                "checksum": "abc123",
                "storage_type": "local",
                "full_path": "/tmp/test.pdf"
            }
            
            # 模拟校验和检查
            with patch('app.crud.document.crud_document.get_by_checksum') as mock_check:
                mock_check.return_value = None  # 不存在重复文档
                
                # 执行上传
                result = DocumentService.upload_document(
                    db=db_session,
                    file=mock_file,
                    file_name="test.pdf",
                    content_type="application/pdf",
                    ingest_channel="upload",
                    metadata={"type": "contract"}
                )
                
                # 验证结果
                assert result["name"] == "test.pdf"
                assert result["file_type"] == "pdf"
                assert result["status"] == "uploaded"
                assert not result["duplicate"]
    
    def test_upload_document_duplicate(self, db_session, sample_document_content):
        """测试文档上传重复"""
        # 创建模拟的文件对象
        mock_file = Mock()
        mock_file.read.return_value = b"file content"
        mock_file.seek.return_value = 0
        mock_file.tell.return_value = len(b"file content")
        
        # 创建模拟的重复文档
        mock_doc = Mock()
        mock_doc.id = "doc123"
        mock_doc.name = "existing.pdf"
        mock_doc.file_type = "pdf"
        mock_doc.status = "uploaded"
        mock_doc.file_ref = {"file_size": 100}
        
        # 模拟文件存储服务
        with patch('app.services.document.storage_service.save_file') as mock_save:
            mock_save.return_value = {
                "file_name": "test.pdf",
                "file_size": 100,
                "checksum": "abc123",
                "storage_type": "local",
                "full_path": "/tmp/test.pdf"
            }
            
            # 模拟校验和检查 - 存在重复文档
            with patch('app.crud.document.crud_document.get_by_checksum') as mock_check:
                mock_check.return_value = mock_doc
                
                # 模拟删除重复文件
                with patch('app.services.document.storage_service.delete_file') as mock_delete:
                    # 执行上传
                    result = DocumentService.upload_document(
                        db=db_session,
                        file=mock_file,
                        file_name="test.pdf",
                        content_type="application/pdf"
                    )
                    
                    # 验证结果
                    assert result["name"] == "existing.pdf"
                    assert result["file_type"] == "pdf"
                    assert result["status"] == "uploaded"
                    assert result["duplicate"]
                    
                    # 验证删除了重复文件
                    mock_delete.assert_called_once()
    
    def test_get_document_success(self, db_session):
        """测试获取文档成功"""
        # 创建模拟文档
        mock_doc = Mock()
        mock_doc.id = "doc123"
        mock_doc.name = "test.pdf"
        mock_doc.file_type = "pdf"
        mock_doc.status = "uploaded"
        mock_doc.parse_status = "completed"
        mock_doc.structure_status = "completed"
        mock_doc.vector_status = "completed"
        mock_doc.created_at = "2023-01-01"
        mock_doc.updated_at = "2023-01-01"
        mock_doc.metadata = {"type": "contract"}
        mock_doc.file_ref = {"file_path": "/tmp/test.pdf"}
        
        with patch('app.crud.document.crud_document.get') as mock_get:
            mock_get.return_value = mock_doc
            
            # 执行获取
            result = DocumentService.get_document(db_session, "doc123")
            
            # 验证结果
            assert result["id"] == "doc123"
            assert result["name"] == "test.pdf"
            assert result["file_type"] == "pdf"
            assert result["status"] == "uploaded"
    
    def test_get_document_not_found(self, db_session):
        """测试获取文档不存在"""
        with patch('app.crud.document.crud_document.get') as mock_get:
            mock_get.return_value = None
            
            # 执行获取
            result = DocumentService.get_document(db_session, "nonexistent")
            
            # 验证结果
            assert result is None
    
    def test_get_documents(self, db_session):
        """测试获取文档列表"""
        # 创建模拟文档列表
        mock_docs = []
        for i in range(5):
            mock_doc = Mock()
            mock_doc.id = f"doc{i}"
            mock_doc.name = f"test{i}.pdf"
            mock_doc.file_type = "pdf"
            mock_doc.status = "uploaded"
            mock_doc.parse_status = "completed"
            mock_doc.structure_status = "completed"
            mock_doc.vector_status = "completed"
            mock_doc.created_at = "2023-01-01"
            mock_doc.updated_at = "2023-01-01"
            mock_doc.metadata = {"type": "contract"}
            mock_docs.append(mock_doc)
        
        with patch('app.crud.document.crud_document.get_multi') as mock_get_multi:
            with patch('app.crud.document.crud_document.get_multi') as mock_count:
                mock_get_multi.return_value = mock_docs[:3]  # 分页结果
                mock_count.return_value = mock_docs  # 总数
                
                # 执行获取
                result = DocumentService.get_documents(db_session, skip=0, limit=3)
                
                # 验证结果
                assert result["total"] == 5
                assert len(result["items"]) == 3
                assert result["page"] == 1
                assert result["page_size"] == 3
    
    def test_update_document_success(self, db_session):
        """测试更新文档成功"""
        # 创建模拟文档
        mock_doc = Mock()
        mock_doc.id = "doc123"
        mock_doc.name = "test.pdf"
        mock_doc.file_type = "pdf"
        mock_doc.status = "uploaded"
        mock_doc.created_at = "2023-01-01"
        mock_doc.updated_at = "2023-01-01"
        mock_doc.metadata = {"type": "contract"}
        
        # 更新后的文档
        updated_doc = Mock()
        updated_doc.id = "doc123"
        updated_doc.name = "updated.pdf"
        updated_doc.file_type = "pdf"
        updated_doc.status = "uploaded"
        updated_doc.created_at = "2023-01-01"
        updated_doc.updated_at = "2023-01-02"
        updated_doc.metadata = {"type": "updated_contract"}
        
        with patch('app.crud.document.crud_document.get') as mock_get:
            with patch('app.crud.document.crud_document.update') as mock_update:
                mock_get.return_value = mock_doc
                mock_update.return_value = updated_doc
                
                # 执行更新
                result = DocumentService.update_document(
                    db_session,
                    "doc123",
                    {"name": "updated.pdf", "metadata": {"type": "updated_contract"}}
                )
                
                # 验证结果
                assert result["id"] == "doc123"
                assert result["name"] == "updated.pdf"
                assert result["metadata"]["type"] == "updated_contract"
    
    def test_update_document_not_found(self, db_session):
        """测试更新文档不存在"""
        with patch('app.crud.document.crud_document.get') as mock_get:
            mock_get.return_value = None
            
            # 执行更新
            result = DocumentService.update_document(
                db_session,
                "nonexistent",
                {"name": "updated.pdf"}
            )
            
            # 验证结果
            assert result is None
    
    def test_update_document_status(self, db_session):
        """测试更新文档状态"""
        # 创建模拟文档
        mock_doc = Mock()
        
        with patch('app.crud.document.crud_document.get') as mock_get:
            with patch('app.crud.document.crud_document.update_status') as mock_update:
                mock_get.return_value = mock_doc
                mock_update.return_value = mock_doc
                
                # 执行更新状态
                result = DocumentService.update_document_status(
                    db_session,
                    "doc123",
                    status="completed",
                    parse_status="completed"
                )
                
                # 验证结果
                assert result is True
    
    def test_update_document_status_not_found(self, db_session):
        """测试更新文档状态不存在"""
        with patch('app.crud.document.crud_document.get') as mock_get:
            mock_get.return_value = None
            
            # 执行更新状态
            result = DocumentService.update_document_status(
                db_session,
                "nonexistent",
                status="completed"
            )
            
            # 验证结果
            assert result is False
    
    def test_delete_document_success(self, db_session):
        """测试删除文档成功"""
        # 创建模拟文档
        mock_doc = Mock()
        mock_doc.file_ref = {"file_path": "/tmp/test.pdf"}
        
        with patch('app.crud.document.crud_document.get') as mock_get:
            with patch('app.crud.document.crud_document.remove') as mock_remove:
                with patch('app.services.document.storage_service.delete_file') as mock_delete:
                    mock_get.return_value = mock_doc
                    mock_remove.return_value = mock_doc
                    
                    # 执行删除
                    result = DocumentService.delete_document(db_session, "doc123")
                    
                    # 验证结果
                    assert result is True
                    
                    # 验证删除了文件
                    mock_delete.assert_called_once()
    
    def test_delete_document_not_found(self, db_session):
        """测试删除文档不存在"""
        with patch('app.crud.document.crud_document.get') as mock_get:
            mock_get.return_value = None
            
            # 执行删除
            result = DocumentService.delete_document(db_session, "nonexistent")
            
            # 验证结果
            assert result is False
    
    def test_get_file_content_success(self, db_session):
        """测试获取文档内容成功"""
        # 创建模拟文档
        mock_doc = Mock()
        mock_doc.file_ref = {"file_path": "/tmp/test.pdf"}
        
        with patch('app.crud.document.crud_document.get') as mock_get:
            with patch('app.services.document.storage_service.get_file') as mock_get_file:
                mock_get.return_value = mock_doc
                mock_get_file.return_value = b"file content"
                
                # 执行获取
                result = DocumentService.get_file_content(db_session, "doc123")
                
                # 验证结果
                assert result == b"file content"
    
    def test_get_file_content_not_found(self, db_session):
        """测试获取文档内容不存在"""
        with patch('app.crud.document.crud_document.get') as mock_get:
            mock_get.return_value = None
            
            # 执行获取
            result = DocumentService.get_file_content(db_session, "nonexistent")
            
            # 验证结果
            assert result is None
    
    def test_search_documents(self, db_session):
        """测试搜索文档"""
        # 创建模拟文档列表
        mock_docs = []
        for i in range(3):
            mock_doc = Mock()
            mock_doc.id = f"doc{i}"
            mock_doc.name = f"test{i}.pdf"
            mock_doc.file_type = "pdf"
            mock_doc.status = "uploaded"
            mock_doc.created_at = "2023-01-01"
            mock_doc.metadata = {"type": "contract"}
            mock_docs.append(mock_doc)
        
        with patch('app.crud.document.crud_document.search') as mock_search:
            with patch('app.crud.document.crud_document.search') as mock_count:
                mock_search.return_value = mock_docs
                mock_count.return_value = mock_docs
                
                # 执行搜索
                result = DocumentService.search_documents(db_session, "test", skip=0, limit=3)
                
                # 验证结果
                assert result["total"] == 3
                assert len(result["items"]) == 3
                assert result["page"] == 1
                assert result["page_size"] == 3