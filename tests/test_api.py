import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch


class TestHealthAPI:
    """健康检查API测试"""
    
    def test_health_check(self, client):
        """测试健康检查接口"""
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data


class TestDocumentAPI:
    """文档API测试"""
    
    def test_upload_document_success(self, client):
        """测试文档上传成功"""
        # 模拟文档上传服务
        with patch('app.api.v1.endpoints.documents.document_service.upload_document') as mock_upload:
            mock_upload.return_value = {
                "document_id": "doc123",
                "name": "test.pdf",
                "file_type": "pdf",
                "size": 1024,
                "status": "uploaded",
                "message": "Document uploaded successfully",
                "duplicate": False
            }
            
            # 准备测试文件
            files = {"file": ("test.pdf", b"mock pdf content", "application/pdf")}
            data = {"ingest_channel": "upload", "metadata": "{}"}
            
            # 发送请求
            response = client.post("/api/v1/documents/upload", files=files, data=data)
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert data["document_id"] == "doc123"
            assert data["name"] == "test.pdf"
            assert data["file_type"] == "pdf"
            assert not data["duplicate"]
    
    def test_upload_document_duplicate(self, client):
        """测试文档上传重复"""
        # 模拟文档上传服务
        with patch('app.api.v1.endpoints.documents.document_service.upload_document') as mock_upload:
            mock_upload.return_value = {
                "document_id": "doc123",
                "name": "existing.pdf",
                "file_type": "pdf",
                "size": 1024,
                "status": "uploaded",
                "message": "Document already exists",
                "duplicate": True
            }
            
            # 准备测试文件
            files = {"file": ("test.pdf", b"mock pdf content", "application/pdf")}
            data = {"ingest_channel": "upload"}
            
            # 发送请求
            response = client.post("/api/v1/documents/upload", files=files, data=data)
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert data["duplicate"]
            assert data["message"] == "Document already exists"
    
    def test_upload_document_file_too_large(self, client):
        """测试上传文件过大"""
        with patch('app.api.v1.endpoints.documents.settings.MAX_FILE_SIZE', 100):
            # 准备超大测试文件
            large_content = b"x" * 200  # 大于最大限制
            files = {"file": ("large.pdf", large_content, "application/pdf")}
            data = {"ingest_channel": "upload"}
            
            # 发送请求
            response = client.post("/api/v1/documents/upload", files=files, data=data)
            
            # 验证结果
            assert response.status_code == 413
            assert "File too large" in response.json()["detail"]
    
    def test_upload_document_invalid_type(self, client):
        """测试上传不支持的文件类型"""
        # 准备不支持的测试文件
        files = {"file": ("test.exe", b"mock exe content", "application/octet-stream")}
        data = {"ingest_channel": "upload"}
        
        # 发送请求
        response = client.post("/api/v1/documents/upload", files=files, data=data)
        
        # 验证结果
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]
    
    def test_get_document_success(self, client):
        """测试获取文档成功"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.documents.document_service.get_document') as mock_get:
            mock_get.return_value = {
                "id": "doc123",
                "name": "test.pdf",
                "file_type": "pdf",
                "status": "uploaded",
                "parse_status": "completed",
                "structure_status": "completed",
                "vector_status": "completed",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {"type": "contract"}
            }
            
            # 发送请求
            response = client.get("/api/v1/documents/doc123")
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "doc123"
            assert data["name"] == "test.pdf"
            assert data["file_type"] == "pdf"
    
    def test_get_document_not_found(self, client):
        """测试获取文档不存在"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.documents.document_service.get_document') as mock_get:
            mock_get.return_value = None
            
            # 发送请求
            response = client.get("/api/v1/documents/nonexistent")
            
            # 验证结果
            assert response.status_code == 404
    
    def test_get_documents(self, client):
        """测试获取文档列表"""
        # 模拟文档列表获取服务
        with patch('app.api.v1.endpoints.documents.document_service.get_documents') as mock_get:
            mock_get.return_value = {
                "items": [
                    {
                        "id": "doc1",
                        "name": "test1.pdf",
                        "file_type": "pdf",
                        "status": "uploaded",
                        "created_at": "2023-01-01T00:00:00"
                    },
                    {
                        "id": "doc2",
                        "name": "test2.pdf",
                        "file_type": "pdf",
                        "status": "uploaded",
                        "created_at": "2023-01-02T00:00:00"
                    }
                ],
                "total": 2,
                "page": 1,
                "page_size": 20
            }
            
            # 发送请求
            response = client.get("/api/v1/documents/")
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["total"] == 2
            assert data["page"] == 1
            assert data["page_size"] == 20
    
    def test_update_document_success(self, client):
        """测试更新文档成功"""
        # 模拟文档更新服务
        with patch('app.api.v1.endpoints.documents.document_service.update_document') as mock_update:
            mock_update.return_value = {
                "id": "doc123",
                "name": "updated.pdf",
                "file_type": "pdf",
                "status": "uploaded",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-02T00:00:00",
                "metadata": {"type": "updated_contract"}
            }
            
            # 准备更新数据
            update_data = {"name": "updated.pdf", "metadata": {"type": "updated_contract"}}
            
            # 发送请求
            response = client.put("/api/v1/documents/doc123", json=update_data)
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "updated.pdf"
            assert data["metadata"]["type"] == "updated_contract"
    
    def test_update_document_not_found(self, client):
        """测试更新文档不存在"""
        # 模拟文档更新服务
        with patch('app.api.v1.endpoints.documents.document_service.update_document') as mock_update:
            mock_update.return_value = None
            
            # 准备更新数据
            update_data = {"name": "updated.pdf"}
            
            # 发送请求
            response = client.put("/api/v1/documents/nonexistent", json=update_data)
            
            # 验证结果
            assert response.status_code == 404
    
    def test_update_document_status(self, client):
        """测试更新文档状态"""
        # 模拟文档状态更新服务
        with patch('app.api.v1.endpoints.documents.document_service.update_document_status') as mock_update:
            mock_update.return_value = True
            
            # 发送请求
            response = client.put("/api/v1/documents/doc123/status", params={"status": "completed"})
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Status updated successfully"
    
    def test_update_document_status_not_found(self, client):
        """测试更新文档状态不存在"""
        # 模拟文档状态更新服务
        with patch('app.api.v1.endpoints.documents.document_service.update_document_status') as mock_update:
            mock_update.return_value = False
            
            # 发送请求
            response = client.put("/api/v1/documents/nonexistent/status", params={"status": "completed"})
            
            # 验证结果
            assert response.status_code == 404
    
    def test_delete_document_success(self, client):
        """测试删除文档成功"""
        # 模拟文档删除服务
        with patch('app.api.v1.endpoints.documents.document_service.delete_document') as mock_delete:
            mock_delete.return_value = True
            
            # 发送请求
            response = client.delete("/api/v1/documents/doc123")
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Document deleted successfully"
    
    def test_delete_document_not_found(self, client):
        """测试删除文档不存在"""
        # 模拟文档删除服务
        with patch('app.api.v1.endpoints.documents.document_service.delete_document') as mock_delete:
            mock_delete.return_value = False
            
            # 发送请求
            response = client.delete("/api/v1/documents/nonexistent")
            
            # 验证结果
            assert response.status_code == 404
    
    def test_search_documents(self, client):
        """测试搜索文档"""
        # 模拟文档搜索服务
        with patch('app.api.v1.endpoints.documents.document_service.search_documents') as mock_search:
            mock_search.return_value = {
                "items": [
                    {
                        "id": "doc1",
                        "name": "contract1.pdf",
                        "file_type": "pdf",
                        "status": "uploaded",
                        "created_at": "2023-01-01T00:00:00",
                        "metadata": {"type": "contract"}
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20
            }
            
            # 发送请求
            response = client.get("/api/v1/documents/search/contract")
            
            # 验证结果
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["total"] == 1
            assert data["items"][0]["name"] == "contract1.pdf"


class TestParsingAPI:
    """解析API测试"""
    
    def test_parse_document(self, client):
        """测试解析文档"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.parsing.document_service.get_document') as mock_get_doc:
            mock_get_doc.return_value = {
                "id": "doc123",
                "file_type": "pdf",
                "parse_status": "uploaded"  # 未解析
            }
            
            # 模拟解析服务
            with patch('app.api.v1.endpoints.parsing.parser_service.parse_document') as mock_parse:
                mock_parse.return_value = {
                    "document_id": "doc123",
                    "file_type": "pdf",
                    "parser_type": "pdf",
                    "blocks": [
                        {"text": "第一章", "block_type": "heading"},
                        {"text": "内容", "block_type": "paragraph"}
                    ],
                    "total_blocks": 2
                }
                
                # 发送请求
                response = client.post("/api/v1/parsing/doc123/parse", json={"parser_type": "auto"})
                
                # 验证结果
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Document parsing started"
                assert data["document_id"] == "doc123"
    
    def test_parse_document_not_found(self, client):
        """测试解析文档不存在"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.parsing.document_service.get_document') as mock_get_doc:
            mock_get_doc.return_value = None
            
            # 发送请求
            response = client.post("/api/v1/parsing/nonexistent/parse")
            
            # 验证结果
            assert response.status_code == 404
    
    def test_parse_document_already_processing(self, client):
        """测试解析文档已在处理中"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.parsing.document_service.get_document') as mock_get_doc:
            mock_get_doc.return_value = {
                "id": "doc123",
                "file_type": "pdf",
                "parse_status": "processing"  # 正在处理
            }
            
            # 发送请求
            response = client.post("/api/v1/parsing/doc123/parse")
            
            # 验证结果
            assert response.status_code == 400
            assert "currently being parsed" in response.json()["detail"]
    
    def test_get_parse_result(self, client):
        """测试获取解析结果"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.parsing.document_service.get_document') as mock_get_doc:
            mock_get_doc.return_value = {
                "id": "doc123",
                "file_type": "pdf",
                "parse_status": "completed"
            }
            
            # 模拟解析结果获取服务
            with patch('app.api.v1.endpoints.parsing.parser_service.get_parse_result') as mock_get_result:
                mock_get_result.return_value = {
                    "document_id": "doc123",
                    "file_type": "pdf",
                    "blocks": [
                        {"text": "第一章", "block_type": "heading"},
                        {"text": "内容", "block_type": "paragraph"}
                    ],
                    "total_blocks": 2
                }
                
                # 发送请求
                response = client.get("/api/v1/parsing/doc123/parse")
                
                # 验证结果
                assert response.status_code == 200
                data = response.json()
                assert data["document_id"] == "doc123"
                assert data["parse_status"] == "completed"
                assert len(data["parse_result"]["blocks"]) == 2
    
    def test_get_parse_result_not_found(self, client):
        """测试获取解析结果文档不存在"""
        # 模拟文档获取服务
        with patch('app.api.v1.endpoints.parsing.document_service.get_document') as mock_get_doc:
            mock_get_doc.return_value = None
            
            # 发送请求
            response = client.get("/api/v1/parsing/nonexistent/parse")
            
            # 验证结果
            assert response.status_code == 404