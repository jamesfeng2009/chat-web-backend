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
from app.services.clause_chunking import clause_chunking_service
from app.services.parser import parser_service
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
    
    def process_with_clause_chunking(self, content: bytes, file_type: str, doc_id: str, doc_name: str, 
                                 mode: str = "contract", use_cross_encoder: bool = False,
                                 embedding_model: str = "text-embedding-3-large",
                                 collection_name: str = "mirrors_clause_vectors",
                                 lang: str = "zh") -> dict[str, any]:
        """
        使用条款切分算法处理文档
        
        Args:
            content: 文档内容字节数组
            file_type: 文件类型
            doc_id: 文档ID
            doc_name: 文档名称
            mode: 切分模式 - "contract"(合同模式), "summary"(汇总模式), "single"(单条款模式)
            use_cross_encoder: 是否使用交叉编码器
            embedding_model: 嵌入模型
            collection_name: 向量集合名称
            lang: 语言代码
            
        Returns:
            处理结果
        """
        try:
            # 1. 解析文档
            logger.info(f"开始解析文档: {doc_name}")
            text_blocks = parser_service.parse(content, file_type)
            
            # 转换为Block结构
            from app.services.clause_chunking import Block
            blocks = [Block.from_text_block(block) for block in text_blocks if block.text.strip()]
            
            if not blocks:
                logger.warning("没有有效的文本块可处理")
                return {
                    "success": False,
                    "message": "文档中没有有效的文本内容",
                    "doc_id": doc_id,
                    "steps": {},
                    "data": {}
                }
            
            # 2. 执行条款切分
            logger.info(f"使用模式 {mode} 执行条款切分")
            chunk_result = clause_chunking_service.chunk_blocks(
                blocks, mode=mode, use_cross_encoder=use_cross_encoder
            )
            
            # 3. 将切分结果转换为Segment对象
            logger.info("将切分结果转换为段落对象")
            segments = []
            for i, span in enumerate(chunk_result["spans"]):
                # 合并span中的文本
                text = "\n".join([blocks[j].text for j in span])
                
                # 获取第一个块的页面信息
                first_block = blocks[span[0]]
                
                # 创建段落对象
                segment = {
                    "id": f"{doc_id}_chunk_{i}",
                    "text": text,
                    "order_index": i,
                    "block_type": "clause_chunk",
                    "level": 0,
                    "page_num": first_block.page_num,
                    "bbox": first_block.bbox,
                    "role": None,  # 后续由LLM标注
                    "region": None,
                    "nc_type": None,
                    "segment_ids": span,
                    "score": 1.0  # 默认分数
                }
                segments.append(segment)
            
            # 4. LLM标注
            logger.info("开始三管线LLM标注")
            labeled_segments = await self.llm_service.label_segments(segments)
            
            # 5. 准备向量摄入数据
            logger.info("准备向量摄入数据")
            ingest_items = self._prepare_ingest_items_from_chunks(
                labeled_segments, chunk_result["spans"], chunk_result["texts"],
                doc_id, doc_name, lang
            )
            
            # 6. 向量化和存储
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
                    "message": "使用条款切分处理文档成功",
                    "doc_id": doc_id,
                    "steps": {
                        "chunking": {
                            "success": True,
                            "chunks_count": len(chunk_result["spans"]),
                            "mode": mode,
                            "use_cross_encoder": use_cross_encoder
                        },
                        "labeling": {
                            "success": True,
                            "segments_count": len(segments),
                            "labeled_count": len(labeled_segments)
                        },
                        "vectorization": ingest_result
                    },
                    "data": {
                        "chunks": chunk_result,
                        "segments": segments,
                        "labeled_segments": labeled_segments,
                        "total_chunks": len(chunk_result["spans"]),
                        "ingested": ingest_result.data.get("succeeded", 0),
                        "failed": ingest_result.data.get("failed", 0)
                    }
                }
            else:
                logger.warning("没有符合条件的条款单元可处理")
                return {
                    "success": True,
                    "message": "条款切分完成，但没有生成可向量化的条款单元",
                    "doc_id": doc_id,
                    "steps": {
                        "chunking": {
                            "success": True,
                            "chunks_count": len(chunk_result["spans"]),
                            "mode": mode,
                            "use_cross_encoder": use_cross_encoder
                        },
                        "labeling": {
                            "success": True,
                            "segments_count": len(segments),
                            "labeled_count": len(labeled_segments)
                        },
                        "vectorization": {"success": True, "message": "向量化跳过"}
                    },
                    "data": {
                        "chunks": chunk_result,
                        "segments": segments,
                        "labeled_segments": labeled_segments,
                        "total_chunks": len(chunk_result["spans"]),
                        "ingested": 0,
                        "failed": 0
                    }
                }
                
        except Exception as e:
            logger.error(f"使用条款切分处理文档失败: {str(e)}")
            return {
                "success": False,
                "message": f"条款切分处理文档失败: {str(e)}",
                "doc_id": doc_id,
                "steps": {},
                "data": {}
            }
    
    def _prepare_ingest_items_from_chunks(
        self,
        labeled_segments: list[dict[str, any]],
        chunk_spans: list[list[int]],
        chunk_texts: list[str],
        doc_id: str,
        doc_name: str,
        lang: str
    ) -> list[VectorIngestItem]:
        """
        从切分后的段落准备向量摄入项
        
        Args:
            labeled_segments: 已标注的段落列表
            chunk_spans: 切分结果的spans
            chunk_texts: 切分结果的texts
            doc_id: 文档ID
            doc_name: 文档名称
            lang: 语言代码
            
        Returns:
            向量摄入项列表
        """
        ingest_items = []
        
        for i, (span, text, segment) in enumerate(zip(chunk_spans, chunk_texts, labeled_segments)):
            # 根据标注结果确定unit_type
            role = segment.get("role", "NON_CLAUSE")
            unit_type = "CLAUSE" if role == "CLAUSE" else "CLAUSE_ITEM"
            
            # 创建条款单元的摄入项
            clause_item = VectorIngestItem(
                unit_type=unit_type,
                doc_id=doc_id,
                doc_name=doc_name,
                clause_id=segment.get("id"),
                clause_title=None,  # 可以从segment中提取
                clause_order_index=i,
                item_id=segment.get("id"),
                parent_item_id=None,
                item_order_index=0,
                lang=lang,
                role=role,
                region=segment.get("region", "MAIN"),
                nc_type=segment.get("nc_type"),
                content=text,  # 使用切分后的文本
                loc={
                    "chunk_span": span,
                    "segment_ids": segment.get("segment_ids", span),
                    "order_index": i
                },
                biz_tags={
                    "score": segment.get("score", 1.0),
                    "block_count": len(span),
                    "chunking_method": "semantic_structure"
                }
            )
            
            ingest_items.append(clause_item)
        
        return ingest_items