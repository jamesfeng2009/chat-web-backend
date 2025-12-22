# 法务数据结构化系统使用指南

## 系统概述

本系统实现了法务数据的结构化处理，将原始合同与条款汇总文档统一切成章 → 条 → 子项 → 正文段的树结构，支持向量化、去重、回溯和检索。

## 核心功能

### 1. 文档路由和解析
- 支持多种文档格式：.docx/.pdf/.txt/.md/.html
- 支持通过URL下载文档或直接解析富文本内容
- 提取文档基本信息和元数据

### 2. 三管线标签系统
- **Region标签**：识别COVER/TOC/MAIN/APPENDIX/SIGN区域
- **NC_Type标签**：识别TITLE/PARTIES/CLAUSE_BODY/null类型
- **Role标签**：识别CLAUSE/NON_CLAUSE角色
- 通过加权评分机制计算置信度分数

### 3. 文档结构化
- 将文档结构化为section/clause/clause_item的层次结构
- 自动识别章节标题、条款编号和子项编号
- 构建层次化的父子关系

### 4. 向量化入库
- 对条款和子项内容进行向量化
- 存储到Milvus向量数据库
- 支持元数据和业务标签

### 5. 检索功能
- 语义搜索：基于向量相似度的搜索
- 混合搜索：结合语义和关键词的搜索
- 支持过滤和排序

## API接口

### 1. 文档处理接口

#### 解析文档
```bash
POST /api/v1/parse_document
```

请求体示例：
```json
{
  "id": "1",
  "title": "股东协议HX",
  "type": "参考文本",
  "created_at": "2025-11-23",
  "file_url": "http://124.70.2.199:7861/download/33f68f65-d567-451c-bef0-71980d1de4ba",
  "rich_content": "",
  "drafters": [
    {"name": "zhangshuo", "status": "activate"}
  ]
}
```

响应示例：
```json
{
  "success": true,
  "doc_id": "1",
  "message": "文档处理完成",
  "parse_result": {
    "parsed_segments": [...],
    "metadata": {...}
  },
  "labeled_segments_count": 100,
  "structured_data": {
    "sections_count": 5,
    "clauses_count": 20,
    "clause_items_count": 15
  },
  "vector_result": {
    "success": true,
    "total": 35,
    "succeeded": 35,
    "failed": 0
  }
}
```

#### 异步解析文档
```bash
POST /api/v1/parse_document_async
```

请求体与解析文档接口相同，但会异步处理。

#### 重新处理文档
```bash
POST /api/v1/reprocess_document/{doc_id}
```

#### 查询文档状态
```bash
GET /api/v1/document_status/{doc_id}
```

响应示例：
```json
{
  "success": true,
  "doc_id": "1",
  "status": "completed",
  "parse_status": "completed",
  "structure_status": "completed",
  "vector_status": "completed",
  "statistics": {
    "sections_count": 5,
    "clauses_count": 20,
    "clause_items_count": 15
  }
}
```

### 2. 搜索接口

#### 语义搜索
```bash
POST /api/v1/vector-search/semantic_search
```

请求体示例：
```json
{
  "query": "股权转让的限制条件",
  "collection_name": "mirrors_clause_vectors",
  "limit": 10,
  "filter_expr": "region == 'MAIN'",
  "output_fields": ["clause_id", "clause_title", "content"]
}
```

#### 混合搜索
```bash
POST /api/v1/vector-search/hybrid_search
```

请求体示例：
```json
{
  "query": "股权转让的限制条件",
  "keywords": ["转让", "限制", "股权"],
  "collection_name": "mirrors_clause_vectors",
  "limit": 10,
  "semantic_weight": 0.7,
  "keyword_weight": 0.3
}
```

#### 获取文档条款
```bash
GET /api/v1/vector-search/document/{doc_id}/clauses
```

#### 获取文档子项
```bash
GET /api/v1/vector-search/document/{doc_id}/clause_items
```

#### 获取特定条款
```bash
GET /api/v1/vector-search/clause/{clause_id}
```

## 系统架构

### 核心组件

1. **文档路由服务** (DocumentRoutingService)
   - 处理多种文档格式的解析
   - 支持URL下载和富文本解析

2. **标签服务** (LabelingService)
   - 实现三管线标签系统
   - 并行处理提高效率

3. **结构化服务** (DocumentStructureService)
   - 构建文档层次结构
   - 识别章节、条款和子项

4. **向量化服务** (VectorIngestionService)
   - 文本向量化
   - 向量数据库操作

5. **文档处理服务** (DocumentProcessorService)
   - 整合所有处理流程
   - 提供完整的文档处理接口

### 数据模型

1. **Document**: 文档元信息
   - id, name, type, created_at
   - file_url, rich_content, drafters

2. **Section**: 章节信息
   - parent_id, number_token, title
   - content, level_hint, order_index

3. **Clause**: 条款信息
   - parent_clause_id, section_id
   - number_token, title, content
   - role, region, nc_type, score

4. **ClauseItem**: 子项信息
   - clause_id, parent_item_id
   - number_token, title, content
   - role, region, nc_type, score

### 数据库设计

系统使用MySQL存储结构化数据，Milvus存储向量数据。

## 部署指南

### 环境要求

- Python 3.8+
- MySQL 8.0+
- Milvus 2.0+
- Redis 6.0+ (可选，用于缓存)

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

创建.env文件：
```bash
# 数据库配置
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/legal_db

# Milvus配置
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 其他配置
DEBUG=True
```

### 初始化数据库

```bash
alembic upgrade head
```

### 启动服务

```bash
# 使用uvicorn启动
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 或使用Docker
docker-compose up -d
```

## 测试

运行测试脚本：

```bash
python test_system.py
```

测试脚本将验证：
1. 文档处理流程
2. 向量搜索功能
3. 文档检索功能

## 性能优化

1. **并发处理**
   - 使用线程池并行处理三管线标注
   - 支持批量向量化

2. **缓存策略**
   - 缓存文档解析结果
   - 缓存向量计算结果

3. **数据库优化**
   - 为常用查询添加索引
   - 使用连接池管理数据库连接

## 常见问题

### Q: 如何添加新的文档格式支持？

A: 在DocumentRoutingService中添加新的解析方法，并更新文件类型检测逻辑。

### Q: 如何自定义标签规则？

A: 修改LabelingService中的提示词或规则逻辑，或替换为自定义的LLM服务。

### Q: 如何调整向量搜索参数？

A: 在VectorIngestionService中调整搜索参数，或通过API请求中的search_params字段传入。

### Q: 如何处理大文档？

A: 系统自动将大文档分割为窗口处理，可以通过调整窗口大小和重叠区域来优化处理效果。