# 三管线LLM标注服务使用指南

## 概述

本文档介绍如何使用三管线独立的LLM标注服务，该服务实现了区域识别、结构类型判断和语义条款检测的并行处理。

## 核心特性

1. **三管线独立处理**：
   - 管线1：区域识别（COVER/TOC/MAIN/APPENDIX/SIGN）
   - 管线2：结构类型判断（nc_type）
   - 管线3：语义条款检测（CLAUSE/NON_CLAUSE）

2. **富文本支持**：
   - 自动检测HTML富文本
   - 使用BeautifulSoup提取纯文本内容
   - 保留原始富文本用于后续处理

3. **加权评分系统**：
   - role权重：0.4
   - region权重：0.2
   - nc_type权重：0.4
   - 最终分数范围：0-4

## API接口

### 1. 完整文档处理

```
POST /api/v1/document-processing/process-document
```

请求体：
```json
{
  "document_content": "文档内容，可以是富文本或纯文本",
  "doc_id": "文档唯一标识",
  "doc_name": "文档名称",
  "embedding_model": "text-embedding-3-large",
  "collection_name": "mirrors_clause_vectors",
  "lang": "zh",
  "score_threshold": "1"
}
```

### 2. 仅文档标注

```
POST /api/v1/document-processing/label-document
```

请求体：
```json
{
  "document_content": "文档内容，可以是富文本或纯文本",
  "doc_id": "文档唯一标识",
  "doc_name": "文档名称",
  "lang": "zh"
}
```

### 3. 向量摄入

```
POST /api/v1/document-processing/ingest-items
```

请求体：
```json
{
  "items": [
    {
      "unit_type": "CLAUSE",
      "doc_id": "文档ID",
      "doc_name": "文档名称",
      "clause_id": "条款ID",
      "clause_title": "条款标题",
      "clause_order_index": 0,
      "item_id": "项目ID",
      "parent_item_id": null,
      "item_order_index": 0,
      "lang": "zh",
      "role": "CLAUSE",
      "region": "MAIN",
      "nc_type": "CLAUSE_BODY",
      "score": "4",
      "content": "条款内容",
      "loc": {
        "segment_ids": ["seg1", "seg2"],
        "order_index": 10
      },
      "biz_tags": {
        "score_float": 3.8,
        "segment_count": 2
      }
    }
  ],
  "embedding_model": "text-embedding-3-large",
  "collection_name": "mirrors_clause_vectors"
}
```

## 使用示例

### Python客户端示例

```python
import requests
import json

# API基础URL
BASE_URL = "http://localhost:8000/api/v1"

# 示例文档内容（富文本）
document_content = """
<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">协议各方约定，下列任何一种情形发生，天使轮投资方有权在各方协商一致的情况下选择将持有的公司股权部分或全部退出：</span></p>
<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">1) 若公司后轮融资，估值达到【】万元，天使轮投资方将以不低于融资、合并、收购估值的9折价格选择出售其持有的公司股权的10%；</span></p>
<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">2) 若公司被第三方公司合并、收购，估值不得低于【】万元，否则天使轮投资方有权要求钱沛东补足天使轮投资方计划按上述【】万元退出股权的总金额与实际退出金额的差额。</span></p>
"""

# 1. 仅进行文档标注
labeling_request = {
    "document_content": document_content,
    "doc_id": "doc_001",
    "doc_name": "投资协议示例",
    "lang": "zh"
}

response = requests.post(
    f"{BASE_URL}/document-processing/label-document",
    json=labeling_request
)

if response.status_code == 200:
    result = response.json()
    print("标注成功!")
    print(f"总段落数: {result['data']['total_segments']}")
    print(f"条款单元数: {result['data']['clause_units']}")
    
    # 打印前几个标注结果
    for i, segment in enumerate(result["labeled_segments"][:3]):
        print(f"\n段落 {i+1}:")
        print(f"  文本: {segment['text'][:50]}...")
        print(f"  区域: {segment['region']}")
        print(f"  类型: {segment['nc_type']}")
        print(f"  角色: {segment['role']}")
        print(f"  分数: {segment['score']}")
    
    # 打印条款单元
    print("\n条款单元:")
    for i, unit in enumerate(result["clause_units"]):
        print(f"\n条款 {i+1}:")
        print(f"  ID: {unit['id']}")
        print(f"  区域: {unit['region']}")
        print(f"  类型: {unit['nc_type']}")
        print(f"  角色: {unit['role']}")
        print(f"  分数: {unit['score']}")
        print(f"  内容: {unit['text'][:100]}...")
else:
    print(f"标注失败: {response.status_code} - {response.text}")

# 2. 完整文档处理（包含向量化和存储）
processing_request = {
    "document_content": document_content,
    "doc_id": "doc_001",
    "doc_name": "投资协议示例",
    "embedding_model": "text-embedding-3-large",
    "collection_name": "mirrors_clause_vectors",
    "lang": "zh",
    "score_threshold": "1"
}

response = requests.post(
    f"{BASE_URL}/document-processing/process-document",
    json=processing_request
)

if response.status_code == 200:
    result = response.json()
    print("\n处理成功!")
    print(f"状态: {result['status']}")
    print(f"消息: {result['message']}")
    print(f"总段落数: {result['data']['total_segments']}")
    print(f"条款单元数: {result['data']['clause_units']}")
    print(f"成功摄入: {result['data']['ingested']}")
    print(f"失败数: {result['data']['failed']}")
else:
    print(f"处理失败: {response.status_code} - {response.text}")
```

## 评分系统说明

### 分数计算

系统根据三个维度的加权评分计算最终条款分数：

1. **role分数**：
   - CLAUSE：4分
   - NON_CLAUSE：0分

2. **region分数**：
   - MAIN：2分（主体部分更可能是条款）
   - APPENDIX：1分（附件有些可能是条款）
   - COVER/TOC/SIGN：0分

3. **nc_type分数**：
   - CLAUSE_BODY：4分
   - TITLE：1分
   - None：1分
   - PARTIES：0分

### 最终分数映射

```
总分 >= 3.5  →  "4" (基本确定是条款)
总分 >= 2.5  →  "3" (非常像条款)
总分 >= 1.5  →  "2" (像条款)
总分 < 1.5    →  "1" (疑似条款)
```

## 注意事项

1. **富文本处理**：系统会自动检测HTML标签并提取纯文本内容，同时保留原始富文本用于后续处理。

2. **并行处理**：三个管线并行执行，提高处理效率。

3. **灵活权重**：可以通过修改`PipelineLLMLabelingService`中的`weights`配置来调整各维度的权重。

4. **分数阈值**：可以通过`score_threshold`参数控制哪些段落被视为条款并参与合并。

5. **错误处理**：系统具有良好的错误处理机制，即使部分管线失败也能返回部分结果。