"""
文档处理服务
整合文档路由、标注、结构化和向量化的完整流程
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.database import get_db
from app.services.document_routing import DocumentRoutingService
from app.services.labeling import LabelingService
from app.services.document_structure import DocumentStructureService
from app.services.vector_ingestion import VectorIngestionService
from app.crud.document import document_crud
from app.crud.section import section_crud
from app.crud.clause import clause_crud
from app.crud.clause_item import clause_item_crud


class DocumentProcessorService:
    """文档处理服务"""
    
    def __init__(
        self, 
        db: Session,
        document_routing: DocumentRoutingService,
        labeling_service: LabelingService,
        structure_service: DocumentStructureService,
        vector_service: VectorIngestionService
    ):
        self.db = db
        self.document_routing = document_routing
        self.labeling_service = labeling_service
        self.structure_service = structure_service
        self.vector_service = vector_service
    
    async def process_document(self, doc_data: dict[str, any]) -> dict[str, any]:
        """
        处理文档的完整流程
        
        Args:
            doc_data: 包含文档信息的字典
            
        Returns:
            处理结果
        """
        doc_id = doc_data.get("id")
        logger.info(f"开始处理文档: {doc_id}")
        
        try:
            # 步骤1: 创建文档记录
            document = await self._create_document_record(doc_data)
            
            # 步骤2: 路由和解析文档
            logger.info(f"路由和解析文档: {doc_id}")
            parse_result = self.document_routing.route_and_parse(doc_data)
            
            # 更新文档解析状态
            await self._update_document_status(doc_id, parse_status="completed")
            
            # 步骤3: 对段落进行标注
            logger.info(f"标注段落: {doc_id}")
            labeled_segments = self.labeling_service.label_segments(
                parse_result.get("parsed_segments", [])
            )
            
            # 步骤4: 结构化文档
            logger.info(f"结构化文档: {doc_id}")
            structured_data = self.structure_service.structure_document(
                doc_id, labeled_segments
            )
            
            # 步骤5: 保存结构化数据到数据库
            logger.info(f"保存结构化数据: {doc_id}")
            await self._save_structured_data(doc_id, structured_data)
            
            # 步骤6: 向量化并入库
            logger.info(f"向量化并入库: {doc_id}")
            vector_result = await self.vector_service.ingest_document_vectors(
                doc_id, structured_data
            )
            
            # 更新文档向量状态
            vector_status = "completed" if vector_result.get("success") else "failed"
            await self._update_document_status(doc_id, vector_status=vector_status)
            
            # 准备返回结果
            result = {
                "success": True,
                "doc_id": doc_id,
                "message": "文档处理完成",
                "parse_result": parse_result,
                "labeled_segments_count": len(labeled_segments),
                "structured_data": {
                    "sections_count": len(structured_data.get("sections", [])),
                    "clauses_count": len(structured_data.get("clauses", [])),
                    "clause_items_count": len(structured_data.get("clause_items", []))
                },
                "vector_result": vector_result
            }
            
            logger.info(f"文档处理完成: {doc_id}")
            return result
            
        except Exception as e:
            logger.error(f"文档处理失败: {doc_id}, 错误: {str(e)}")
            
            # 更新文档状态为失败
            await self._update_document_status(doc_id, status="failed")
            
            return {
                "success": False,
                "doc_id": doc_id,
                "message": f"文档处理失败: {str(e)}",
                "error": str(e)
            }
    
    async def _create_document_record(self, doc_data: dict[str, any]) -> any:
        """创建文档记录"""
        doc_id = doc_data.get("id")
        
        # 检查文档是否已存在
        existing_doc = document_crud.get(self.db, id=doc_id)
        if existing_doc:
            logger.info(f"文档已存在: {doc_id}")
            return existing_doc
        
        # 创建新文档
        document_data = {
            "id": doc_id,
            "name": doc_data.get("title", ""),
            "type": doc_data.get("type", ""),
            "created_at": doc_data.get("created_at") or datetime.now(),
            "file_url": doc_data.get("file_url"),
            "rich_content": doc_data.get("rich_content"),
            "drafters": doc_data.get("drafters", []),
            "status": "processing",
            "parse_status": "processing",
            "structure_status": "pending",
            "vector_status": "pending"
        }
        
        document = document_crud.create(self.db, obj_in=document_data)
        logger.info(f"创建文档记录: {doc_id}")
        return document
    
    async def _update_document_status(
        self, 
        doc_id: str, 
        status: [str] = None,
        parse_status: [str] = None,
        structure_status: [str] = None,
        vector_status: [str] = None
    ):
        """更新文档状态"""
        update_data = {}
        if status:
            update_data["status"] = status
        if parse_status:
            update_data["parse_status"] = parse_status
        if structure_status:
            update_data["structure_status"] = structure_status
        if vector_status:
            update_data["vector_status"] = vector_status
        
        if update_data:
            document_crud.update(self.db, db_obj_id=doc_id, obj_in=update_data)
            logger.info(f"更新文档状态: {doc_id}, {update_data}")
    
    async def _save_structured_data(self, doc_id: str, structured_data: dict[str, any]):
        """保存结构化数据到数据库"""
        sections = structured_data.get("sections", [])
        clauses = structured_data.get("clauses", [])
        clause_items = structured_data.get("clause_items", [])
        
        # 保存sections
        for section_data in sections:
            section_data["doc_id"] = doc_id
            section_crud.create(self.db, obj_in=section_data)
        
        # 保存clauses
        for clause_data in clauses:
            clause_data["doc_id"] = doc_id
            clause_crud.create(self.db, obj_in=clause_data)
        
        # 保存clause_items
        for item_data in clause_items:
            clause_item_crud.create(self.db, obj_in=item_data)
        
        # 更新结构化状态
        await self._update_document_status(doc_id, structure_status="completed")
        
        logger.info(f"保存结构化数据完成: {doc_id}, "
                   f"sections: {len(sections)}, "
                   f"clauses: {len(clauses)}, "
                   f"clause_items: {len(clause_items)}")
    
    async def reprocess_document(self, doc_id: str) -> dict[str, any]:
        """
        重新处理文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            处理结果
        """
        logger.info(f"重新处理文档: {doc_id}")
        
        try:
            # 获取文档信息
            document = document_crud.get(self.db, id=doc_id)
            if not document:
                return {
                    "success": False,
                    "message": f"文档不存在: {doc_id}"
                }
            
            # 删除现有向量数据
            await self.vector_service.delete_document_vectors(doc_id)
            
            # 删除现有结构化数据
            await self._delete_structured_data(doc_id)
            
            # 准备文档数据
            doc_data = {
                "id": doc_id,
                "title": document.name,
                "type": document.type,
                "created_at": document.created_at,
                "file_url": document.file_url,
                "rich_content": document.rich_content,
                "drafters": document.drafters
            }
            
            # 重新处理
            result = await self.process_document(doc_data)
            
            logger.info(f"文档重新处理完成: {doc_id}")
            return result
            
        except Exception as e:
            logger.error(f"文档重新处理失败: {doc_id}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"文档重新处理失败: {str(e)}",
                "error": str(e)
            }
    
    async def _delete_structured_data(self, doc_id: str):
        """删除结构化数据"""
        # 删除clause_items
        clause_item_crud.delete_by_doc_id(self.db, doc_id=doc_id)
        
        # 删除clauses
        clause_crud.delete_by_doc_id(self.db, doc_id=doc_id)
        
        # 删除sections
        section_crud.delete_by_doc_id(self.db, doc_id=doc_id)
        
        logger.info(f"删除结构化数据完成: {doc_id}")
    
    async def get_document_processing_status(self, doc_id: str) -> dict[str, any]:
        """
        获取文档处理状态
        
        Args:
            doc_id: 文档ID
            
        Returns:
            处理状态
        """
        try:
            document = document_crud.get(self.db, id=doc_id)
            if not document:
                return {
                    "success": False,
                    "message": f"文档不存在: {doc_id}"
                }
            
            # 获取结构化数据统计
            sections_count = section_crud.count_by_doc_id(self.db, doc_id=doc_id)
            clauses_count = clause_crud.count_by_doc_id(self.db, doc_id=doc_id)
            clause_items_count = clause_item_crud.count_by_doc_id(self.db, doc_id=doc_id)
            
            return {
                "success": True,
                "doc_id": doc_id,
                "status": document.status,
                "parse_status": document.parse_status,
                "structure_status": document.structure_status,
                "vector_status": document.vector_status,
                "statistics": {
                    "sections_count": sections_count,
                    "clauses_count": clauses_count,
                    "clause_items_count": clause_items_count
                }
            }
        except Exception as e:
            logger.error(f"获取文档处理状态失败: {doc_id}, 错误: {str(e)}")
            return {
                "success": False,
                "message": f"获取文档处理状态失败: {str(e)}",
                "error": str(e)
            }