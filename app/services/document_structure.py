"""
文档结构化服务
支持两种格式的文档解析：
1. v1: 将标注后的段落转换为section/clause/clause_item的层次结构
2. v2: 处理基于新数据结构的文档解析和结构化
"""
import re
import uuid
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.core.logger import logger
from app.schemas.document import DocumentCreate
from app.schemas.section import SectionCreate
from app.schemas.clause import ClauseCreate
from app.schemas.clause_item import ClauseItemCreate


@dataclass
class StructuredElement:
    """结构化元素的数据类"""
    id: str
    element_type: str  # section, clause, clause_item
    parent_id: str | None
    order_index: int
    number_token: str | None
    title: str | None
    content: str | None
    level_hint: int | None
    loc: dict[str, Any] | None
    role: str
    region: str
    nc_type: str | None
    score: int


class DocumentStructureService:
    """文档结构化服务 - 支持v1和v2两种格式"""
    
    def __init__(self):
        # 章节标题正则表达式
        self.section_patterns = [
            r'^第[一二三四五六七八九十\d]+章[：:\s]*(.+)',  # 第一章、第二章
            r'^第[一二三四五六七八九十\d]+节[：:\s]*(.+)',  # 第一节、第二节
            r'^第[一二三四五六七八九十\d]+部分[：:\s]*(.+)',  # 第一部分、第二部分
            r'^[一二三四五六七八九十\d]+[、，\.\s]+(.+)',  # 一、二、三、
            r'^[1-9]\d*[、\.\s]+(.+)',  # 1.、2.、3.
            r'^\([1-9]\d*\)[\s：:](.+)',  # (1)、(2)、(3)
            r'^[A-Z]\.[\s：:](.+)',  # A.、B.、C.
        ]
        
        # 条款编号正则表达式
        self.clause_patterns = [
            r'^第[一二三四五六七八九十\d]+条[：:\s]*(.+)',  # 第一条、第二条
            r'^[1-9]\d+\.[1-9]\d*(\.[1-9]\d*)?[、\.\s]+(.+)',  # 1.1、1.2.1
            r'^[1-9]\d+[\s、:：](.+)',  # 1、2、3
            r'^[1-9]\d+\.[1-9]\d*\s*(.+)',  # 1.1、2.3
        ]
        
        # 子项编号正则表达式
        self.item_patterns = [
            r'^[（\(][一二三四五六七八九十\d]+[）\)][\s：:：](.+)',  # （一）、（二）
            r'^\([1-9]\d*\)[\s：:：](.+)',  # (1)、(2)
            r'^[1-9]\d+\)[\s：:：](.+)',  # 1)、2)
            r'^[a-zA-Z]\)[\s：:：](.+)',  # a)、b)
            r'^[①②③④⑤⑥⑦⑧⑨⑩][\s：:：](.+)',  # ①、②
        ]
        
        # v2格式使用的计数器
        self.order_counter = 0
    
    # ===== V1 格式处理方法 =====
    
    def structure_document(self, doc_id: str, labeled_segments: list[dict[str, Any]]) -> dict[str, Any]:
        """
        v1格式: 将标注后的段落结构化为section/clause/clause_item层次结构
        
        Args:
            doc_id: 文档ID
            labeled_segments: 已标注的段落列表
            
        Returns:
            包含sections、clauses和clause_items的结构化数据
        """
        if not labeled_segments:
            return {
                "sections": [],
                "clauses": [],
                "clause_items": []
            }
        
        # 步骤1: 提取所有结构化元素
        elements = self._extract_structured_elements(doc_id, labeled_segments)
        
        # 步骤2: 构建section层次结构
        sections = self._build_section_hierarchy(elements)
        
        # 步骤3: 构建clause层次结构
        clauses = self._build_clause_hierarchy(elements, sections)
        
        # 步骤4: 构建clause_item层次结构
        clause_items = self._build_clause_item_hierarchy(elements, clauses)
        
        return {
            "sections": sections,
            "clauses": clauses,
            "clause_items": clause_items
        }
    
    def _extract_structured_elements(self, doc_id: str, labeled_segments: list[dict[str, Any]]) -> list[StructuredElement]:
        """从标注段落中提取结构化元素"""
        elements = []
        
        for segment in labeled_segments:
            text = segment["text"]
            element_id = str(uuid.uuid4())
            order_index = segment["id"]
            role = segment.get("role", "NON_CLAUSE")
            region = segment.get("region", "MAIN")
            nc_type = segment.get("nc_type")
            score = segment.get("score", 1)
            
            # 尝试识别section
            section_match = self._match_section(text)
            if section_match:
                elements.append(StructuredElement(
                    id=element_id,
                    element_type="section",
                    parent_id=None,  # 稍后确定
                    order_index=order_index,
                    number_token=section_match[0],
                    title=section_match[1],
                    content=text,
                    level_hint=section_match[2],
                    loc=self._extract_loc(segment),
                    role=role,
                    region=region,
                    nc_type=nc_type,
                    score=score
                ))
                continue
            
            # 尝试识别clause
            clause_match = self._match_clause(text)
            if clause_match and role == "CLAUSE":
                elements.append(StructuredElement(
                    id=element_id,
                    element_type="clause",
                    parent_id=None,  # 稍后确定
                    order_index=order_index,
                    number_token=clause_match[0],
                    title=clause_match[1],
                    content=text,
                    level_hint=clause_match[2],
                    loc=self._extract_loc(segment),
                    role=role,
                    region=region,
                    nc_type=nc_type,
                    score=score
                ))
                continue
            
            # 尝试识别clause_item
            item_match = self._match_item(text)
            if item_match and role == "CLAUSE":
                elements.append(StructuredElement(
                    id=element_id,
                    element_type="clause_item",
                    parent_id=None,  # 稍后确定
                    order_index=order_index,
                    number_token=item_match[0],
                    title=item_match[1] if item_match[1] else None,
                    content=text,
                    level_hint=item_match[2],
                    loc=self._extract_loc(segment),
                    role=role,
                    region=region,
                    nc_type=nc_type,
                    score=score
                ))
                continue
            
            # 不符合任何结构化元素，但可能是CLAUSE_BODY
            if role == "CLAUSE" and nc_type == "CLAUSE_BODY":
                elements.append(StructuredElement(
                    id=element_id,
                    element_type="clause",  # 作为无编号的条款
                    parent_id=None,  # 稍后确定
                    order_index=order_index,
                    number_token=None,
                    title=None,
                    content=text,
                    level_hint=0,
                    loc=self._extract_loc(segment),
                    role=role,
                    region=region,
                    nc_type=nc_type,
                    score=score
                ))
        
        return elements
    
    def _match_section(self, text: str) -> tuple[str, str, int] | None:
        """匹配章节标题"""
        for i, pattern in enumerate(self.section_patterns):
            match = re.match(pattern, text)
            if match:
                number_token = match.group(1) if len(match.groups()) > 0 else ""
                title = match.group(2) if len(match.groups()) > 1 else match.group(1)
                return (text.split('：', 1)[0].split(':', 1)[0], title, i+1)
        return None
    
    def _match_clause(self, text: str) -> tuple[str, str, int] | None:
        """匹配条款编号"""
        for i, pattern in enumerate(self.clause_patterns):
            match = re.match(pattern, text)
            if match:
                number_token = match.group(1) if len(match.groups()) > 0 else ""
                title = match.group(2) if len(match.groups()) > 1 else match.group(1)
                return (text.split('：', 1)[0].split(':', 1)[0], title, i+1)
        return None
    
    def _match_item(self, text: str) -> tuple[str, str | None, int] | None:
        """匹配子项编号"""
        for i, pattern in enumerate(self.item_patterns):
            match = re.match(pattern, text)
            if match:
                number_token = match.group(1) if len(match.groups()) > 0 else ""
                title = match.group(2) if len(match.groups()) > 1 else None
                return (text.split('：', 1)[0].split(':', 1)[0], title, i+1)
        return None
    
    def _extract_loc(self, segment: dict[str, Any]) -> dict[str, Any]:
        """从段落中提取位置信息"""
        loc = segment.get("loc", {})
        if not loc:
            loc = {}
        return loc
    
    def _build_section_hierarchy(self, elements: list[StructuredElement]) -> list[SectionCreate]:
        """构建章节层次结构"""
        # 提取所有section元素
        sections = [e for e in elements if e.element_type == "section"]
        
        # 按order_index排序
        sections.sort(key=lambda x: x.order_index)
        
        # 构建层次结构
        section_dicts = []
        for section in sections:
            section_dicts.append({
                "id": section.id,
                "parent_id": None,
                "order_index": section.order_index,
                "level_hint": section.level_hint,
                "number_token": section.number_token,
                "title": section.title,
                "content": section.content
            })
        
        # 确定父子关系
        self._determine_parent_relationships(section_dicts)
        
        # 转换为SectionCreate对象
        result = []
        for section_dict in section_dicts:
            result.append(SectionCreate(
                id=section_dict["id"],
                parent_id=section_dict["parent_id"],
                order_index=section_dict["order_index"],
                level=section_dict["level_hint"],
                number_token=section_dict["number_token"],
                title=section_dict["title"],
                content=section_dict["content"]
            ))
        
        return result
    
    def _build_clause_hierarchy(self, elements: list[StructuredElement], sections: list[SectionCreate]) -> list[ClauseCreate]:
        """构建条款层次结构"""
        # 提取所有clause元素
        clauses = [e for e in elements if e.element_type == "clause"]
        
        # 按order_index排序
        clauses.sort(key=lambda x: x.order_index)
        
        # 确定每个clause所属的section
        section_map = {s.id: s for s in sections}
        clause_dicts = []
        
        for clause in clauses:
            # 查找最近的section
            section_id = self._find_closest_section(clause.order_index, sections)
            
            clause_dicts.append({
                "id": clause.id,
                "parent_clause_id": None,  # 稍后确定
                "section_id": section_id,
                "order_index": clause.order_index,
                "number_token": clause.number_token,
                "title": clause.title,
                "content": clause.content,
                "lang": "zh",  # 默认中文
                "loc": clause.loc,
                "role": clause.role,
                "region": clause.region,
                "nc_type": clause.nc_type,
                "score": clause.score
            })
        
        # 确定条款之间的父子关系
        self._determine_clause_parent_relationships(clause_dicts)
        
        # 转换为ClauseCreate对象
        result = []
        for clause_dict in clause_dicts:
            result.append(ClauseCreate(
                id=clause_dict["id"],
                parent_clause_id=clause_dict["parent_clause_id"],
                section_id=clause_dict["section_id"],
                order_index=clause_dict["order_index"],
                number_token=clause_dict["number_token"],
                title=clause_dict["title"],
                content=clause_dict["content"],
                lang=clause_dict["lang"],
                loc=clause_dict["loc"],
                role=clause_dict["role"],
                region=clause_dict["region"],
                nc_type=clause_dict["nc_type"],
                score=clause_dict["score"]
            ))
        
        return result
    
    def _build_clause_item_hierarchy(self, elements: list[StructuredElement], clauses: list[ClauseCreate]) -> list[ClauseItemCreate]:
        """构建条款子项层次结构"""
        # 提取所有clause_item元素
        items = [e for e in elements if e.element_type == "clause_item"]
        
        # 按order_index排序
        items.sort(key=lambda x: x.order_index)
        
        # 确定每个item所属的clause
        clause_map = {c.id: c for c in clauses}
        item_dicts = []
        
        for item in items:
            # 查找最近的clause
            clause_id = self._find_closest_clause(item.order_index, clauses)
            
            if clause_id:
                item_dicts.append({
                    "id": item.id,
                    "clause_id": clause_id,
                    "parent_item_id": None,  # 稍后确定
                    "order_index": item.order_index,
                    "number_token": item.number_token,
                    "title": item.title,
                    "content": item.content,
                    "lang": "zh",  # 默认中文
                    "loc": item.loc,
                    "role": item.role,
                    "region": item.region,
                    "nc_type": item.nc_type,
                    "score": item.score
                })
        
        # 确定item之间的父子关系
        self._determine_item_parent_relationships(item_dicts)
        
        # 转换为ClauseItemCreate对象
        result = []
        for item_dict in item_dicts:
            result.append(ClauseItemCreate(
                id=item_dict["id"],
                clause_id=item_dict["clause_id"],
                parent_item_id=item_dict["parent_item_id"],
                order_index=item_dict["order_index"],
                number_token=item_dict["number_token"],
                title=item_dict["title"],
                content=item_dict["content"],
                lang=item_dict["lang"],
                loc=item_dict["loc"],
                role=item_dict["role"],
                region=item_dict["region"],
                nc_type=item_dict["nc_type"],
                score=item_dict["score"]
            ))
        
        return result
    
    def _determine_parent_relationships(self, sections: list[dict[str, Any]]):
        """确定章节之间的父子关系"""
        for i, section in enumerate(sections):
            level_hint = section["level_hint"]
            
            # 查找最近的父级section
            parent_id = None
            for j in range(i-1, -1, -1):
                if sections[j]["level_hint"] < level_hint:
                    parent_id = sections[j]["id"]
                    break
            
            section["parent_id"] = parent_id
    
    def _determine_clause_parent_relationships(self, clauses: list[dict[str, Any]]):
        """确定条款之间的父子关系"""
        for i, clause in enumerate(clauses):
            # 查找最近的父级clause
            parent_clause_id = None
            for j in range(i-1, -1, -1):
                if self._is_parent_clause(clauses[j], clause):
                    parent_clause_id = clauses[j]["id"]
                    break
            
            clause["parent_clause_id"] = parent_clause_id
    
    def _determine_item_parent_relationships(self, items: list[dict[str, Any]]):
        """确定条款子项之间的父子关系"""
        for i, item in enumerate(items):
            # 查找最近的父级item
            parent_item_id = None
            for j in range(i-1, -1, -1):
                if self._is_parent_item(items[j], item):
                    parent_item_id = items[j]["id"]
                    break
            
            item["parent_item_id"] = parent_item_id
    
    # ===== V2 格式处理方法 =====
    
    def parse_document_structure(self, doc_id: str, structure_data: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        """
        v2格式: 解析文档结构数据
        
        Args:
            doc_id: 文档ID
            structure_data: 文档结构数据
            metadata: 文档元数据
            
        Returns:
            包含sections、clauses和clause_items的结构化数据
        """
        self.order_counter = 0  # 重置计数器
        
        # 递归解析结构
        sections = []
        clauses = []
        clause_items = []
        
        # 处理根节点
        self._parse_structure_node(
            doc_id=doc_id,
            node=structure_data,
            parent_id=None,
            sections=sections,
            clauses=clauses,
            clause_items=clause_items,
            level=1,
            metadata=metadata
        )
        
        return {
            "sections": sections,
            "clauses": clauses,
            "clause_items": clause_items
        }
    
    def _parse_structure_node(
        self,
        doc_id: str,
        node: dict[str, Any],
        parent_id: str | None,
        sections: list[SectionCreate],
        clauses: list[ClauseCreate],
        clause_items: list[ClauseItemCreate],
        level: int,
        metadata: dict[str, Any]
    ):
        """
        递归解析结构节点
        
        Args:
            doc_id: 文档ID
            node: 当前节点数据
            parent_id: 父节点ID
            sections: 章节列表
            clauses: 条款列表
            clause_items: 条款子项列表
            level: 当前层级
            metadata: 文档元数据
        """
        # 获取节点信息
        node_id = node.get("id", str(uuid.uuid4()))
        node_level = node.get("level", 1)
        page = node.get("page", 1)
        
        title = node.get("title", "")
        title_tags = node.get("title_tags", {})
        content = node.get("content", "")
        content_tags = node.get("content_tags", {})
        children = node.get("children", [])
        
        # 确定节点类型
        node_type = self._determine_node_type(title, content, title_tags, content_tags)
        
        # 根据节点类型创建相应的对象
        if node_type == "section":
            # 创建章节
            section = self._create_section(
                doc_id=doc_id,
                node_id=node_id,
                parent_id=parent_id,
                level=level,
                title=title,
                content=title,  # 章节内容为标题
                title_tags=title_tags,
                page=page
            )
            sections.append(section)
            
            # 递归处理子节点
            for child in children:
                self._parse_structure_node(
                    doc_id=doc_id,
                    node=child,
                    parent_id=node_id,
                    sections=sections,
                    clauses=clauses,
                    clause_items=clause_items,
                    level=level + 1,
                    metadata=metadata
                )
                
        elif node_type == "clause":
            # 创建条款
            clause = self._create_clause(
                doc_id=doc_id,
                node_id=node_id,
                parent_id=parent_id,
                section_id=None,  # 需要在后续步骤中确定
                title=title,
                content=content,
                tags=content_tags,
                page=page
            )
            clauses.append(clause)
            
            # 处理子节点，通常是clause_item
            for child in children:
                self._parse_structure_node(
                    doc_id=doc_id,
                    node=child,
                    parent_id=node_id,
                    sections=sections,
                    clauses=clauses,
                    clause_items=clause_items,
                    level=level + 1,
                    metadata=metadata
                )
                
        elif node_type == "clause_item":
            # 创建条款子项
            item = self._create_clause_item(
                doc_id=doc_id,
                node_id=node_id,
                parent_id=parent_id,
                clause_id=None,  # 需要在后续步骤中确定
                content=content,
                tags=content_tags,
                page=page
            )
            clause_items.append(item)
            
            # 通常clause_item不会有子节点，但如果有则继续处理
            for child in children:
                self._parse_structure_node(
                    doc_id=doc_id,
                    node=child,
                    parent_id=node_id,
                    sections=sections,
                    clauses=clauses,
                    clause_items=clause_items,
                    level=level + 1,
                    metadata=metadata
                )
    
    def _determine_node_type(self, title: str, content: str, title_tags: dict[str, Any], content_tags: dict[str, Any]) -> str:
        """
        根据标题、内容和标签确定节点类型
        
        Args:
            title: 标题
            content: 内容
            title_tags: 标题标签
            content_tags: 内容标签
            
        Returns:
            节点类型: section/clause/clause_item
        """
        # 检查标签
        content_role = content_tags.get("role", "NON_CLAUSE")
        content_region = content_tags.get("region", "MAIN")
        
        # 如果有标题，通常是section或clause
        if title:
            # 如果有章节标识，认为是section
            if self._is_section_title(title):
                return "section"
            
            # 如果是条款，认为是clause
            if self._is_clause_title(title) or content_role == "CLAUSE":
                return "clause"
        
        # 如果只有内容，可能是clause或clause_item
        if content:
            # 检查是否是子项
            if self._is_clause_item(content) or (content_role == "CLAUSE" and content_region == "MAIN"):
                return "clause_item"
            
            # 其他情况认为是clause
            if content_role == "CLAUSE":
                return "clause"
        
        # 默认作为section处理
        return "section"
    
    def _is_section_title(self, title: str) -> bool:
        """判断是否是章节标题"""
        # 章节标题模式
        section_patterns = [
            r'第[一二三四五六七八九十\d]+章',
            r'第[一二三四五六七八九十\d]+节',
            r'第[一二三四五六七八九十\d]+部分',
        ]
        
        for pattern in section_patterns:
            if re.search(pattern, title):
                return True
        
        return False
    
    def _is_clause_title(self, title: str) -> bool:
        """判断是否是条款标题"""
        # 条款标题模式
        clause_patterns = [
            r'第[一二三四五六七八九十\d]+条',
            r'^\d+[\.\s]',
            r'^\d+\.\d+',
        ]
        
        for pattern in clause_patterns:
            if re.search(pattern, title):
                return True
        
        return False
    
    def _is_clause_item(self, content: str) -> bool:
        """判断是否是条款子项"""
        # 子项模式
        item_patterns = [
            r'^[（\(][一二三四五六七八九十\d]+[）\)]',
            r'^\(\d+\)',
            r'^\d+\)',
            r'^[a-zA-Z]\)',
            r'^[①②③④⑤⑥⑦⑧⑨⑩]',
        ]
        
        for pattern in item_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _create_section(
        self,
        doc_id: str,
        node_id: str,
        parent_id: str | None,
        level: int,
        title: str,
        content: str,
        title_tags: dict[str, Any],
        page: int
    ) -> SectionCreate:
        """创建章节对象"""
        self.order_counter += 1
        
        # 提取编号和标题
        number_token, title_text = self._extract_number_and_title(title)
        
        # 获取标签
        role = title_tags.get("role", "NON_CLAUSE")
        region = title_tags.get("region", "MAIN")
        nc_type = title_tags.get("nc_type")
        
        return SectionCreate(
            id=node_id,
            parent_id=parent_id,
            order_index=self.order_counter,
            level=level,
            number_token=number_token,
            title=title_text,
            content=content,
            loc={"page": page}  # 简化的位置信息
        )
    
    def _create_clause(
        self,
        doc_id: str,
        node_id: str,
        parent_id: str | None,
        section_id: str | None,
        title: str,
        content: str,
        tags: dict[str, Any],
        page: int
    ) -> ClauseCreate:
        """创建条款对象"""
        self.order_counter += 1
        
        # 提取编号和标题
        number_token, title_text = self._extract_number_and_title(title)
        
        # 获取标签
        role = tags.get("role", "CLAUSE")
        region = tags.get("region", "MAIN")
        nc_type = tags.get("nc_type", "CLAUSE_BODY")
        score = tags.get("score", 2)
        
        return ClauseCreate(
            id=node_id,
            parent_clause_id=parent_id,  # 如果父节点也是clause
            section_id=section_id,  # 将在后续步骤中设置
            order_index=self.order_counter,
            number_token=number_token,
            title=title_text,
            content=content,
            lang="zh",  # 默认中文
            loc={"page": page},  # 简化的位置信息
            role=role,
            region=region,
            nc_type=nc_type,
            score=score
        )
    
    def _create_clause_item(
        self,
        doc_id: str,
        node_id: str,
        parent_id: str | None,
        clause_id: str | None,
        content: str,
        tags: dict[str, Any],
        page: int
    ) -> ClauseItemCreate:
        """创建条款子项对象"""
        self.order_counter += 1
        
        # 提取编号和标题
        number_token, title_text = self._extract_number_and_title(content)
        
        # 获取标签
        role = tags.get("role", "CLAUSE")
        region = tags.get("region", "MAIN")
        nc_type = tags.get("nc_type", "CLAUSE_BODY")
        score = tags.get("score", 2)
        
        return ClauseItemCreate(
            id=node_id,
            clause_id=clause_id,  # 将在后续步骤中设置
            parent_item_id=parent_id,  # 如果父节点也是item
            order_index=self.order_counter,
            number_token=number_token,
            title=title_text,
            content=content,
            lang="zh",  # 默认中文
            loc={"page": page},  # 简化的位置信息
            role=role,
            region=region,
            nc_type=nc_type,
            score=score
        )
    
    def _extract_number_and_title(self, text: str) -> tuple[str | None, str]:
        """
        从文本中提取编号和标题
        
        Args:
            text: 原始文本
            
        Returns:
            (编号, 标题) 的元组
        """
        # 尝试匹配编号模式
        patterns = [
            r'^(第[一二三四五六七八九十\d]+[章节条款部分])[：:\s]*(.+)',
            r'^([（\(][一二三四五六七八九十\d]+[）\)])[\s：:：]*(.+)',
            r'^(\(\d+\))[\s：:：]*(.+)',
            r'^(\d+\))[\s：:：]*(.+)',
            r'^([a-zA-Z]\))[\s：:：]*(.+)',
            r'^([①②③④⑤⑥⑦⑧⑨⑩])[\s：:：]*(.+)',
            r'^(\d+)[\.\s]+(.+)',
            r'^(\d+\.\d+)[\.\s]+(.+)',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text)
            if match:
                number_token = match.group(1)
                title = match.group(2) if len(match.groups()) > 1 else ""
                return number_token, title
        
        # 如果没有匹配到编号模式，整个文本作为标题
        return None, text
    
    # ===== 共同方法 =====
    
    def establish_relationships(
        self,
        sections: list[SectionCreate],
        clauses: list[ClauseCreate],
        clause_items: list[ClauseItemCreate]
    ) -> tuple[list[SectionCreate], list[ClauseCreate], list[ClauseItemCreate]]:
        """
        建立章节、条款和子项之间的关系
        
        Args:
            sections: 章节列表
            clauses: 条款列表
            clause_items: 条款子项列表
            
        Returns:
            更新后的章节、条款和子项列表
        """
        # 1. 确定每个clause所属的section
        for clause in clauses:
            if clause.section_id is None:
                clause.section_id = self._find_closest_section(clause.order_index, sections)
        
        # 2. 确定每个clause_item所属的clause
        for item in clause_items:
            if item.clause_id is None:
                item.clause_id = self._find_closest_clause(item.order_index, clauses)
        
        # 3. 确定clause之间的父子关系
        clauses = self._establish_clause_relationships(clauses)
        
        # 4. 确定clause_item之间的父子关系
        clause_items = self._establish_item_relationships(clause_items)
        
        return sections, clauses, clause_items
    
    def _find_closest_section(self, order_index: int, sections: list[SectionCreate]) -> str | None:
        """找到给定order_index最近的section"""
        closest_section = None
        closest_distance = float('inf')
        
        for section in sections:
            if section.order_index < order_index:
                distance = order_index - section.order_index
                if distance < closest_distance:
                    closest_distance = distance
                    closest_section = section
        
        return closest_section.id if closest_section else None
    
    def _find_closest_clause(self, order_index: int, clauses: list[ClauseCreate]) -> str | None:
        """找到给定order_index最近的clause"""
        closest_clause = None
        closest_distance = float('inf')
        
        for clause in clauses:
            if clause.order_index < order_index:
                distance = order_index - clause.order_index
                if distance < closest_distance:
                    closest_distance = distance
                    closest_clause = clause
        
        return closest_clause.id if closest_clause else None
    
    def _establish_clause_relationships(self, clauses: list[ClauseCreate]) -> list[ClauseCreate]:
        """建立条款之间的父子关系"""
        # 按order_index排序
        clauses.sort(key=lambda x: x.order_index)
        
        for i, clause in enumerate(clauses):
            # 查找最近的父级clause
            parent_clause_id = None
            for j in range(i-1, -1, -1):
                if self._is_parent_clause(clauses[j], clause):
                    parent_clause_id = clauses[j].id
                    break
            
            clause.parent_clause_id = parent_clause_id
        
        return clauses
    
    def _establish_item_relationships(self, items: list[ClauseItemCreate]) -> list[ClauseItemCreate]:
        """建立条款子项之间的父子关系"""
        # 按order_index排序
        items.sort(key=lambda x: x.order_index)
        
        for i, item in enumerate(items):
            # 查找最近的父级item
            parent_item_id = None
            for j in range(i-1, -1, -1):
                if self._is_parent_item(items[j], item):
                    parent_item_id = items[j].id
                    break
            
            item.parent_item_id = parent_item_id
        
        return items
    
    def _is_parent_clause(self, potential_parent: dict[str, Any], child: dict[str, Any]) -> bool:
        """判断一个条款是否是另一个条款的父级"""
        parent_number = potential_parent.get("number_token")
        child_number = child.get("number_token")
        if not parent_number or not child_number:
            return False
        
        # 简单的基于编号层级判断
        parent_parts = re.findall(r'\d+', parent_number)
        child_parts = re.findall(r'\d+', child_number)
        
        if len(parent_parts) >= len(child_parts):
            return False
        
        # 检查父级编号是否是子级编号的前缀
        for i, part in enumerate(parent_parts):
            if part != child_parts[i]:
                return False
        
        return True
    
    def _is_parent_item(self, potential_parent: dict[str, Any], child: dict[str, Any]) -> bool:
        """判断一个子项是否是另一个子项的父级"""
        parent_number = potential_parent.get("number_token")
        child_number = child.get("number_token")
        if not parent_number or not child_number:
            return False
        
        # 简单的基于编号层级判断
        # 例如：（一）是 1) 的父级
        parent_is_paren = "（" in parent_number or "(" in parent_number
        child_is_digit = bool(re.match(r'^\d+\)', child_number))
        
        if parent_is_paren and child_is_digit:
            return True
        
        # (1) 是 a) 的父级
        parent_is_digit = bool(re.match(r'^\(\d+\)', parent_number))
        child_is_letter = bool(re.match(r'^[a-zA-Z]\)', child_number))
        
        if parent_is_digit and child_is_letter:
            return True
        
        return False


# 为了向后兼容，创建一个别名
DocumentStructureV2Service = DocumentStructureService