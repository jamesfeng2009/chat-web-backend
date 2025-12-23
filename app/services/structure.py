import re
import json
import uuid
from typing import Any, Tuple

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.crud.section import crud_section
from app.crud.clause import crud_clause
from app.crud.clause_item import crud_clause_item
from app.crud.paragraph_span import crud_paragraph_span
from app.schemas.section import SectionCreate
from app.schemas.clause import ClauseCreate
from app.schemas.clause_item import ClauseItemCreate
from app.schemas.paragraph_span import ParagraphSpanCreate
from app.services.document import document_service
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class SegmentRole(Enum):
    """段落角色枚举"""
    CLAUSE = "CLAUSE"
    NON_CLAUSE = "NON_CLAUSE"


class SegmentRegion(Enum):
    """段落区域枚举"""
    COVER = "COVER"
    MAIN = "MAIN"
    APPENDIX = "APPENDIX"
    SIGN = "SIGN"


class SegmentNCType(Enum):
    """非条款类型枚举"""
    # COVER区
    COVER_TITLE = "COVER_TITLE"
    TOC = "TOC"
    COVER_META = "COVER_META"
    COVER_PARTIES = "COVER_PARTIES"
    COVER_OTHER = "COVER_OTHER"
    
    # MAIN区
    TITLE = "TITLE"
    CLAUSE_BODY = "CLAUSE_BODY"
    RECITAL = "RECITAL"
    MAIN_OTHER = "MAIN_OTHER"
    
    # APPENDIX区
    APPENDIX_TITLE = "APPENDIX_TITLE"
    APPENDIX_BODY = "APPENDIX_BODY"
    APPENDIX_OTHER = "APPENDIX_OTHER"
    
    # SIGN区
    SIGN_PAGE_TITLE = "SIGN_PAGE_TITLE"
    SIGN_PAGE_PARTY = "SIGN_PAGE_PARTY"
    SIGN_PAGE_BODY = "SIGN_PAGE_BODY"


@dataclass
class Segment:
    """文档段落数据结构"""
    seg_id: str
    doc_id: str
    order_index: int
    text: str
    block_type: str
    level: int
    page_num: int = 0
    bbox: Tuple[float, float, float, float] | None = None
    style: dict[str, Any] | None = None

    # LLM标注结果
    role: SegmentRole | None = None
    region: SegmentRegion | None = None
    nc_type: SegmentNCType | None = None
    clause_number: str | None = None
    boundary: str | None = None  # B/I/O标签

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "seg_id": self.seg_id,
            "doc_id": self.doc_id,
            "order_index": self.order_index,
            "text": self.text,
            "block_type": self.block_type,
            "level": self.level,
            "page_num": self.page_num,
            "bbox": self.bbox,
            "style": self.style or {},
            "role": self.role.value if self.role else None,
            "region": self.region.value if self.region else None,
            "nc_type": self.nc_type.value if self.nc_type else None,
            "clause_number": self.clause_number,
            "boundary": self.boundary
        }


class StructureService:
    """文档结构化服务"""
    
    def __init__(self):
        self.llm_service = None  # 可以初始化LLM服务
    
    def structure_document(
        self,
        db: Session,
        document_id: str,
        structure_type: str = "auto",
        options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        结构化文档
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            structure_type: 结构化类型
            options: 结构化选项
            
        Returns:
            结构化结果
        """
        try:
            # 获取文档信息
            document = document_service.get_document(db, document_id=document_id)
            if not document:
                raise ValueError(f"Document not found: {document_id}")
            
            # 检查文档解析状态
            if document.get("parse_status") != "completed":
                raise ValueError(f"Document not parsed: {document_id}")
            
            # 获取解析结果
            parse_result = self._get_parse_result(db, document_id)
            if not parse_result or not parse_result.get("blocks"):
                raise ValueError(f"No parse result found for document: {document_id}")
            
            # 创建段落
            segments = self._create_segments(document_id, parse_result["blocks"])
            
            # LLM标注
            if options and options.get("use_llm", True):
                segments = self._annotate_with_llm(segments)
            
            # 聚合标注结果
            segments = self._aggregate_annotations(segments)
            
            # 创建章节
            sections = self._create_sections(db, document_id, segments)
            
            # 创建条款
            clauses = self._create_clauses(db, document_id, segments, sections)
            
            # 创建子项
            clause_items = self._create_clause_items(db, clauses, segments)
            
            # 创建段落跨度
            paragraph_spans = self._create_paragraph_spans(db, clauses, clause_items, segments)
            
            # 构建结果
            result = {
                "document_id": document_id,
                "structure_type": structure_type,
                "options": options or {},
                "sections": sections,
                "clauses": clauses,
                "clause_items": clause_items,
                "paragraph_spans": paragraph_spans,
                "total_sections": len(sections),
                "total_clauses": len(clauses),
                "total_clause_items": len(clause_items),
                "total_paragraph_spans": len(paragraph_spans)
            }
            
            # 更新文档状态
            document_service.update_document_status(
                db=db,
                document_id=document_id,
                status="completed",
                structure_status="completed"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error structuring document: {e}")
            # 更新文档状态为失败
            document_service.update_document_status(
                db=db,
                document_id=document_id,
                status="failed",
                structure_status="failed"
            )
            raise
    
    def get_structure_result(self, db: Session, document_id: str) -> dict[str, Any] | None:
        """
        获取结构化结果
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            
        Returns:
            结构化结果或None
        """
        try:
            # 获取章节
            sections = crud_section.get_by_document_all(db, doc_id=document_id)
            
            # 获取条款
            clauses = crud_clause.get_by_document_all(db, doc_id=document_id)
            
            # 构建结果
            result = {
                "document_id": document_id,
                "sections": [section.__dict__ for section in sections],
                "clauses": [clause.__dict__ for clause in clauses],
                "total_sections": len(sections),
                "total_clauses": len(clauses)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting structure result: {e}")
            return None
    
    def get_document_sections(self, db: Session, document_id: str) -> list[dict[str, Any]]:
        """
        获取文档的章节列表
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            
        Returns:
            章节列表
        """
        try:
            sections = crud_section.get_by_document_all(db, doc_id=document_id)
            return [
                {
                    "id": section.id,
                    "title": section.title,
                    "level": section.level,
                    "order_index": section.order_index,
                    "role": section.role,
                    "region": section.region,
                    "nc_type": section.nc_type
                }
                for section in sections
            ]
        except Exception as e:
            logger.error(f"Error getting document sections: {e}")
            return []
    
    def get_document_clauses(
        self,
        db: Session,
        document_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> dict[str, Any]:
        """
        获取文档的条款列表
        
        Args:
            db: 数据库会话
            document_id: 文档ID
            skip: 跳过记录数
            limit: 返回记录数
            
        Returns:
            条款列表和总数
        """
        try:
            clauses = crud_clause.get_by_document(db, doc_id=document_id, skip=skip, limit=limit)
            total = len(crud_clause.get_by_document_all(db, doc_id=document_id))
            
            return {
                "items": [
                    {
                        "id": clause.id,
                        "section_id": clause.section_id,
                        "title": clause.title,
                        "content": clause.content,
                        "lang": clause.lang,
                        "order_index": clause.order_index,
                        "role": clause.role,
                        "region": clause.region,
                        "nc_type": clause.nc_type
                    }
                    for clause in clauses
                ],
                "total": total,
                "page": skip // limit + 1,
                "page_size": limit
            }
        except Exception as e:
            logger.error(f"Error getting document clauses: {e}")
            return {"items": [], "total": 0, "page": 1, "page_size": limit}
    
    def get_clause_detail(self, db: Session, clause_id: str) -> dict[str, Any] | None:
        """
        获取条款详情（包含子项）
        
        Args:
            db: 数据库会话
            clause_id: 条款ID
            
        Returns:
            条款详情或None
        """
        try:
            # 获取条款
            clause = crud_clause.get(db, id=clause_id)
            if not clause:
                return None
            
            # 获取子项
            items = crud_clause_item.get_by_clause_all(db, clause_id=clause_id)
            
            # 构建结果
            result = {
                "id": clause.id,
                "doc_id": clause.doc_id,
                "section_id": clause.section_id,
                "title": clause.title,
                "content": clause.content,
                "lang": clause.lang,
                "order_index": clause.order_index,
                "role": clause.role,
                "region": clause.region,
                "nc_type": clause.nc_type,
                "items": [
                    {
                        "id": item.id,
                        "parent_item_id": item.parent_item_id,
                        "title": item.title,
                        "content": item.content,
                        "lang": item.lang,
                        "order_index": item.order_index,
                        "role": item.role,
                        "region": item.region,
                        "nc_type": item.nc_type
                    }
                    for item in items
                ]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting clause detail: {e}")
            return None
    
    def _get_parse_result(self, db: Session, document_id: str) -> dict[str, Any] | None:
        """获取解析结果"""
        # 这里可以从数据库或文件系统中获取已保存的解析结果
        # 为了简化，这里返回None，实际实现中应该从解析结果存储中获取
        return None
    
    def _create_segments(self, document_id: str, blocks: list[dict[str, Any]]) -> list[Segment]:
        """创建段落"""
        segments = []
        
        for i, block in enumerate(blocks):
            segment = Segment(
                seg_id=f"seg_{uuid.uuid4().hex}",
                doc_id=document_id,
                order_index=i + 1,
                text=block.get("text", ""),
                block_type=block.get("block_type", "paragraph"),
                level=block.get("level", 1),
                page_num=block.get("page_num", 0),
                bbox=block.get("bbox"),
                style=block.get("style", {})
            )
            segments.append(segment)
        
        return segments
    
    def _annotate_with_llm(self, segments: list[Segment]) -> list[Segment]:
        """使用LLM标注段落"""
        # 这里应该调用LLM服务进行标注
        # 为了简化，这里只做基于规则的简单标注
        
        for segment in segments:
            # 检测区域
            segment.region = self._detect_region(segment)
            
            # 检测角色
            segment.role = self._detect_role(segment)
            
            # 检测非条款类型
            if segment.role == SegmentRole.NON_CLAUSE:
                segment.nc_type = self._detect_nc_type(segment)
            
            # 检测条款编号
            if segment.role == SegmentRole.CLAUSE:
                segment.clause_number = self._extract_clause_number(segment.text)
            
            # 检测边界
            segment.boundary = self._detect_boundary(segment)
        
        return segments
    
    def _aggregate_annotations(self, segments: list[Segment]) -> list[Segment]:
        """聚合标注结果"""
        # 这里可以对LLM标注结果进行投票或仲裁
        # 为了简化，这里不做处理
        return segments
    
    def _detect_region(self, segment: Segment) -> SegmentRegion:
        """检测段落区域"""
        text = segment.text
        
        # 封面/抬头检测
        if re.search(r'合同|协议|章程|规定|办法', text) and segment.order_index <= 5:
            return SegmentRegion.COVER
        
        # 签名页检测
        if re.search(r'甲方|乙方|签字|盖章|日期|签署', text):
            return SegmentRegion.SIGN
        
        # 附件检测
        if re.search(r'附件|附录|附表|补充', text):
            return SegmentRegion.APPENDIX
        
        # 默认为主体内容
        return SegmentRegion.MAIN
    
    def _detect_role(self, segment: Segment) -> SegmentRole:
        """检测段落角色"""
        text = segment.text
        block_type = segment.block_type
        
        # 标题通常是章节
        if block_type == "heading":
            return SegmentRole.NON_CLAUSE
        
        # 目录
        if re.search(r'目录|目次|contents|table\s+of\s+contents', text, re.I):
            return SegmentRole.NON_CLAUSE
        
        # 条款检测
        if re.search(r'^第[一二三四五六七八九十\d]+[条]', text):
            return SegmentRole.CLAUSE
        
        # 段落通常是条款内容
        if block_type == "paragraph" and segment.region == SegmentRegion.MAIN:
            return SegmentRole.CLAUSE
        
        return SegmentRole.NON_CLAUSE
    
    def _detect_nc_type(self, segment: Segment) -> SegmentNCType:
        """检测非条款类型"""
        text = segment.text
        region = segment.region
        
        if region == SegmentRegion.COVER:
            if re.search(r'合同|协议|章程|规定|办法', text):
                return SegmentNCType.COVER_TITLE
            elif re.search(r'目录|目次', text, re.I):
                return SegmentNCType.TOC
            elif re.search(r'编号|版本|日期', text):
                return SegmentNCType.COVER_META
            elif re.search(r'甲方|乙方', text):
                return SegmentNCType.COVER_PARTIES
            else:
                return SegmentNCType.COVER_OTHER
        
        elif region == SegmentRegion.MAIN:
            if segment.block_type == "heading":
                return SegmentNCType.TITLE
            elif re.search(r'鉴于|鉴于条款|前言', text):
                return SegmentNCType.RECITAL
            else:
                return SegmentNCType.MAIN_OTHER
        
        elif region == SegmentRegion.APPENDIX:
            if segment.block_type == "heading":
                return SegmentNCType.APPENDIX_TITLE
            elif segment.block_type == "paragraph":
                return SegmentNCType.APPENDIX_BODY
            else:
                return SegmentNCType.APPENDIX_OTHER
        
        elif region == SegmentRegion.SIGN:
            if re.search(r'签字页|签署页', text):
                return SegmentNCType.SIGN_PAGE_TITLE
            elif re.search(r'甲方|乙方', text):
                return SegmentNCType.SIGN_PAGE_PARTY
            else:
                return SegmentNCType.SIGN_PAGE_BODY
        
        return SegmentNCType.MAIN_OTHER
    
    def _extract_clause_number(self, text: str) -> str | None:
        """提取条款编号"""
        match = re.search(r'第([一二三四五六七八九十\d]+)[条]', text)
        if match:
            return match.group(1)
        return None
    
    def _detect_boundary(self, segment: Segment) -> str | None:
        """检测边界标签"""
        if segment.role == SegmentRole.CLAUSE and segment.clause_number:
            return "B"  # Begin
        elif segment.role == SegmentRole.CLAUSE and not segment.clause_number:
            return "I"  # Inside
        else:
            return "O"  # Outside
    
    def _create_sections(self, db: Session, document_id: str, segments: list[Segment]) -> list[dict[str, Any]]:
        """创建章节"""
        sections = []
        
        # 找出所有章节标题
        section_segments = [s for s in segments if s.role == SegmentRole.NON_CLAUSE and s.block_type == "heading"]
        
        for segment in section_segments:
            # 创建章节
            section_data = SectionCreate(
                doc_id=document_id,
                title=segment.text,
                level=segment.level,
                order_index=segment.order_index,
                loc={
                    "page_num": segment.page_num,
                    "bbox": segment.bbox,
                    "style": segment.style
                },
                role=segment.role.value if segment.role else "NON_CLAUSE",
                region=segment.region.value if segment.region else "MAIN",
                nc_type=segment.nc_type.value if segment.nc_type else None
            )
            
            section = crud_section.create(db, obj_in=section_data)
            sections.append(section.__dict__)
        
        return sections
    
    def _create_clauses(self, db: Session, document_id: str, segments: list[Segment], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """创建条款"""
        clauses = []
        
        # 找出所有条款段落
        clause_segments = [s for s in segments if s.role == SegmentRole.CLAUSE]
        
        # 按条款编号分组
        clause_groups = {}
        for segment in clause_segments:
            clause_number = segment.clause_number or "unknown"
            if clause_number not in clause_groups:
                clause_groups[clause_number] = []
            clause_groups[clause_number].append(segment)
        
        # 为每个条款组创建条款
        for clause_number, group_segments in clause_groups.items():
            if not group_segments:
                continue
            
            # 按顺序排序
            group_segments.sort(key=lambda s: s.order_index)
            
            # 提取标题和内容
            title = ""
            content = ""
            
            for segment in group_segments:
                if segment.clause_number and not title:
                    title = segment.text
                else:
                    content += segment.text + "\n"
            
            content = content.strip()
            
            # 查找所属章节
            section_id = None
            first_segment = group_segments[0]
            
            # 找到最近的章节
            for section in sections:
                if section.get("order_index") < first_segment.order_index:
                    if not section_id or section.get("order_index") > section_id:
                        section_id = section.get("id")
            
            # 创建条款
            clause_data = ClauseCreate(
                doc_id=document_id,
                section_id=section_id,
                title=title,
                content=content,
                lang=first_segment.style.get("lang", "zh"),
                order_index=first_segment.order_index,
                loc={
                    "page_nums": list(set(s.page_num for s in group_segments)),
                    "segments": [s.seg_id for s in group_segments]
                },
                role=SegmentRole.CLAUSE.value,
                region=first_segment.region.value if first_segment.region else "MAIN",
                nc_type=SegmentNCType.CLAUSE_BODY.value
            )
            
            clause = crud_clause.create(db, obj_in=clause_data)
            clauses.append(clause.__dict__)
        
        return clauses
    
    def _create_clause_items(self, db: Session, clauses: list[dict[str, Any]], segments: list[Segment]) -> list[dict[str, Any]]:
        """创建子项"""
        clause_items = []
        
        # 找出所有子项段落
        item_segments = [s for s in segments if re.search(r'^[（\(][一二三四五六七八九十\d]+[）\)]|^[\d]+\.[\s]', s.text)]
        
        # 简单实现：根据顺序将子项分配给最近的条款
        for segment in item_segments:
            # 找到最近的条款
            nearest_clause = None
            min_distance = float('inf')
            
            for clause in clauses:
                distance = abs(clause.get("order_index", 0) - segment.order_index)
                if distance < min_distance:
                    min_distance = distance
                    nearest_clause = clause
            
            # 提取子项标题
            title_match = re.search(r'^([（\(][一二三四五六七八九十\d]+[）\)]|[\d]+\.[\s])', segment.text)
            title = title_match.group(1) if title_match else ""
            
            # 提取内容
            content = segment.text[len(title):].strip()
            
            # 创建子项
            if not nearest_clause:
                continue
            
            item_data = ClauseItemCreate(
                clause_id=nearest_clause.get("id"),
                title=title,
                content=content,
                lang=segment.style.get("lang", "zh"),
                order_index=segment.order_index,
                loc={
                    "page_num": segment.page_num,
                    "bbox": segment.bbox,
                    "style": segment.style
                },
                role=SegmentRole.CLAUSE.value,
                region=segment.region.value if segment.region else "MAIN",
                nc_type=SegmentNCType.CLAUSE_BODY.value
            )
            
            item = crud_clause_item.create(db, obj_in=item_data)
            clause_items.append(item.__dict__)
        
        return clause_items
    
    def _create_paragraph_spans(self, db: Session, clauses: list[dict[str, Any]], clause_items: list[dict[str, Any]], segments: list[Segment]) -> list[dict[str, Any]]:
        """创建段落跨度"""
        paragraph_spans = []
        
        # 为每个段落创建跨度
        for segment in segments:
            # 确定所有者类型和ID
            owner_type = "Clause"
            owner_id = None
            
            # 查找对应的条款或子项
            if segment.role == SegmentRole.CLAUSE:
                # 找到最近的条款
                for clause in clauses:
                    if abs(clause.get("order_index", 0) - segment.order_index) < 5:
                        owner_id = clause.get("id")
                        break
            elif re.search(r'^[（\(][一二三四五六七八九十\d]+[）\)]|^[\d]+\.[\s]', segment.text):
                # 查找对应的子项
                owner_type = "ClauseItem"
                for item in clause_items:
                    if abs(item.get("order_index", 0) - segment.order_index) < 2:
                        owner_id = item.get("id")
                        break
            
            if not owner_id:
                continue
            
            # 创建段落跨度
            span_data = ParagraphSpanCreate(
                owner_type=owner_type,
                owner_id=owner_id,
                seq=segment.order_index,
                raw_text=segment.text,
                style=segment.style,
                loc={
                    "page_num": segment.page_num,
                    "bbox": segment.bbox
                },
                role=segment.role.value if segment.role else "NON_CLAUSE",
                region=segment.region.value if segment.region else "MAIN",
                nc_type=segment.nc_type.value if segment.nc_type else None
            )
            
            span = crud_paragraph_span.create(db, obj_in=span_data)
            paragraph_spans.append(span.__dict__)
        
        return paragraph_spans


# 全局结构化服务实例
structure_service = StructureService()