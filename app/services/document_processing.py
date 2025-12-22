"""
文档处理服务
整合三管线LLM标注服务和向量摄入服务
"""
import asyncio

from app.core.logger import get_logger

logger = get_logger(__name__)
from app.services.llm_labeling import PipelineLLMLabelingService
from app.services.vector_ingestion import VectorIngestionService
from app.services.document_structure import DocumentStructureService
from app.schemas.vector_ingestion import VectorIngestItem, VectorIngestRequest


class DocumentProcessingService:
    """文档处理服务 - 整合三管线LLM标注"""
    
    def __init__(self, embedding_service=None):
        self.llm_service = PipelineLLMLabelingService()
        self.vector_service = VectorIngestionService(embedding_service)
        self.doc_structure_service = DocumentStructureService()
    
    def _parse_document_content(self, document_content: str) -> dict:
        """
        解析文档内容，提取段落
        
        Args:
            document_content: 文档内容
            
        Returns:
            包含段落的字典
        """
        try:
            # 简单的段落分割逻辑
            paragraphs = document_content.split('\n\n')
            segments = []
            
            for i, paragraph in enumerate(paragraphs):
                if paragraph.strip():  # 忽略空段落
                    segments.append({
                        "id": f"seg_{i}",
                        "text": paragraph.strip(),
                        "order_index": i
                    })
            
            return {"segments": segments}
        except Exception as e:
            logger.error(f"解析文档内容失败: {str(e)}")
            return {"segments": []}
    
    async def process_document(
        self,
        document_content: str,
        doc_id: str,
        doc_name: str,
        embedding_model: str = "text-embedding-3-large",
        collection_name: str = "mirrors_clause_vectors",
        lang: str = "zh",
        score_threshold: str = "1"
    ) -> dict[str, any]:
        """
        处理文档：解析结构、LLM标注、向量化和存储
        
        Args:
            document_content: 文档内容
            doc_id: 文档ID
            doc_name: 文档名称
            embedding_model: 嵌入模型名称
            collection_name: 向量集合名称
            lang: 语言代码
            score_threshold: 条款分数阈值
            
        Returns:
            处理结果
        """
        try:
            # 1. 解析文档结构
            logger.info(f"开始解析文档结构: {doc_name}")
            # 从文档内容中解析出段落
            parsed_structure = self._parse_document_content(document_content)
            
            # 2. LLM标注
            logger.info("开始三管线LLM标注")
            labeled_segments = await self.llm_service.label_segments(parsed_structure.get("segments", []))
            
            # 3. 根据分数合并段落为条款单元
            logger.info(f"根据分数阈值 {score_threshold} 合并段落为条款单元")
            clause_units = self.llm_service.merge_segments_by_clause(labeled_segments, score_threshold)
            
            # 4. 准备向量摄入数据
            logger.info("准备向量摄入数据")
            ingest_items = self._prepare_ingest_items(
                clause_units,
                doc_id,
                doc_name,
                lang
            )
            
            # 5. 向量化和存储
            if ingest_items:
                logger.info(f"开始向量化和存储到集合 {collection_name}")
                ingest_request = VectorIngestRequest(
                    embedding_model=embedding_model,
                    items=ingest_items
                )
                
                ingest_result = await self.vector_service.ingest_items_to_collection(
                    collection_name,
                    ingest_request
                )
                
                # 返回处理结果
                return {
                    "success": True,
                    "message": "文档处理成功",
                    "doc_id": doc_id,
                    "steps": {
                        "labeling": {
                            "success": True,
                            "segments_count": len(labeled_segments),
                            "labeled_count": len(labeled_segments),
                            "clause_units_count": len(clause_units)
                        },
                        "vectorization": ingest_result
                    },
                    "data": {
                        "labeled_segments": labeled_segments,
                        "clause_units": clause_units,
                        "total_segments": len(labeled_segments),
                        "ingested": ingest_result.data.get("succeeded", 0),
                        "failed": ingest_result.data.get("failed", 0)
                    }
                }
            else:
                logger.warning("没有符合条件的条款单元可处理")
                return {
                    "success": True,
                    "message": f"没有分数大于等于 {score_threshold} 的条款单元",
                    "doc_id": doc_id,
                    "steps": {
                        "labeling": {
                            "success": True,
                            "segments_count": len(labeled_segments),
                            "labeled_count": len(labeled_segments),
                            "clause_units_count": 0
                        },
                        "vectorization": {"success": True, "message": "向量化跳过"}
                    },
                    "data": {
                        "labeled_segments": labeled_segments,
                        "clause_units": [],
                        "total_segments": len(labeled_segments),
                        "ingested": 0,
                        "failed": 0
                    }
                }
                
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            return {
                "success": False,
                "message": f"文档处理失败: {str(e)}",
                "doc_id": doc_id,
                "steps": {},
                "data": {}
            }
    
    def _prepare_ingest_items(
        self,
        clause_units: list[dict[str, any]],
        doc_id: str,
        doc_name: str,
        lang: str
    ) -> list[VectorIngestItem]:
        """
        准备向量摄入项
        
        Args:
            clause_units: 条款单元列表
            doc_id: 文档ID
            doc_name: 文档名称
            lang: 语言代码
            
        Returns:
            向量摄入项列表
        """
        ingest_items = []
        
        for i, unit in enumerate(clause_units):
            # 创建条款单元的摄入项
            clause_item = VectorIngestItem(
                unit_type="CLAUSE",
                doc_id=doc_id,
                doc_name=doc_name,
                clause_id=unit.get("id"),
                clause_title=unit.get("nc_type") == "TITLE" and unit.get("text", "")[:50] or None,
                clause_order_index=i,
                item_id=unit.get("id"),
                parent_item_id=None,
                item_order_index=0,
                lang=lang,
                role=unit.get("role", "NON_CLAUSE"),
                region=unit.get("region", "MAIN"),
                nc_type=unit.get("nc_type"),
                score=unit.get("score"),
                content=unit.get("text", ""),
                loc={
                    "segment_ids": unit.get("segment_ids", []),
                    "order_index": unit.get("order_index", 0)
                },
                biz_tags={
                    "score_float": unit.get("score_float", 0),
                    "segment_count": len(unit.get("segment_ids", []))
                }
            )
            
            ingest_items.append(clause_item)
        
        return ingest_items
    
    async def label_document_only(
        self,
        document_content: str,
        doc_id: str,
        doc_name: str,
        lang: str = "zh"
    ) -> dict[str, any]:
        """
        仅进行文档标注，不执行向量化和存储
        
        Args:
            document_content: 文档内容
            doc_id: 文档ID
            doc_name: 文档名称
            lang: 语言代码
            
        Returns:
            标注结果
        """
        try:
            # 1. 解析文档结构
            logger.info(f"开始解析文档结构: {doc_name}")
            # 从文档内容中解析出段落
            parsed_structure = self._parse_document_content(document_content)
            
            # 2. LLM标注
            logger.info("开始三管线LLM标注")
            labeled_segments = await self.llm_service.label_segments(parsed_structure.get("segments", []))
            
            # 3. 根据分数合并段落为条款单元
            logger.info("合并段落为条款单元")
            clause_units = self.llm_service.merge_segments_by_clause(labeled_segments)
            
            # 返回标注结果
            return {
                "success": True,
                "message": "文档标注成功",
                "doc_id": doc_id,
                "steps": {
                    "labeling": {
                        "success": True,
                        "segments_count": len(labeled_segments),
                        "labeled_count": len(labeled_segments),
                        "clause_units_count": len(clause_units)
                    }
                },
                "data": {
                    "labeled_segments": labeled_segments,
                    "clause_units": clause_units,
                    "total_segments": len(labeled_segments)
                }
            }
                
        except Exception as e:
            logger.error(f"文档标注失败: {str(e)}")
            return {
                "success": False,
                "message": f"文档标注失败: {str(e)}",
                "doc_id": doc_id,
                "steps": {},
                "data": {}
            }
    
    async def ingest_prepared_items(
        self,
        ingest_items: list[VectorIngestItem],
        embedding_model: str = "text-embedding-3-large",
        collection_name: str = "mirrors_clause_vectors"
    ) -> dict[str, any]:
        """
        向量化并存储预先准备好的条款项
        
        Args:
            ingest_items: 预先准备好的向量摄入项列表
            embedding_model: 嵌入模型名称
            collection_name: 向量集合名称
            
        Returns:
            向量摄入结果
        """
        try:
            if not ingest_items:
                return {
                    "success": True,
                    "message": "没有提供条款项",
                    "steps": {
                        "vectorization": {
                            "success": True,
                            "message": "向量化跳过"
                        }
                    },
                    "data": {}
                }
            
            logger.info(f"开始向量化和存储 {len(ingest_items)} 个条款项到集合 {collection_name}")
            ingest_request = VectorIngestRequest(
                embedding_model=embedding_model,
                items=ingest_items
            )
            
            ingest_result = await self.vector_service.ingest_items_to_collection(
                collection_name,
                ingest_request
            )
            
            return {
                "success": True,
                "message": "向量摄入完成",
                "steps": {
                    "vectorization": ingest_result
                },
                "data": ingest_result.data
            }
                
        except Exception as e:
            logger.error(f"向量摄入失败: {str(e)}")
            return {
                "success": False,
                "message": f"向量摄入失败: {str(e)}",
                "steps": {},
                "data": {}
            }
    
    # 向后兼容方法 - 保留旧API接口
    async def process_document_v1(
        self,
        doc_id: str,
        segments: list[dict[str, any]],
        metadata: dict[str, any],
        options: [dict[str, any]] = None
    ) -> dict[str, any]:
        """
        处理文档 (v1格式 - 从原始段落开始)
        向后兼容方法，转换为新的处理流程
        
        Args:
            doc_id: 文档ID
            segments: 文档段落列表
            metadata: 文档元数据
            options: 处理选项
            
        Returns:
            处理结果
        """
        try:
            options = options or {}
            doc_name = metadata.get("title", doc_id)
            embedding_model = options.get("embedding_model", "text-embedding-3-large")
            collection_name = options.get("collection_name", "mirrors_clause_vectors")
            lang = options.get("lang", "zh")
            score_threshold = options.get("score_threshold", "1")
            
            # 将段落转换为文档内容
            document_content = "\n\n".join([seg.get("text", "") for seg in segments])
            
            # 调用新的处理方法
            result = await self.process_document(
                document_content=document_content,
                doc_id=doc_id,
                doc_name=doc_name,
                embedding_model=embedding_model,
                collection_name=collection_name,
                lang=lang,
                score_threshold=score_threshold
            )
            
            return result
            
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            return {
                "success": False,
                "message": f"文档处理失败: {str(e)}",
                "doc_id": doc_id,
                "steps": {},
                "data": {}
            }
    
    async def process_document_v2(
        self,
        doc_id: str,
        structure_data: dict[str, any],
        metadata: dict[str, any],
        options: [dict[str, any]] = None
    ) -> dict[str, any]:
        """
        处理文档 (v2格式 - 从预结构化数据开始)
        向后兼容方法，转换为新的处理流程
        
        Args:
            doc_id: 文档ID
            structure_data: 文档结构数据
            metadata: 文档元数据
            options: 处理选项
            
        Returns:
            处理结果
        """
        try:
            options = options or {}
            doc_name = metadata.get("title", doc_id)
            embedding_model = options.get("embedding_model", "text-embedding-3-large")
            collection_name = options.get("collection_name", "mirrors_clause_vectors")
            lang = options.get("lang", "zh")
            score_threshold = options.get("score_threshold", "1")
            
            # 将结构化数据转换为文档内容
            document_content = self._convert_structure_to_text(structure_data)
            
            # 调用新的处理方法
            result = await self.process_document(
                document_content=document_content,
                doc_id=doc_id,
                doc_name=doc_name,
                embedding_model=embedding_model,
                collection_name=collection_name,
                lang=lang,
                score_threshold=score_threshold
            )
            
            return result
            
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            return {
                "success": False,
                "message": f"文档处理失败: {str(e)}",
                "doc_id": doc_id,
                "steps": {},
                "data": {}
            }
    
    def _convert_structure_to_text(self, structure_data: dict[str, any]) -> str:
        """
        将结构化数据转换为纯文本
        
        Args:
            structure_data: 结构化数据
            
        Returns:
            转换后的文本
        """
        text_parts = []
        
        # 处理sections
        for section in structure_data.get("sections", []):
            title = section.get("title", "")
            content = section.get("content", "")
            if title:
                text_parts.append(f"## {title}")
            if content:
                text_parts.append(content)
        
        # 处理clauses
        for clause in structure_data.get("clauses", []):
            title = clause.get("title", "")
            content = clause.get("content", "")
            if title:
                text_parts.append(f"### {title}")
            if content:
                text_parts.append(content)
        
        # 处理clause_items
        for item in structure_data.get("clause_items", []):
            content = item.get("content", "")
            if content:
                text_parts.append(f"- {content}")
        
        return "\n\n".join(text_parts)