# 法务数据结构化系统 v2 - 使用指南

## 系统概述

本系统是一个完整的法务文档结构化和向量化解决方案，支持从文档解析到智能检索的完整流程。系统采用模块化设计，包含文档路由、标注、结构化、向量化和检索等核心功能。

系统支持两种主要的数据结构格式：
1. **v1格式**: 基于文件URL或富文本的文档处理
2. **v2格式**: 基于预先解析好的结构化数据的文档处理（新增）

## 核心功能

### 1. 文档解析
- 支持多种文档格式：PDF、DOCX、HTML、TXT、MD
- 自动提取文档内容和元数据
- 支持从URL下载文档或直接解析富文本
- 支持直接处理预先结构化的文档数据

### 2. 三管线标签系统
- region: 区域标签（COVER/MAIN/APPENDIX/SIGN/TOC）
- nc_type: 非条款类型（COVER_TITLE/PARTIES/CLAUSE_BODY等）
- role: 角色标签（CLAUSE/NON_CLAUSE）

### 3. 文档结构化
- 自动识别章节层次结构（section）
- 自动识别条款和子项（clause/clause_item）
- 支持多级嵌套结构
- 支持直接导入预先结构化的数据

### 4. 向量化存储
- 自动将条款和子项向量化
- 支持批量向量化处理
- 集成Milvus向量数据库

### 5. 智能检索
- 语义搜索
- 混合搜索（关键词+语义）
- 文档检索

## API接口

### 文档处理接口

#### 解析文档 (v1格式)
```
POST /api/v1/parse_document
Content-Type: application/json

{
    "id": "doc-001",
    "title": "公司章程",
    "type": "参考文本",
    "created_at": "2022-08-20",
    "file_url": "https://example.com/doc.pdf",
    "rich_content": "<html>...</html>",
    "drafters": [{"name": "张三", "status": "active"}]
}
```

#### 解析结构化文档 (v2格式) - 新增功能
```
POST /api/v1/document-parsing/parse_structured_document
Content-Type: application/json

{
    "metadata": {
        "id": "doc-001",
        "title": "公司章程",
        "type": "参考文本",
        "created_at": "2022-08-20",
        "file_url": "https://example.com/company-charter.docx",
        "drafters": [
            {"name": "刘冉", "status": "active"}
        ]
    },
    "structure": {
        "id": "section-1",
        "level": 1,
        "page": 1,
        "title": "公司章程",
        "title_tags": {"role": "NON_CLAUSE", "region": "COVER", "nc_type": "COVER_TITLE"},
        "content": "公司章程",
        "content_tags": {"role": "NON_CLAUSE", "region": "COVER", "nc_type": "COVER_TITLE"},
        "children": [
            {
                "id": "section-2",
                "level": 2,
                "page": 2,
                "title": "第一章 总则",
                "title_tags": {"role": "NON_CLAUSE", "region": "MAIN", "nc_type": ""},
                "content": "第一章 总则",
                "content_tags": {"role": "NON_CLAUSE", "region": "MAIN", "nc_type": ""},
                "children": [
                    {
                        "id": "clause-1",
                        "level": "2-1",
                        "page": 2,
                        "title": "第一条 公司名称和住所",
                        "title_tags": {"role": "", "region": "", "nc_type": ""},
                        "content": "第一条 公司名称和住所",
                        "content_tags": {"role": "CLAUSE", "region": "MAIN", "nc_type": "TITLE"}
                    }
                ]
            }
        ]
    },
    "vectorization": true
}
```

#### 获取文档处理状态
```
GET /api/v1/document_status/{doc_id}
```

#### 获取文档结构 (v2格式) - 新增功能
```
GET /api/v1/document-parsing/get_document_structure/{doc_id}
```

#### 重新处理文档
```
POST /api/v1/reprocess_document/{doc_id}
```

### 检索接口

#### 语义搜索
```
POST /api/v1/vector-search/semantic_search
Content-Type: application/json

{
    "query": "股权转让限制",
    "top_k": 5,
    "doc_ids": ["doc-001"],
    "filters": {
        "region": "MAIN",
        "role": "CLAUSE"
    }
}
```

#### 混合搜索
```
POST /api/v1/vector-search/hybrid_search
Content-Type: application/json

{
    "query": "股权转让限制",
    "top_k": 5,
    "doc_ids": ["doc-001"],
    "keyword_weight": 0.3
}
```

#### 文档检索
```
POST /api/v1/vector-search/document_search
Content-Type: application/json

{
    "query": "股权转让限制",
    "top_k": 5,
    "filters": {
        "type": "参考文本"
    }
}
```

## 数据模型

### Document（文档）
```
{
    "id": "文档ID",
    "name": "文档名称",
    "type": "文档类型",
    "file_type": "文件格式",
    "file_url": "文件URL",
    "drafters": "起草人信息",
    "status": "处理状态",
    "parse_status": "解析状态",
    "structure_status": "结构化状态",
    "vector_status": "向量化状态"
}
```

### Section（章节）
```
{
    "id": "章节ID",
    "doc_id": "文档ID",
    "parent_id": "父章节ID",
    "title": "章节标题",
    "content": "章节内容",
    "number_token": "编号标记",
    "level_hint": "层级提示",
    "order_index": "顺序"
}
```

### Clause（条款）
```
{
    "id": "条款ID",
    "doc_id": "文档ID",
    "section_id": "章节ID",
    "parent_clause_id": "父条款ID",
    "title": "条款标题",
    "content": "条款内容",
    "number_token": "编号标记",
    "role": "角色标签",
    "region": "区域标签",
    "nc_type": "非条款类型",
    "score": "置信度分数",
    "embedding_id": "向量ID"
}
```

### ClauseItem（条款子项）
```
{
    "id": "子项ID",
    "clause_id": "条款ID",
    "parent_item_id": "父子项ID",
    "content": "子项内容",
    "title": "子项标题",
    "number_token": "编号标记",
    "role": "角色标签",
    "region": "区域标签",
    "nc_type": "非条款类型",
    "score": "置信度分数",
    "embedding_id": "向量ID"
}
```

## 使用流程

### 1. 启动系统
```bash
# 启动数据库和Milvus
docker-compose up -d

# 启动API服务
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. 处理文档

#### v1格式处理（文件URL或富文本）
```python
import httpx

# 解析文档
response = httpx.post(
    "http://localhost:8000/api/v1/parse_document",
    json={
        "id": "doc-001",
        "title": "公司章程",
        "file_url": "https://example.com/charter.pdf"
    }
)

result = response.json()
doc_id = result["doc_id"]
```

#### v2格式处理（预先结构化数据）
```python
import httpx

# 解析结构化文档
response = httpx.post(
    "http://localhost:8000/api/v1/document-parsing/parse_structured_document",
    json={
        "metadata": {
            "id": "doc-001",
            "title": "公司章程",
            "type": "参考文本",
            "created_at": "2022-08-20",
            "file_url": "https://example.com/company-charter.docx",
            "drafters": [{"name": "刘冉", "status": "active"}]
        },
        "structure": {
            # 结构化数据...
        },
        "vectorization": True
    }
)

result = response.json()
doc_id = result["doc_id"]
```

### 3. 检索内容
```python
# 语义搜索
response = httpx.post(
    "http://localhost:8000/api/v1/vector-search/semantic_search",
    json={
        "query": "股东会职权",
        "top_k": 5,
        "doc_ids": [doc_id]
    }
)

results = response.json()["results"]
for item in results:
    print(f"内容: {item['content']}")
    print(f"相似度: {item['score']}")
```

## 测试脚本

### 基本功能测试 (v1格式)
```bash
# 运行基本功能测试
python test_system.py
```

### 新数据结构测试 (v2格式)
```bash
# 运行新数据结构测试
python test_v2_system.py
```

## 配置说明

### 数据库配置
```python
# app/core/config.py
DATABASE_URL = "postgresql://user:password@localhost/dbname"
```

### Milvus配置
```python
# app/core/config.py
MILVUS_HOST = "localhost"
MILVUS_PORT = 19530
MILVUS_COLLECTION_NAME = "legal_documents"
```

### 存储配置
```python
# app/core/config.py
STORAGE_TYPE = "local"  # local/s3/oss
```

## v2格式数据结构详解

### 数据结构说明
v2格式支持预先解析好的文档结构数据，适用于已有结构化处理结果的场景。数据结构包含以下主要部分：

1. **metadata**: 文档元数据
   - id: 文档ID（必需）
   - title: 文档标题
   - type: 文档类型
   - created_at: 创建时间
   - file_url: 文件下载链接
   - drafters: 起草人信息

2. **structure**: 文档结构数据
   - id: 元素ID
   - level: 层级
   - page: 页码
   - title: 标题
   - title_tags: 标题标签
   - content: 内容
   - content_tags: 内容标签
   - children: 子元素列表

3. **vectorization**: 是否进行向量化处理
   - true: 处理完成后进行向量化
   - false: 跳过向量化步骤

### 标签系统说明

#### title_tags 和 content_tags
每个元素可以包含以下标签：
- role: CLAUSE/NON_CLAUSE
- region: COVER/MAIN/APPENDIX/SIGN/TOC
- nc_type: 具体类型，如COVER_TITLE/PARTIES/CLAUSE_BODY等
- score: 置信度分数（1-4）

### 层级结构说明
- 章节结构: section -> section -> ...
- 条款结构: clause -> clause_item -> clause_item
- 支持混合嵌套结构

### 处理流程
1. 解析metadata并创建Document记录
2. 递归解析structure结构
3. 根据标签和内容类型创建Section/Clause/ClauseItem对象
4. 建立层次关系
5. 批量保存到数据库
6. 可选进行向量化处理

## 故障排除

### 常见问题

1. **文档解析失败**
   - 检查文档格式是否支持
   - 确认文档URL可访问
   - 查看解析日志

2. **向量化失败**
   - 检查Milvus服务状态
   - 确认向量维度配置
   - 查看向量化日志

3. **搜索结果不准确**
   - 调整top_k参数
   - 使用混合搜索
   - 添加过滤条件

4. **v2格式数据处理失败**
   - 检查数据结构是否符合要求
   - 确认metadata和structure字段完整
   - 检查嵌套结构是否正确

### 日志查看
```bash
# 查看应用日志
tail -f logs/app.log

# 查看数据库日志
docker logs postgres-container

# 查看Milvus日志
docker logs milvus-container
```

## 性能优化

1. **批量处理**
   - 使用批量API接口
   - 调整批处理大小

2. **缓存优化**
   - 启用查询缓存
   - 预加载热点数据

3. **并发处理**
   - 使用异步API
   - 调整工作进程数

## 部署指南

### Docker部署
```bash
# 构建镜像
docker build -t legal-structure-system .

# 运行容器
docker-compose up -d
```

### Kubernetes部署
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legal-structure-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: legal-structure-system
  template:
    metadata:
      labels:
        app: legal-structure-system
    spec:
      containers:
      - name: api
        image: legal-structure-system:latest
        ports:
        - containerPort: 8000
```

## 监控和维护

### 监控指标
- 文档处理成功率
- 向量化处理速度
- 搜索响应时间
- 系统资源使用率

### 定期维护
- 清理无效向量
- 优化索引
- 备份数据库
- 更新模型