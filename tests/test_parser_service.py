import pytest
from unittest.mock import Mock, patch
from io import BytesIO

from app.services.parser import (
    PDFParser, DocxParser, TxtParser, MarkdownParser, HTMLParser,
    ParserService, TextBlock
)


class TestPDFParser:
    """PDF解析器测试"""
    
    def test_parse_pdf_text_extraction(self):
        """测试PDF文本提取解析"""
        # 创建模拟的PDF内容
        pdf_content = b"mock pdf content"
        
        # 创建模拟的PyMuPDF文档
        mock_page = Mock()
        mock_page.get_text.return_value = [
            (0, 0, 100, 20, "第一章 总则"),  # (x0, y0, x1, y1, text)
            (0, 25, 100, 45, "这是第一条内容"),
            (0, 50, 100, 70, "第二条 权利和义务"),
            (0, 75, 100, 95, "这是第二条内容")
        ]
        
        mock_doc = Mock()
        mock_doc.page_count = 1
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        with patch('fitz.open', return_value=mock_doc):
            parser = PDFParser()
            blocks = parser.parse(pdf_content, "pdf", {"use_ocr": False})
            
            # 验证结果
            assert len(blocks) == 4
            assert blocks[0].text == "第一章 总则"
            assert blocks[0].block_type == "heading"
            assert blocks[0].level == 1
            
            assert blocks[1].text == "这是第一条内容"
            assert blocks[1].block_type == "paragraph"
            
            assert blocks[2].text == "第二条 权利和义务"
            assert blocks[2].block_type == "heading"
            assert blocks[2].level == 2


class TestDocxParser:
    """DOCX解析器测试"""
    
    def test_parse_docx(self):
        """测试DOCX解析"""
        # 创建模拟的DOCX内容
        docx_content = b"mock docx content"
        
        # 创建模拟的文档和段落
        mock_paragraph1 = Mock()
        mock_paragraph1.text = "第一章 总则"
        mock_paragraph1.style.name = "Heading 1"
        mock_paragraph1.runs = [Mock(font_size=16, bold=True)]
        
        mock_paragraph2 = Mock()
        mock_paragraph2.text = "这是第一条内容"
        mock_paragraph2.style.name = "Normal"
        mock_paragraph2.runs = [Mock(font_size=12, bold=False)]
        
        mock_paragraph3 = Mock()
        mock_paragraph3.text = "第二条 权利和义务"
        mock_paragraph3.style.name = "Heading 2"
        mock_paragraph3.runs = [Mock(font_size=14, bold=True)]
        
        mock_doc = Mock()
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2, mock_paragraph3]
        mock_doc.tables = []
        
        with patch('docx.Document', return_value=mock_doc):
            parser = DocxParser()
            blocks = parser.parse(docx_content, "docx")
            
            # 验证结果
            assert len(blocks) == 3
            assert blocks[0].text == "第一章 总则"
            assert blocks[0].block_type == "heading"
            assert blocks[0].level == 1
            
            assert blocks[1].text == "这是第一条内容"
            assert blocks[1].block_type == "paragraph"
            
            assert blocks[2].text == "第二条 权利和义务"
            assert blocks[2].block_type == "heading"
            assert blocks[2].level == 2


class TestTxtParser:
    """TXT解析器测试"""
    
    def test_parse_txt(self):
        """测试TXT解析"""
        # 创建TXT内容
        txt_content = b"""第一章 总则
        
这是第一条内容。

第二条 权利和义务

这是第二条内容。"""
        
        parser = TxtParser()
        blocks = parser.parse(txt_content, "txt")
        
        # 验证结果
        assert len(blocks) >= 3
        
        # 找到标题块
        heading_blocks = [b for b in blocks if b.block_type == "heading"]
        assert len(heading_blocks) >= 1
        assert "第一章" in heading_blocks[0].text
        
        # 找到内容块
        content_blocks = [b for b in blocks if b.block_type == "paragraph"]
        assert len(content_blocks) >= 1
        assert "内容" in content_blocks[0].text


class TestMarkdownParser:
    """Markdown解析器测试"""
    
    def test_parse_markdown(self):
        """测试Markdown解析"""
        # 创建Markdown内容
        md_content = b"""# 第一章 总则

这是第一条内容。

## 第二条 权利和义务

这是第二条内容。"""
        
        parser = MarkdownParser()
        blocks = parser.parse(md_content, "md")
        
        # 验证结果
        assert len(blocks) >= 4
        
        # 找到标题块
        heading_blocks = [b for b in blocks if b.block_type == "heading"]
        assert len(heading_blocks) >= 2
        assert heading_blocks[0].level == 1
        assert "第一章" in heading_blocks[0].text
        assert heading_blocks[1].level == 2
        assert "第二条" in heading_blocks[1].text


class TestHTMLParser:
    """HTML解析器测试"""
    
    def test_parse_html(self):
        """测试HTML解析"""
        # 创建HTML内容
        html_content = b"""<html>
<body>
<h1>第一章 总则</h1>
<p>这是第一条内容。</p>
<h2>第二条 权利和义务</h2>
<p>这是第二条内容。</p>
</body>
</html>"""
        
        parser = HTMLParser()
        blocks = parser.parse(html_content, "html")
        
        # 验证结果
        assert len(blocks) >= 4
        
        # 找到标题块
        heading_blocks = [b for b in blocks if b.block_type == "heading"]
        assert len(heading_blocks) >= 2
        assert heading_blocks[0].level == 1
        assert "第一章" in heading_blocks[0].text
        assert heading_blocks[1].level == 2
        assert "第二条" in heading_blocks[1].text


class TestParserService:
    """解析服务测试"""
    
    def test_parse_document_pdf(self):
        """测试解析PDF文档"""
        # 创建模拟的数据库会话
        mock_db = Mock()
        
        # 创建模拟的文档信息
        mock_document = {
            "id": "doc123",
            "file_type": "pdf",
            "parse_status": "pending"
        }
        
        # 创建模拟的解析结果
        mock_blocks = [
            TextBlock(text="第一章 总则", block_type="heading", level=1).to_dict(),
            TextBlock(text="这是内容", block_type="paragraph", level=1).to_dict()
        ]
        
        with patch('app.services.parser.document_service.get_document') as mock_get_doc:
            with patch('app.services.parser.document_service.get_file_content') as mock_get_content:
                with patch('app.services.parser.PDFParser') as mock_parser_class:
                    with patch('app.services.parser.ParserService._save_parse_result') as mock_save:
                        with patch('app.services.parser.document_service.update_document_status') as mock_update:
                            # 设置模拟返回值
                            mock_get_doc.return_value = mock_document
                            mock_get_content.return_value = b"mock pdf content"
                            
                            mock_parser = Mock()
                            mock_parser.parse.return_value = mock_blocks
                            mock_parser_class.return_value = mock_parser
                            
                            # 执行解析
                            service = ParserService()
                            result = service.parse_document(mock_db, "doc123")
                            
                            # 验证结果
                            assert result["document_id"] == "doc123"
                            assert result["file_type"] == "pdf"
                            assert result["parser_type"] == "pdf"
                            assert len(result["blocks"]) == 2
                            assert result["total_blocks"] == 2
                            
                            # 验证调用了相关方法
                            mock_get_doc.assert_called_once()
                            mock_get_content.assert_called_once()
                            mock_parser.parse.assert_called_once()
                            mock_save.assert_called_once()
                            mock_update.assert_called_once_with(
                                db=mock_db,
                                document_id="doc123",
                                parse_status="completed"
                            )
    
    def test_parse_document_auto(self):
        """测试自动选择解析器"""
        # 创建模拟的数据库会话
        mock_db = Mock()
        
        # 创建模拟的文档信息
        mock_document = {
            "id": "doc123",
            "file_type": "pdf",
            "parse_status": "pending"
        }
        
        # 创建模拟的解析结果
        mock_blocks = [
            TextBlock(text="内容", block_type="paragraph", level=1).to_dict()
        ]
        
        with patch('app.services.parser.document_service.get_document') as mock_get_doc:
            with patch('app.services.parser.document_service.get_file_content') as mock_get_content:
                with patch('app.services.parser.PDFParser') as mock_parser_class:
                    with patch('app.services.parser.ParserService._save_parse_result') as mock_save:
                        with patch('app.services.parser.document_service.update_document_status') as mock_update:
                            # 设置模拟返回值
                            mock_get_doc.return_value = mock_document
                            mock_get_content.return_value = b"mock pdf content"
                            
                            mock_parser = Mock()
                            mock_parser.parse.return_value = mock_blocks
                            mock_parser_class.return_value = mock_parser
                            
                            # 执行解析（自动选择解析器）
                            service = ParserService()
                            result = service.parse_document(mock_db, "doc123", parser_type="auto")
                            
                            # 验证结果
                            assert result["parser_type"] == "pdf"  # 自动选择了PDF解析器
    
    def test_get_parse_result(self):
        """测试获取解析结果"""
        # 创建模拟的数据库会话
        mock_db = Mock()
        
        service = ParserService()
        result = service.get_parse_result(mock_db, "doc123")
        
        # 验证结果（当前实现返回None）
        assert result is None