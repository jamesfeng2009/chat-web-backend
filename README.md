# 法务数据结构化系统

## 项目概述

本系统旨在实现法务文档的结构化处理，将原始合同文档转换为章→条→子项→正文段的树形结构，并提供向量化、检索和回溯功能。

## 系统架构

### 技术栈

- **后端框架**: Python + FastAPI
- **数据库**: MySQL 8.0 (关系数据) + Milvus (向量数据)
- **文件存储**: 本地存储 / MinIO
- **缓存**: Redis
- **任务队列**: Celery
- **容器化**: Docker + Docker Compose

### 核心功能

1. **文档管理**: 上传、存储、版本控制
2. **文档解析**: 支持PDF、DOCX、TXT、MD、HTML等格式
3. **结构化处理**: 条款切分、层次结构构建
4. **向量化**: 文本向量化、向量库管理
5. **检索服务**: 语义搜索、相似度搜索
6. **业务标签**: 文档分类、条款标注

## 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose
- MySQL 8.0+
- Redis 6.0+
- Milvus 2.3+

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd chat-web-backend
```

2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库、API密钥等
```

3. 使用Docker Compose启动服务
```bash
docker-compose up -d
```

4. 安装Python依赖
```bash
pip install -r requirements.txt
```

5. 启动应用
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 验证安装

访问 http://localhost:8000/docs 查看API文档，或访问 http://localhost:8000/api/v1/health/ 检查服务状态。

## API文档

### 文档管理API

#### 上传文档
```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

Parameters:
- file: 文件 (支持PDF、DOCX、TXT、MD、HTML)
- ingest_channel: 导入渠道 (可选)
- metadata: 元数据 (JSON字符串，可选)
```

#### 获取文档列表
```
GET /api/v1/documents/

Parameters:
- skip: 跳过记录数 (可选)
- limit: 返回记录数 (可选)
- status: 状态过滤 (可选)
- owner_id: 所有者过滤 (可选)
```

#### 获取文档详情
```
GET /api/v1/documents/{document_id}
```

#### 更新文档
```
PUT /api/v1/documents/{document_id}
Content-Type: application/json

Body:
{
  "name": "文档名称",
  "metadata": {...}
}
```

#### 更新文档状态
```
PUT /api/v1/documents/{document_id}/status

Parameters:
- status: 状态
- parse_status: 解析状态 (可选)
- structure_status: 结构化状态 (可选)
- vector_status: 向量化状态 (可选)
```

#### 删除文档
```
DELETE /api/v1/documents/{document_id}
```

#### 下载文档
```
GET /api/v1/documents/{document_id}/download
```

#### 搜索文档
```
GET /api/v1/documents/search/{keyword}

Parameters:
- skip: 跳过记录数 (可选)
- limit: 返回记录数 (可选)
```

### 文档解析API

#### 解析文档
```
POST /api/v1/parsing/{document_id}/parse
Content-Type: application/json

Body:
{
  "parser_type": "auto",
  "options": {...}
}
```

#### 获取解析结果
```
GET /api/v1/parsing/{document_id}/parse
```

### 文档结构化API

#### 结构化文档
```
POST /api/v1/structure/{document_id}/structure
Content-Type: application/json

Body:
{
  "structure_type": "auto",
  "options": {...}
}
```

#### 获取结构化结果
```
GET /api/v1/structure/{document_id}/structure
```

#### 获取文档章节
```
GET /api/v1/structure/{document_id}/sections
```

#### 获取文档条款
```
GET /api/v1/structure/{document_id}/clauses

Parameters:
- skip: 跳过记录数 (可选)
- limit: 返回记录数 (可选)
```

#### 获取条款详情
```
GET /api/v1/structure/{document_id}/clauses/{clause_id}
```

### 向量集合API

#### 创建向量集合
```
POST /api/v1/vector-collections/
Content-Type: application/json

Body:
{
  "name": "集合名称",
  "description": "集合描述",
  "embedding_dimension": 1536,
  "options": {
    "shards_num": 2,
    "enable_dynamic_fields": true,
    "consistency_level": "Session"
  }
}
```

#### 获取向量集合列表
```
GET /api/v1/vector-collections/
```

#### 获取向量集合详情
```
GET /api/v1/vector-collections/{collection_name}
```

#### 删除向量集合
```
DELETE /api/v1/vector-collections/{collection_name}
```

#### 批量导入向量数据
```
POST /api/v1/vector-collections/{collection_name}/ingest
Content-Type: application/json

Body:
{
  "embedding_model": "text-embedding-3-large",
  "batch_size": 100,
  "upsert": false,
  "async": false,
  "items": [
    {
      "unit_type": "CLAUSE",
      "doc_id": "文档ID",
      "doc_name": "文档名称",
      "content": "文本内容",
      "lang": "zh",
      "role": "CLAUSE",
      "region": "MAIN",
      "nc_type": "CLAUSE_BODY",
      ...
    }
  ]
}
```

### 搜索API

#### 语义搜索
```
POST /api/v1/search/semantic
Content-Type: application/json

Body:
{
  "collection": "向量集合名称",
  "query": "搜索查询",
  "embedding_model": "text-embedding-3-large",
  "limit": 10,
  "filters": {...},
  "include_content": true
}
```

#### 相似度搜索
```
POST /api/v1/search/similarity
Content-Type: application/json

Body: 同语义搜索
```

## 数据模型

### 文档表 (documents)
- id: 文档ID
- name: 文档名称
- ingest_channel: 导入渠道
- file_type: 文件类型
- checksum: 文件校验和
- file_ref: 文件存储引用
- metadata: 文档元数据
- status: 处理状态
- parse_status: 解析状态
- structure_status: 结构化状态
- vector_status: 向量化状态

### 章节表 (sections)
- id: 章节ID
- doc_id: 文档ID
- title: 章节标题
- level: 大纲层级
- order_index: 全局顺序
- loc: 定位信息
- role: 角色
- region: 区域
- nc_type: 非条款类型

### 条款表 (clauses)
- id: 条款ID
- doc_id: 文档ID
- section_id: 章节ID
- title: 条款标题
- content: 条款内容
- lang: 文本语种
- embedding_id: 向量ID
- embedding_dimension: 向量维度
- loc: 定位信息
- role: 角色
- region: 区域
- nc_type: 非条款类型

### 子项表 (clause_items)
- id: 子项ID
- clause_id: 条款ID
- parent_item_id: 父项ID
- title: 子项标题
- content: 子项内容
- lang: 文本语种
- embedding_id: 向量ID
- loc: 定位信息
- role: 角色
- region: 区域
- nc_type: 非条款类型

### 段落跨度表 (paragraph_spans)
- id: 段落ID
- owner_type: 所有者类型
- owner_id: 所有者ID
- seq: 段落顺序
- raw_text: 原始段落文本
- style: 样式信息
- loc: 定位信息
- role: 角色
- region: 区域
- nc_type: 非条款类型

## 开发指南

### 目录结构

```
app/
├── api/               # API路由
│   └── v1/          # API v1版本
├── core/             # 核心配置
├── crud/             # 数据库操作
├── models/           # 数据模型
├── schemas/          # Pydantic模式
└── services/         # 业务逻辑服务
tests/                # 测试代码
scripts/              # 脚本文件
```

### 添加新的API端点

1. 在 `app/api/v1/endpoints/` 中创建新的端点文件
2. 在 `app/api/v1/api.py` 中注册路由
3. 在 `app/schemas/` 中定义请求/响应模式
4. 在 `app/services/` 中实现业务逻辑
5. 在 `app/crud/` 中添加数据库操作

### 添加新的数据模型

1. 在 `app/models/` 中定义SQLAlchemy模型
2. 在 `app/schemas/` 中定义Pydantic模式
3. 在 `app/crud/` 中实现CRUD操作
4. 在 `app/services/` 中实现业务逻辑

### 测试

运行单元测试：
```bash
pytest tests/
```

运行特定测试：
```bash
pytest tests/test_document_service.py -v
```

## 部署指南

### 开发环境

使用Docker Compose启动所有服务：
```bash
docker-compose up -d
```

### 生产环境

1. 准备生产环境配置
2. 设置环境变量
3. 使用Kubernetes或Docker Swarm部署
4. 配置负载均衡和反向代理
5. 设置监控和日志收集

### 监控

系统提供以下监控端点：
- `/api/v1/health/` - 健康检查
- `/metrics` - Prometheus指标 (如果配置)

## 常见问题

### Q: 如何添加新的文档格式支持？

A: 在 `app/services/parser.py` 中创建新的解析器类，继承 `BaseParser`，并在 `ParserService` 中注册。

### Q: 如何使用自定义的向量模型？

A: 在 `app/services/embedding.py` 中的 `model_configs` 添加新模型配置。

### Q: 如何调整检索结果的相关性？

A: 在 `app/services/search.py` 中修改混合搜索权重或相关性计算逻辑。

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。