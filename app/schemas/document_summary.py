"""
文档摘要相关 Schema 定义
"""
from typing import Any
from pydantic import BaseModel, Field


class TimelineSummaryRequest(BaseModel):
    """时间线摘要请求"""
    doc_ids: list[str] = Field(..., description="文档ID列表")


class RAGSummaryRequest(BaseModel):
    """RAG摘要请求"""
    query: str = Field(..., description="用户查询/问题")
    doc_ids: list[str] = Field(..., description="文档ID列表")
    collection_name: str | None = Field(None, description="向量集合名称")
    top_k: int | None = Field(10, description="检索返回数量")


class GlobalSummaryRequest(BaseModel):
    """全局概要请求"""
    doc_ids: list[str] = Field(..., description="文档ID列表")
    build_knowledge_graph: bool | None = Field(False, description="是否构建知识图谱关系")


class TimelineEvent(BaseModel):
    """时间线事件"""
    date: str = Field(..., description="标准化日期")
    event: str = Field(..., description="事件描述")
    context: str | None = Field(None, description="原文上下文")
    # 引用源定位字段
    doc_id: str | None = Field(None, description="文档ID")
    clause_id: str | None = Field(None, description="条款ID")
    block_id: str | None = Field(None, description="前端锚点ID")


class SummarySource(BaseModel):
    """摘要来源"""
    doc_id: str | None = Field(None, description="文档ID")
    doc_name: str | None = Field(None, description="文档名称")
    title: str | None = Field(None, description="条款标题")
    score: float | None = Field(None, description="相似度得分")
    # 引用源定位字段
    clause_id: str | None = Field(None, description="条款ID，可用于定位到具体条款")
    item_id: str | None = Field(None, description="子项ID，如果来源是子项")
    span_ids: list[str] = Field(default_factory=list, description="段落ID列表，包含该条款的所有段落")
    block_id: str | None = Field(None, description="前端锚点ID（如 p-12），由 clause_id 映射生成")
    loc: dict[str, Any] | None = Field(None, description="详细位置信息：字符区间、页段、样式线索")
    page: int | None = Field(None, description="页码（如果文档是PDF）")


class DocumentSummaryItem(BaseModel):
    """文档摘要项"""
    doc_id: str = Field(..., description="文档ID")
    doc_name: str = Field(..., description="文档名称")
    doc_type: str | None = Field(None, description="文档类型")
    summary: str = Field(..., description="文档摘要")
    key_points: list[str] = Field(default_factory=list, description="关键点列表")
    # 引用源定位字段
    block_ids: list[str] = Field(default_factory=list, description="该文档摘要引用的前端锚点ID列表")


class Entity(BaseModel):
    """实体"""
    name: str = Field(..., description="实体名称")
    type: str = Field(..., description="实体类型: PERSON|ORG|LOCATION|DATE|MONEY|OTHER")
    count: int = Field(..., description="出现次数")


class KnowledgeGraph(BaseModel):
    """知识图谱"""
    nodes: list[dict[str, Any]] = Field(default_factory=list, description="节点列表")
    edges: list[dict[str, Any]] = Field(default_factory=list, description="边列表")


class GlobalSummaryContent(BaseModel):
    """全局概要内容"""
    overview: str = Field(..., description="整体概览")
    common_points: list[str] = Field(default_factory=list, description="共同点")
    differences: list[str] = Field(default_factory=list, description="差异点")


class TimelineSummaryResponse(BaseModel):
    """时间线摘要响应"""
    success: bool
    doc_count: int = Field(..., description="文档数量")
    events_count: int = Field(..., description="事件数量")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="时间线")


class RAGSummaryResponse(BaseModel):
    """RAG摘要响应"""
    success: bool
    query: str = Field(..., description="查询问题")
    summary: str = Field(..., description="摘要内容")
    sources: list[SummarySource] = Field(default_factory=list, description="来源列表")
    source_count: int = Field(..., description="来源数量")


class GlobalSummaryResponse(BaseModel):
    """全局概要响应"""
    success: bool
    doc_count: int = Field(..., description="文档数量")
    document_summaries: list[DocumentSummaryItem] = Field(default_factory=list, description="各文档摘要")
    entities: list[Entity] = Field(default_factory=list, description="实体列表")
    global_summary: GlobalSummaryContent = Field(..., description="全局概要")
    knowledge_graph: KnowledgeGraph | None = Field(None, description="知识图谱")


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    message: str = Field(..., description="错误信息")
