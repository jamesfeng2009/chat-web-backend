"""
文档摘要服务
实现时间线摘要、自定义摘要（RAG）、全局概要三种摘要模式
"""
import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

import openai
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.config import settings
from app.crud.clause import crud_clause
from app.crud.document import crud_document
from app.crud.clause_item import crud_clause_item
from app.crud.paragraph_span import crud_paragraph_span
from app.services.search import search_service

logger = get_logger(__name__)


class DocumentSummaryService:
    """文档摘要服务"""

    def __init__(self):
        # OpenAI 客户端
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # 默认模型
        self.summary_model = "gpt-4"
        self.embedding_model = settings.EMBEDDING_MODEL

    # ==================== 辅助方法 ====================

    async def _get_location_info(
        self,
        db: Session,
        clause_id: str,
        item_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取位置信息，用于引用源定位

        Args:
            db: 数据库会话
            clause_id: 条款ID
            item_id: 子项ID（可选）

        Returns:
            位置信息字典，包含 clause_id, item_id, span_ids, block_id, loc, page 等
        """
        location_info = {
            "clause_id": clause_id,
            "item_id": item_id,
            "span_ids": [],
            "block_id": None,
            "loc": None,
            "page": None
        }

        try:
            # 获取条款信息
            clause = crud_clause.get(db, id=clause_id)
            if clause:
                # 获取 loc 信息
                if clause.loc:
                    location_info["loc"] = clause.loc
                    # 尝试从 loc 中提取页码
                    if isinstance(clause.loc, dict):
                        location_info["page"] = clause.loc.get("page")

                # 获取关联的段落
                if item_id:
                    # 如果是子项，获取子项的段落
                    spans = crud_paragraph_span.get_by_clause_item_all(db, item_id=item_id)
                else:
                    # 获取条款的段落
                    spans = crud_paragraph_span.get_by_clause_all(db, clause_id=clause_id)

                # 收集 span_ids
                location_info["span_ids"] = [span.id for span in spans]

                # 生成 block_id
                # block_id 规则：基于 clause_id 生成，如 "block-{clause_id}-{index}"
                # 如果有多个段落，使用第一个段落的 seq 作为 index
                if spans:
                    location_info["block_id"] = f"block-{clause_id}-{spans[0].seq}"
                else:
                    location_info["block_id"] = f"block-{clause_id}"

        except Exception as e:
            logger.error(f"获取位置信息失败 (clause_id={clause_id}): {e}")

        return location_info

    # ==================== 时间线摘要 ====================

    async def timeline_summary(
        self,
        doc_ids: List[str],
        db: Session
    ) -> Dict[str, Any]:
        """
        时间线摘要：抽取时间 → 规范化 → 排序 → 润色

        Args:
            doc_ids: 文档ID列表
            db: 数据库会话

        Returns:
            时间线摘要结果
        """
        try:
            # 1. 获取文档内容
            documents = []
            for doc_id in doc_ids:
                doc = crud_document.get(db, id=doc_id)
                if doc:
                    documents.append(doc)

            if not documents:
                return {
                    "success": False,
                    "message": "未找到指定文档"
                }

            # 2. 获取所有条款内容
            all_text = []
            for doc in documents:
                clauses = crud_clause.get_by_doc_id(db, doc_id=doc.id)
                for clause in clauses:
                    if clause.content:
                        all_text.append(clause.content)

            full_text = "\n\n".join(all_text)

            # 3. 抽取时间信息
            logger.info(f"开始抽取时间信息，文档数量: {len(documents)}")
            time_extractions = await self._extract_timelines(full_text, db, doc_ids)

            # 4. 规范化和排序
            logger.info(f"规范化时间信息，事件数量: {len(time_extractions)}")
            normalized_events = await self._normalize_and_sort_events(time_extractions)

            # 5. 润色输出
            logger.info("润色时间线输出")
            polished_timeline = await self._polish_timeline(normalized_events)

            return {
                "success": True,
                "doc_count": len(documents),
                "events_count": len(polished_timeline),
                "timeline": polished_timeline
            }

        except Exception as e:
            logger.error(f"时间线摘要失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"时间线摘要失败: {str(e)}"
            }

    async def _extract_timelines(
        self,
        text: str,
        db: Session,
        doc_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        抽取时间信息

        Args:
            text: 要分析的文本
            db: 数据库会话
            doc_ids: 文档ID列表，用于获取位置信息
        """
        # 1. 正则规则抽取（中文日期格式）
        date_patterns = [
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', 'ymd'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'dash'),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', 'slash'),
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', 'dot'),
            (r'(\d{1,2})月(\d{1,2})日', 'md'),
        ]

        events = []
        for pattern, pattern_type in date_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]

                events.append({
                    "raw_date": match.group(),
                    "context": context,
                    "position": match.start()
                })

        # 2. 为事件添加位置信息
        # 根据文本位置查找对应的条款
        for doc_id in doc_ids:
            clauses = crud_clause.get_by_doc_id(db, doc_id=doc_id)
            for event in events:
                position = event.get("position", 0)

                # 查找包含该位置文本的条款
                # 这里使用简化的匹配方式：匹配 context
                event_context = event.get("context", "")
                for clause in clauses:
                    if clause.content and event_context in clause.content:
                        event["doc_id"] = doc_id
                        event["clause_id"] = clause.id

                        # 获取详细位置信息
                        location_info = await self._get_location_info(db, clause.id)
                        event["block_id"] = location_info.get("block_id")
                        break

        # 3. LLM 辅助抽取和标注
        if events:
            # 限制文本长度
            llm_text = text[:10000]
            llm_extracted = await self._llm_extract_dates(llm_text, db, doc_ids)
            events.extend(llm_extracted)

        return events

    async def _llm_extract_dates(
        self,
        text: str,
        db: Session,
        doc_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        使用 LLM 抽取日期

        Args:
            text: 要分析的文本
            db: 数据库会话
            doc_ids: 文档ID列表，用于获取位置信息
        """
        prompt = f"""从以下文本中提取所有日期和时间相关的事件，返回JSON格式：

{text}

请返回格式：
{{
    "events": [
        {{"date": "标准化日期（YYYY-MM-DD）", "event": "事件描述", "context": "原文上下文"}}
    ]
}}

只提取明确提到的日期事件，不要推测。
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            events = result.get("events", [])

            # 为 LLM 抽取的事件添加位置信息
            for doc_id in doc_ids:
                clauses = crud_clause.get_by_doc_id(db, doc_id=doc_id)
                for event in events:
                    event_context = event.get("context", "")
                    for clause in clauses:
                        if clause.content and event_context in clause.content:
                            event["doc_id"] = doc_id
                            event["clause_id"] = clause.id

                            # 获取详细位置信息
                            location_info = await self._get_location_info(db, clause.id)
                            event["block_id"] = location_info.get("block_id")
                            break

            return events
        except Exception as e:
            logger.error(f"LLM 日期抽取失败: {e}")
            return []

    async def _normalize_and_sort_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """规范化和排序事件"""
        if not events:
            return []

        # 保留位置信息映射
        events_position_map = {
            idx: {
                "doc_id": e.get("doc_id"),
                "clause_id": e.get("clause_id"),
                "block_id": e.get("block_id")
            }
            for idx, e in enumerate(events)
        }

        # 限制事件数量，避免 token 过多
        events_for_llm = events[:50]

        events_text = "\n".join([
            f"- {e.get('raw_date', '')}: {e.get('context', '')[:100]}"
            for e in events_for_llm
        ])

        prompt = f"""请将以下日期和时间事件规范化为统一的格式（YYYY-MM-DD），并按时间排序。如果没有具体日期，使用相近时间或保持原样。

{events_text}

返回JSON格式：
{{
    "normalized_events": [
        {{"date": "2024-01-01", "event": "事件描述", "original": "原始文本"}}
    ]
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            normalized_events = result.get("normalized_events", [])

            # 将位置信息附加到规范化后的事件
            for idx, event in enumerate(normalized_events):
                if idx < len(events_position_map):
                    position_info = events_position_map[idx]
                    event["doc_id"] = position_info.get("doc_id")
                    event["clause_id"] = position_info.get("clause_id")
                    event["block_id"] = position_info.get("block_id")

            return normalized_events
        except Exception as e:
            logger.error(f"规范化事件失败: {e}")
            # 返回原始事件
            return [
                {
                    "date": e.get("raw_date", ""),
                    "event": e.get("context", "")[:50],
                    "original": e.get("raw_date", ""),
                    "doc_id": e.get("doc_id"),
                    "clause_id": e.get("clause_id"),
                    "block_id": e.get("block_id")
                }
                for e in events[:20]
            ]

    async def _polish_timeline(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """润色时间线输出"""
        if not events:
            return []

        # 保留位置信息映射
        events_position_map = {
            idx: {
                "doc_id": e.get("doc_id"),
                "clause_id": e.get("clause_id"),
                "block_id": e.get("block_id")
            }
            for idx, e in enumerate(events)
        }

        events_text = "\n".join([
            f"{e['date']}: {e['event']}"
            for e in events[:30]
        ])

        prompt = f"""请润色以下时间线，使其更清晰、连贯、简洁。保持时间顺序不变。

{events_text}

返回JSON格式：
{{
    "timeline": [
        {{"date": "日期", "event": "润色后的事件描述"}}
    ]
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            polished_timeline = result.get("timeline", [])

            # 将位置信息附加到润色后的事件
            for idx, event in enumerate(polished_timeline):
                if idx < len(events_position_map):
                    position_info = events_position_map[idx]
                    event["doc_id"] = position_info.get("doc_id")
                    event["clause_id"] = position_info.get("clause_id")
                    event["block_id"] = position_info.get("block_id")

            return polished_timeline
        except Exception as e:
            logger.error(f"润色时间线失败: {e}")
            return events[:20]

    # ==================== RAG 摘要 ====================

    async def rag_summary(
        self,
        query: str,
        doc_ids: List[str],
        db: Session,
        collection_name: str = "mirrors_clause_vectors",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        自定义摘要（RAG 技术）：根据查询检索相关内容，生成摘要

        Args:
            query: 用户查询/问题
            doc_ids: 文档ID列表
            db: 数据库会话
            collection_name: 向量集合名称
            top_k: 检索返回数量

        Returns:
            RAG 摘要结果
        """
        try:
            logger.info(f"执行 RAG 摘要，查询: {query}")

            # 1. 使用检索服务搜索相关内容
            search_result = search_service.semantic_search(
                collection=collection_name,
                query=query,
                limit=top_k,
                filters={"doc_id": doc_ids} if len(doc_ids) == 1 else None
            )

            # 2. 提取相关内容
            relevant_items = search_result.get("items", [])
            logger.info(f"检索到 {len(relevant_items)} 个相关片段")

            if not relevant_items:
                return {
                    "success": False,
                    "message": "未找到相关内容"
                }

            # 3. 构建检索上下文，并收集位置信息
            context_parts = []
            source_locations = []  # 存储位置信息

            for item in relevant_items[:10]:
                title = item.get("title", "未知")
                content = item.get("content", "")
                context_parts.append(f"【{title}】{content}")

                # 获取位置信息
                clause_id = item.get("clause_id")
                item_id = item.get("item_id")
                if clause_id:
                    location_info = await self._get_location_info(db, clause_id, item_id)
                    source_locations.append({
                        "doc_id": item.get("doc_id"),
                        "doc_name": item.get("doc_name"),
                        "title": title,
                        "score": item.get("score"),
                        **location_info
                    })

            context = "\n\n".join(context_parts[:20])  # 限制上下文长度

            # 4. 生成摘要（基于检索内容）
            summary_prompt = f"""根据以下检索到的文档片段，准确回答用户的问题。只使用提供的信息，不要编造。

问题：{query}

检索到的相关内容：
{context}

要求：
1. 直接回答问题
2. 如果信息不足，说明需要更多信息
3. 引用相关来源
4. 保持简洁、准确
"""

            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0
            )

            summary = response.choices[0].message.content

            return {
                "success": True,
                "query": query,
                "summary": summary,
                "sources": source_locations,
                "source_count": len(source_locations)
            }

        except Exception as e:
            logger.error(f"RAG 摘要失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"RAG 摘要失败: {str(e)}"
            }

    # ==================== 全局概要 ====================

    async def global_summary(
        self,
        doc_ids: List[str],
        db: Session,
        build_knowledge_graph: bool = False
    ) -> Dict[str, Any]:
        """
        全局概要：支持跨文档，先文档内部概要，再多文档汇总

        Args:
            doc_ids: 文档ID列表
            db: 数据库会话
            build_knowledge_graph: 是否构建知识图谱关系

        Returns:
            全局概要结果
        """
        try:
            logger.info(f"开始全局概要，文档数量: {len(doc_ids)}")

            # 1. 对每个文档生成内部概要
            doc_summaries = []
            for doc_id in doc_ids:
                doc_summary = await self._generate_document_summary(doc_id, db)
                if doc_summary:
                    doc_summaries.append(doc_summary)

            if not doc_summaries:
                return {
                    "success": False,
                    "message": "无法生成文档摘要"
                }

            # 2. 抽取实体
            logger.info("抽取实体信息")
            entities = await self._extract_entities_from_docs(doc_summaries)

            # 3. 多文档汇总
            logger.info("生成多文档全局概要")
            multi_doc_summary = await self._generate_multi_doc_summary(doc_summaries, entities)

            # 4. 可选：构建知识图谱
            knowledge_graph = None
            if build_knowledge_graph and len(doc_ids) > 1:
                logger.info("构建知识图谱")
                knowledge_graph = await self._build_knowledge_graph(entities, doc_summaries)

            return {
                "success": True,
                "doc_count": len(doc_summaries),
                "document_summaries": doc_summaries,
                "entities": entities,
                "global_summary": multi_doc_summary,
                "knowledge_graph": knowledge_graph
            }

        except Exception as e:
            logger.error(f"全局概要失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"全局概要失败: {str(e)}"
            }

    async def _generate_document_summary(self, doc_id: str, db: Session) -> Optional[Dict[str, Any]]:
        """
        生成单个文档的内部概要

        Args:
            doc_id: 文档ID
            db: 数据库会话

        Returns:
            文档摘要（包含位置信息）
        """
        try:
            # 获取文档
            doc = crud_document.get(db, id=doc_id)
            if not doc:
                return None

            # 获取所有条款
            clauses = crud_clause.get_by_doc_id(db, doc_id=doc.id)

            if not clauses:
                return {
                    "doc_id": doc_id,
                    "doc_name": doc.name,
                    "doc_type": doc.type,
                    "summary": "文档内容为空或无法解析",
                    "key_points": [],
                    "block_ids": []
                }

            # 将条款内容拼接
            text_parts = []
            for clause in clauses:
                if clause.content and clause.content.strip():
                    title = clause.title or "无标题"
                    text_parts.append(f"【{title}】{clause.content}")

            full_text = "\n\n".join(text_parts)

            # 限制文本长度
            text_for_summary = full_text[:15000]

            # 生成文档摘要
            summary = await self._generate_single_document_summary(text_for_summary, doc.name)

            # 提取关键点
            key_points = await self._extract_key_points(summary)

            # 为每个条款生成 block_id
            block_ids = []
            for clause in clauses[:10]:  # 限制数量
                location_info = await self._get_location_info(db, clause.id)
                if location_info.get("block_id"):
                    block_ids.append(location_info["block_id"])

            return {
                "doc_id": doc_id,
                "doc_name": doc.name,
                "doc_type": doc.type,
                "summary": summary,
                "key_points": key_points,
                "block_ids": block_ids  # 添加 block_id 列表
            }

        except Exception as e:
            logger.error(f"生成文档摘要失败 ({doc_id}): {e}")
            return None

    async def _generate_single_document_summary(self, text: str, doc_name: str) -> str:
        """生成单个文档的摘要"""
        prompt = f"""请为以下文档内容生成简洁的摘要（300字以内），抓住核心内容和要点：

文档名称：{doc_name}

文档内容：
{text}

要求：
1. 摘要简洁、准确
2. 突出核心条款和要点
3. 使用专业语言
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"生成文档摘要失败: {e}")
            return f"文档《{doc_name}》的摘要生成失败"

    async def _extract_key_points(self, summary: str) -> List[str]:
        """从摘要中提取关键点"""
        prompt = f"""从以下摘要中提取 3-5 个关键点，返回 JSON 格式：

{summary}

返回格式：
{{
    "key_points": ["关键点1", "关键点2", "关键点3"]
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("key_points", [])
        except Exception as e:
            logger.error(f"提取关键点失败: {e}")
            return []

    async def _extract_entities_from_docs(self, doc_summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从文档摘要中抽取实体"""
        # 合并摘要文本
        all_summaries = "\n\n".join([
            f"文档: {s['doc_name']}\n摘要: {s['summary']}"
            for s in doc_summaries[:10]
        ])

        prompt = f"""从以下文档摘要中抽取重要实体（人名、机构、地点、日期、金额等），并标注实体类型：

{all_summaries}

返回 JSON 格式：
{{
    "entities": [
        {{"name": "实体名称", "type": "PERSON|ORG|LOCATION|DATE|MONEY|OTHER", "count": 出现次数}}
    ]
}}

只提取重要实体，不要过多。
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("entities", [])
        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return []

    async def _generate_multi_doc_summary(
        self,
        doc_summaries: List[Dict[str, Any]],
        entities: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """生成多文档汇总"""
        # 重点关注有实体的内容，但也要确保无实体的内容不丢失
        summaries_text = "\n\n".join([
            f"【{s['doc_name']}】{s['summary']}"
            for s in doc_summaries[:8]
        ])

        entities_text = "\n".join([
            f"- {e['name']} ({e['type']})"
            for e in entities[:20]
        ])

        prompt = f"""根据以下多个文档的摘要，生成全局概要：

文档摘要：
{summaries_text}

重要实体：
{entities_text}

要求：
1. 重点关注实体相关的内容
2. 不要忽略没有明确提及实体的内容
3. 提供整体概览、共同点、差异点
4. 返回 JSON 格式

返回格式：
{{
    "overview": "整体概览（200字以内）",
    "common_points": ["共同点1", "共同点2"],
    "differences": ["差异点1", "差异点2"]
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            logger.error(f"生成多文档汇总失败: {e}")
            return {
                "overview": summaries_text[:500],
                "common_points": [],
                "differences": []
            }

    async def _build_knowledge_graph(
        self,
        entities: List[Dict[str, Any]],
        doc_summaries: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict]]:
        """构建知识图谱关系"""
        summaries_text = "\n\n".join([
            f"文档: {s['doc_name']}\n摘要: {s['summary']}"
            for s in doc_summaries[:5]
        ])

        entities_text = "\n".join([
            f"- {e['name']} ({e['type']})"
            for e in entities[:15]
        ])

        prompt = f"""根据以下实体和文档摘要，识别实体之间的关系，构建简单的关系图。

实体：
{entities_text}

文档摘要：
{summaries_text}

返回 JSON 格式：
{{
    "nodes": [
        {{"id": "实体ID（如：entity1, entity2）", "label": "实体名称", "type": "实体类型"}}
    ],
    "edges": [
        {{"source": "源实体ID", "target": "目标实体ID", "label": "关系类型（如：关联、属于、涉及）", "doc_id": "来源文档ID"}}
    ]
}}

只识别明显的关系，不要过度推断。
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.summary_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            logger.error(f"构建知识图谱失败: {e}")
            return {"nodes": [], "edges": []}


# 全局服务实例
document_summary_service = DocumentSummaryService()
