"""
系统测试脚本
测试整个文档处理流程，包括：
1. 文档路由和解析
2. 段落标注
3. 文档结构化
4. 向量化入库
5. 搜索功能
"""
import asyncio
import json
import requests


# API基础URL
BASE_URL = "http://localhost:8000"


async def test_document_processing():
    """测试文档处理流程"""
    print("="*50)
    print("测试文档处理流程")
    print("="*50)
    
    # 1. 测试文档解析接口
    doc_data = {
        "id": "test_doc_001",
        "title": "测试合同文档",
        "type": "参考文本",
        "created_at": "2025-01-01",
        "file_url": "http://example.com/test.docx",  # 假设的URL
        "rich_content": """
        测试合同

        第一章 总则

        第一条 定义
        本合同中使用的术语定义如下：

        第二条 适用范围
        本合同适用于所有相关方。

        第二章 权利义务

        第三条 甲方的权利和义务
        （一）甲方有权要求乙方履行合同义务。
        （二）甲方应当按时支付合同款项。
        1. 甲方应当于每月5日前支付上月款项。
        2. 逾期支付应当承担违约责任。

        第四条 乙方的权利和义务
        （一）乙方有权要求甲方履行合同义务。
        （二）乙方应当按时完成合同约定的工作。

        第三章 违约责任

        第五条 违约处理
        任何一方违反合同约定，应当承担相应的违约责任。

        第四章 附则

        第六条 其他
        本合同自双方签字盖章之日起生效。

        甲方：_____________
        乙方：_____________
        """,
        "drafters": [
            {"name": "test_user", "status": "activate"}
        ]
    }
    
    print("1. 调用文档解析接口...")
    response = requests.post(f"{BASE_URL}/api/v1/parse_document", json=doc_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"   解析成功: {result.get('message')}")
        print(f"   文档ID: {result.get('doc_id')}")
        print(f"   标注段落数: {result.get('labeled_segments_count')}")
        print(f"   结构化数据: {result.get('structured_data')}")
    else:
        print(f"   解析失败: {response.status_code} - {response.text}")
        return False
    
    # 2. 测试文档状态查询
    doc_id = doc_data["id"]
    print(f"\n2. 查询文档处理状态: {doc_id}")
    response = requests.get(f"{BASE_URL}/api/v1/document_status/{doc_id}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   状态查询成功")
        print(f"   文档状态: {result.get('status')}")
        print(f"   解析状态: {result.get('parse_status')}")
        print(f"   结构化状态: {result.get('structure_status')}")
        print(f"   向量化状态: {result.get('vector_status')}")
        print(f"   统计信息: {result.get('statistics')}")
    else:
        print(f"   状态查询失败: {response.status_code} - {response.text}")
    
    return True


def test_vector_search():
    """测试向量搜索功能"""
    print("\n" + "="*50)
    print("测试向量搜索功能")
    print("="*50)
    
    # 1. 测试语义搜索
    search_request = {
        "query": "甲方的权利和义务",
        "limit": 5
    }
    
    print("1. 语义搜索...")
    response = requests.post(f"{BASE_URL}/api/v1/vector-search/semantic_search", json=search_request)
    
    if response.status_code == 200:
        result = response.json()
        print(f"   搜索成功")
        print(f"   查询: {result.get('query')}")
        print(f"   结果数量: {result.get('total')}")
        
        for i, item in enumerate(result.get('results', [])):
            print(f"   结果 {i+1}:")
            print(f"     ID: {item.get('clause_id')}")
            print(f"     标题: {item.get('clause_title')}")
            print(f"     内容: {item.get('content')[:50]}...")
            print(f"     相似度: {item.get('distance')}")
    else:
        print(f"   语义搜索失败: {response.status_code} - {response.text}")
    
    # 2. 测试混合搜索
    hybrid_request = {
        "query": "甲方的权利和义务",
        "keywords": ["甲方", "权利", "义务"],
        "limit": 5,
        "semantic_weight": 0.7,
        "keyword_weight": 0.3
    }
    
    print("\n2. 混合搜索...")
    response = requests.post(f"{BASE_URL}/api/v1/vector-search/hybrid_search", json=hybrid_request)
    
    if response.status_code == 200:
        result = response.json()
        print(f"   搜索成功")
        print(f"   查询: {result.get('query')}")
        print(f"   关键词: {result.get('keywords')}")
        print(f"   结果数量: {result.get('total')}")
        
        for i, item in enumerate(result.get('results', [])):
            print(f"   结果 {i+1}:")
            print(f"     ID: {item.get('clause_id')}")
            print(f"     标题: {item.get('clause_title')}")
            print(f"     内容: {item.get('content')[:50]}...")
            print(f"     综合分数: {item.get('combined_score')}")
    else:
        print(f"   混合搜索失败: {response.status_code} - {response.text}")


def test_document_retrieval():
    """测试文档检索功能"""
    print("\n" + "="*50)
    print("测试文档检索功能")
    print("="*50)
    
    doc_id = "test_doc_001"
    
    # 1. 获取文档的所有条款
    print(f"1. 获取文档 {doc_id} 的所有条款...")
    response = requests.get(f"{BASE_URL}/api/v1/vector-search/document/{doc_id}/clauses")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   获取成功")
        print(f"   文档ID: {result.get('doc_id')}")
        print(f"   条款数量: {result.get('total')}")
        
        for i, clause in enumerate(result.get('clauses', [])[:3]):  # 只显示前3个
            print(f"   条款 {i+1}:")
            print(f"     ID: {clause.get('clause_id')}")
            print(f"     标题: {clause.get('clause_title')}")
            print(f"     内容: {clause.get('content')[:50]}...")
    else:
        print(f"   获取条款失败: {response.status_code} - {response.text}")
    
    # 2. 获取文档的所有子项
    print(f"\n2. 获取文档 {doc_id} 的所有子项...")
    response = requests.get(f"{BASE_URL}/api/v1/vector-search/document/{doc_id}/clause_items")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   获取成功")
        print(f"   文档ID: {result.get('doc_id')}")
        print(f"   子项数量: {result.get('total')}")
        
        for i, item in enumerate(result.get('clause_items', [])[:3]):  # 只显示前3个
            print(f"   子项 {i+1}:")
            print(f"     ID: {item.get('item_id')}")
            print(f"     所属条款: {item.get('clause_id')}")
            print(f"     内容: {item.get('content')[:50]}...")
    else:
        print(f"   获取子项失败: {response.status_code} - {response.text}")


def main():
    """主函数"""
    print("法务数据结构化系统测试")
    print("请确保API服务已启动: http://localhost:8000")
    
    try:
        # 测试API健康状态
        print("\n检查API健康状态...")
        response = requests.get(f"{BASE_URL}/api/v1/health")
        if response.status_code != 200:
            print(f"API服务未正常启动: {response.status_code}")
            return
        
        print("API服务正常")
        
        # 测试文档处理流程
        test_success = asyncio.run(test_document_processing())
        
        if test_success:
            # 测试向量搜索功能
            test_vector_search()
            
            # 测试文档检索功能
            test_document_retrieval()
    
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")


if __name__ == "__main__":
    main()