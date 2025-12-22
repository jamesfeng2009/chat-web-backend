# 向量摄入API文档

## 概述

向量摄入API支持将条款和子项数据批量向量化并写入指定的Milvus集合。该API利用Milvus 2.x的动态字段特性，可以灵活处理各种元数据，无需预先定义所有字段。

## 设计特点

1. **单集合设计**：Clause和ClauseItem存储在同一集合中，通过`unit_type`区分
2. **动态字段支持**：利用Milvus动态字段特性，可灵活处理各种元数据
3. **父子关系表示**：通过`clause_id`、`item_id`、`parent_item_id`等字段表示层级关系
4. **灵活向量化**：支持预计算向量和服务端计算两种模式
5. **批量处理**：支持批量写入，提高效率

## API接口

### 接口信息

- **Method**: POST
- **Path**: `/api/v1/vector-collections/{collection_name}/ingest`
- **Content-Type**: application/json

### 路径参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|-------|------|
| collection_name | string | 是 | 集合名称，如 "mirrors_clause_vectors" |

### 请求体

```json
{
  "embedding_model": "text-embedding-3-large",
  "items": [
    {
      "unit_type": "CLAUSE",
      
      "doc_id": "DOC_001",
      "doc_name": "股权转让协议（示范文本）",
      
      "section_id": "SEC_01",
      "section_title": "第一章 总则",
      "section_level": 1,
      
      "clause_id": "C_24",
      "clause_title": "第二十四条 股权转让",
      "clause_order_index": 24,
      
      "item_id": null,
      "parent_item_id": null,
      "item_order_index": null,
      
      "lang": "zh",
      "role": "CLAUSE",
      "region": "MAIN",
      "nc_type": "CLAUSE_BODY",
      
      "content": "本条款约定了股权转让的对象、价格、付款方式以及交割条件……",
      "loc": {
        "page_range": [5, 6],
        "char_span": [1234, 1456],
        "list_level": 0
      },
      
      "biz_tags": {
        "draft_owner": "张三",
        "type": "股权转让协议",
        "reviewer": "李四"
      },
      
      "embedding": null  // 可选，由服务端计算
    },
    {
      "unit_type": "CLAUSE_ITEM",
      
      "doc_id": "DOC_001",
      "doc_name": "股权转让协议（示范文本）",
      
      "section_id": "SEC_01",
      "section_title": "第一章 总则",
      "section_level": 1,
      
      "clause_id": "C_24",
      "clause_title": "第二十四条 股权转让",
      "clause_order_index": 24,
      
      "item_id": "C_24_1",
      "parent_item_id": null,
      "item_order_index": 1,
      
      "lang": "zh",
      "role": "CLAUSE",
      "region": "MAIN",
      "nc_type": "CLAUSE_BODY",
      
      "content": "（一）甲方同意将其持有的目标公司 40% 股权转让给乙方……",
      "loc": {
        "page_range": [5, 5],
        "char_span": [1300, 1370],
        "list_level": 1
      },
      
      "biz_tags": {
        "draft_owner": "张三",
        "type": "股权转让协议",
        "reviewer": "李四"
      },
      
      "embedding": null  // 可选，由服务端计算
    }
  ]
}
```

### 请求体字段说明

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|-------|------|
| embedding_model | string | 是 | 使用的embedding模型名称 |
| items | array | 是 | 向量摄入项列表 |

#### items 中的字段

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|-------|------|
| unit_type | string | 是 | 单元类型："CLAUSE" / "CLAUSE_ITEM" |
| doc_id | string | 是 | 文档ID |
| doc_name | string | 是 | 文档名称 |
| section_id | string | 否 | 章节ID |
| section_title | string | 否 | 章节标题 |
| section_level | int | 否 | 章节层级 |
| clause_id | string | 否 | 条款ID |
| clause_title | string | 否 | 条款标题 |
| clause_order_index | int | 否 | 条款顺序 |
| item_id | string | 否 | 子项ID |
| parent_item_id | string | 否 | 父子项ID |
| item_order_index | int | 否 | 子项顺序 |
| lang | string | 否 | 语言，默认"zh" |
| role | string | 是 | 角色："CLAUSE" / "NON_CLAUSE" |
| region | string | 是 | 区域："MAIN" / "COVER" / "APPENDIX" / "SIGN" |
| nc_type | string | 否 | 内容类型 |
| content | string | 是 | 向量化源文本 |
| loc | object | 否 | 定位信息（JSON） |
| biz_tags | object | 否 | 业务标签（JSON） |
| embedding | array | 否 | 预计算的向量，可为null由服务端计算 |

### 响应体

#### 成功响应

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "collection": "mirrors_clause_vectors",
    "total": 2,
    "succeeded": 2,
    "failed": 0,
    "failed_items": []
  }
}
```

#### 部分失败响应

```json
{
  "code": 0,
  "message": "partial_failed",
  "data": {
    "collection": "mirrors_clause_vectors",
    "total": 3,
    "succeeded": 2,
    "failed": 1,
    "failed_items": [
      {
        "index": 2,
        "reason": "missing content"
      }
    ]
  }
}
```

### 响应体字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| code | int | 状态码：0-成功，非0-失败 |
| message | string | 响应消息 |
| data | object | 响应数据 |

#### data 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| collection | string | 集合名称 |
| total | int | 总数 |
| succeeded | int | 成功数 |
| failed | int | 失败数 |
| failed_items | array | 失败项列表 |

#### failed_items 中的字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| index | int | 失败项索引 |
| reason | string | 失败原因 |

## 使用示例

### cURL 示例

```bash
# 向 mirrors_clause_vectors 集合批量写入向量数据
curl -X POST "http://localhost:8000/api/v1/vector-collections/mirrors_clause_vectors/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "embedding_model": "text-embedding-3-large",
    "items": [
      {
        "unit_type": "CLAUSE",
        "doc_id": "DOC_001",
        "doc_name": "股权转让协议",
        "section_id": "SEC_01",
        "section_title": "第一章 总则",
        "section_level": 1,
        "clause_id": "C_24",
        "clause_title": "第二十四条 股权转让",
        "clause_order_index": 24,
        "lang": "zh",
        "role": "CLAUSE",
        "region": "MAIN",
        "nc_type": "CLAUSE_BODY",
        "content": "本条款约定了股权转让的对象、价格、付款方式以及交割条件",
        "loc": {
          "page_range": [5, 6],
          "char_span": [1234, 1456]
        }
      },
      {
        "unit_type": "CLAUSE_ITEM",
        "doc_id": "DOC_001",
        "doc_name": "股权转让协议",
        "section_id": "SEC_01",
        "section_title": "第一章 总则",
        "section_level": 1,
        "clause_id": "C_24",
        "clause_title": "第二十四条 股权转让",
        "clause_order_index": 24,
        "item_id": "C_24_1",
        "item_order_index": 1,
        "lang": "zh",
        "role": "CLAUSE",
        "region": "MAIN",
        "nc_type": "CLAUSE_BODY",
        "content": "（一）甲方同意将其持有的目标公司 40% 股权转让给乙方",
        "loc": {
          "page_range": [5, 5],
          "char_span": [1300, 1370],
          "list_level": 1
        }
      }
    ]
  }'
```

### Python 示例

```python
import requests
import json

url = "http://localhost:8000/api/v1/vector-collections/mirrors_clause_vectors/ingest"
headers = {"Content-Type": "application/json"}

data = {
    "embedding_model": "text-embedding-3-large",
    "items": [
        {
            "unit_type": "CLAUSE",
            "doc_id": "DOC_001",
            "doc_name": "股权转让协议",
            "clause_id": "C_24",
            "content": "本条款约定了股权转让的对象、价格、付款方式以及交割条件",
            "lang": "zh",
            "role": "CLAUSE",
            "region": "MAIN"
        }
    ]
}

response = requests.post(url, headers=headers, json=data)
result = response.json()
print(json.dumps(result, indent=2, ensure_ascii=False))
```

## 技术实现

### 核心流程

1. **验证集合存在性**：检查指定的集合是否存在
2. **验证数据有效性**：检查必要字段是否存在
3. **生成向量**：
   - 如果item中已提供embedding，使用预计算向量
   - 否则，调用embedding服务计算向量
4. **组装列式数据**：准备符合pymilvus要求的列式数据结构
5. **批量写入Milvus**：将向量数据批量写入指定集合
6. **返回处理结果**：统计成功/失败数量及失败原因

### 动态字段处理

Milvus 2.x支持动态字段，本实现充分利用这一特性：

1. **固定字段**：向量、unit_type等核心字段在集合创建时定义
2. **动态字段**：biz_tags等自定义字段直接写入，无需预先定义
3. **列式写入**：使用pymilvus的列式写入方式，提高效率

### 错误处理

1. **集合不存在**：返回明确的错误信息
2. **数据验证**：检查必要字段，返回详细错误
3. **部分失败**：记录失败项索引和原因，继续处理其他项
4. **异常捕获**：捕获并记录所有异常，避免系统崩溃

## 注意事项

1. **向量维度**：确保向量维度与集合定义一致
2. **集合状态**：确保集合已加载（loaded）状态
3. **批量大小**：避免单次写入过大，可分批处理
4. **预计算向量**：如有预计算向量，确保维度和格式正确
5. **JSON字段**：biz_tags和loc等JSON字段会被自动序列化

## 扩展性

1. **新增字段**：通过动态字段支持，可直接在items中添加新字段
2. **多模型支持**：通过embedding_model参数支持多种embedding模型
3. **多集合支持**：同一接口支持向多个不同集合写入数据
4. **自定义业务标签**：biz_tags字段支持任意业务标签，灵活扩展