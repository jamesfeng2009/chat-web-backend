# LLM集成与向量集合管理功能总结

## 概述

本系统已成功集成了大语言模型(LLM)标注功能和向量集合管理功能，支持完整的文档处理流程：

1. **文档解析 + 规范化** → 生成 blocks
2. **文档级预处理** → 切分为 segments
3. **条款切分 + LLM标注** → 滑动窗口打包、LLM标注、结果汇总
4. **条款记录建模 + 轻量父子** → 筛选CLAUSE段落、合并为条款单元
5. **Embedding计算 + 向量库索引** → 构建embedding文本、计算向量、写入向量库

## 新增功能

### 1. LLM标注服务 (`app/services/llm_labeling.py`)

实现了基于LLM的文档段落标注功能：

- **滑动窗口处理**：支持自定义窗口大小和重叠，提高标注一致性
- **多标签标注**：
  - `role`: CLAUSE / NON_CLAUSE
  - `nc_type`: 内容类型（COVER_TITLE, TOC, CLAUSE_BODY等）
  - `boundary`: 条款边界（B/I/E/S/O）
  - `clause_number`: 条款编号
- **多窗口结果合并**：投票/仲裁机制，确保标注准确性
- **段落合并**：根据clause_number和boundary标签合并为条款单元

### 2. 向量集合管理服务 (`app/services/vector_collection.py`)

提供了完整的Milvus向量集合管理功能：

- **集合创建**：支持自定义名称、维度和选项
- **集合列表**：查询所有集合信息
- **集合删除**：安全删除指定集合
- **集合详情**：获取集合详细信息和统计数据

### 3. 向量集合管理API (`app/api/v1/endpoints/vector_collections.py`)

实现了RESTful API接口：

- `POST /api/v1/vector_collections/` - 创建新集合
- `GET /api/v1/vector_collections/` - 列出所有集合
- `GET /api/v1/vector_collections/{collection_name}` - 获取集合详情
- `DELETE /api/v1/vector_collections/{collection_name}` - 删除集合

### 4. 文档处理服务 (`app/services/document_processing.py`)

整合了LLM标注、文档结构化和向量化功能：

- **V1格式处理**：从原始段落开始的完整流程
- **V2格式处理**：从预结构化数据开始的简化流程
- **可配置选项**：窗口大小、重叠、是否向量化等

### 5. LLM文档处理API (`app/api/v1/endpoints/document_llm_processing.py`)

提供了完整的文档处理API：

- `POST /api/v1/llm-processing/process_document_v1` - 处理v1格式文档
- `POST /api/v1/llm-processing/process_document_v2` - 处理v2格式文档
- `POST /api/v1/llm-processing/process_document_v2_async` - 异步处理文档

## 向量集合Schema

实现了符合要求的向量集合schema，包含以下字段：

### 主要字段

- `id`: 主键（自增）
- `embedding`: 向量字段（FLOAT_VECTOR）
- `unit_type`: 单元类型（CLAUSE/CLAUSE_ITEM）

### 文档元数据

- `doc_id`: 文档ID
- `doc_name`: 文档名称

### Section信息

- `section_id`: 章节ID
- `section_title`: 章节标题
- `section_level`: 章节层级

### Clause信息

- `clause_id`: 条款ID
- `clause_title`: 条款标题
- `clause_order_index`: 条款顺序

### ClauseItem信息

- `item_id`: 子项ID
- `parent_item_id`: 父子项ID
- `item_order_index`: 子项顺序

### 业务字段

- `content`: 文本内容
- `lang`: 语言
- `role`: 角色
- `region`: 区域
- `nc_type`: 内容类型
- `loc`: 位置信息（JSON）

## 使用流程

### 1. 创建向量集合

```bash
curl -X POST "http://localhost:8000/api/v1/vector_collections/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mirrors_clause_vectors",
    "description": "合同条款与子项向量集合",
    "embedding_dimension": 1536,
    "options": {
      "shards_num": 2,
      "enable_dynamic_fields": true,
      "consistency_level": "Session"
    }
  }'
```

### 2. 处理v1格式文档（从原始段落）

```bash
curl -X POST "http://localhost:8000/api/v1/llm-processing/process_document_v1" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "id": "doc_001",
      "title": "合同示例",
      "type": "contract",
      "created_at": "2023-01-01T00:00:00Z",
      "file_url": "https://example.com/doc.pdf",
      "drafters": ["张三", "李四"]
    },
    "segments": [
      {
        "id": "seg_1",
        "order_index": 1,
        "text": "第一条 合同目的",
        "page": 1
      },
      {
        "id": "seg_2",
        "order_index": 2,
        "text": "本合同旨在明确双方权利义务",
        "page": 1
      }
    ],
    "options": {
      "window_size": 10,
      "overlap": 2,
      "vectorize": true,
      "collection_name": "mirrors_clause_vectors"
    }
  }'
```

### 3. 处理v2格式文档（从预结构化数据）

```bash
curl -X POST "http://localhost:8000/api/v1/llm-processing/process_document_v2" \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {
      "id": "doc_002",
      "title": "合同示例",
      "type": "contract"
    },
    "structure": {
      "id": "root",
      "level": 1,
      "page": 1,
      "title": "第一章",
      "title_tags": {
        "role": "NON_CLAUSE",
        "nc_type": "CLAUSE_TITLE"
      },
      "content": "",
      "content_tags": {},
      "children": [
        {
          "id": "clause_1",
          "level": 2,
          "page": 1,
          "title": "第一条",
          "content": "本合同旨在明确双方权利义务",
          "content_tags": {
            "role": "CLAUSE",
            "nc_type": "CLAUSE_BODY"
          }
        }
      ]
    },
    "options": {
      "vectorize": true,
      "collection_name": "mirrors_clause_vectors"
    }
  }'
```

## 设计特点

1. **单集合设计**：同时存储Clause和ClauseItem，通过unit_type区分
2. **完整元数据**：保留文档结构关系，支持复杂查询
3. **动态字段**：支持未来扩展，无需重建集合
4. **多层次处理**：支持v1和v2两种格式，适应不同场景
5. **异步处理**：大文档可后台处理，避免阻塞
6. **可配置性**：窗口大小、重叠、向量化等均可配置

## 后续扩展

1. **真实LLM集成**：替换mock响应为实际LLM API调用
2. **Embedding服务**：实现真正的文本向量化服务
3. **高级查询**：基于metadata的复杂向量查询
4. **文档更新**：支持增量更新文档内容
5. **批量处理**：支持批量处理多个文档