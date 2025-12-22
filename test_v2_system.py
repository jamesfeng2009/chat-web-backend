#!/usr/bin/env python3
"""
测试系统v2 - 测试新的数据结构解析功能
"""

import asyncio
import json
import httpx



# 测试数据
test_document = {
    "metadata": {
        "id": "test-doc-001",
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
        "title_tags": {
            "role": "NON_CLAUSE",
            "region": "COVER",
            "nc_type": "COVER_TITLE"
        },
        "content": "公司章程",
        "content_tags": {
            "role": "NON_CLAUSE",
            "region": "COVER",
            "nc_type": "COVER_TITLE"
        },
        "children": [
            {
                "id": "section-2",
                "level": 2,
                "page": 2,
                "title": "第一章 总则",
                "title_tags": {
                    "role": "NON_CLAUSE",
                    "region": "MAIN",
                    "nc_type": ""
                },
                "content": "第一章 总则",
                "content_tags": {
                    "role": "NON_CLAUSE",
                    "region": "MAIN",
                    "nc_type": ""
                },
                "children": [
                    {
                        "id": "clause-1",
                        "level": "2-1",
                        "page": 2,
                        "title": "第一条 公司名称和住所",
                        "title_tags": {
                            "role": "",
                            "region": "",
                            "nc_type": ""
                        },
                        "content": "第一条 公司名称和住所",
                        "content_tags": {
                            "role": "CLAUSE",
                            "region": "MAIN",
                            "nc_type": "TITLE"
                        }
                    },
                    {
                        "id": "clause-2",
                        "level": "2-2",
                        "page": 3,
                        "title": "第二条 公司经营范围",
                        "title_tags": {
                            "role": "",
                            "region": "",
                            "nc_type": ""
                        },
                        "content": "第二条 公司经营范围",
                        "content_tags": {
                            "role": "CLAUSE",
                            "region": "MAIN",
                            "nc_type": "TITLE"
                        },
                        "children": [
                            {
                                "id": "item-1",
                                "parent_id": "clause-2",
                                "level": "2-2-1",
                                "page": 3,
                                "content": "(一) 从事技术开发、技术咨询、技术服务；",
                                "content_tags": {
                                    "role": "CLAUSE",
                                    "region": "MAIN",
                                    "nc_type": "CLAUSE_BODY"
                                }
                            },
                            {
                                "id": "item-2",
                                "parent_id": "clause-2",
                                "level": "2-2-2",
                                "page": 3,
                                "content": "(二) 从事软件开发和销售；",
                                "content_tags": {
                                    "role": "CLAUSE",
                                    "region": "MAIN",
                                    "nc_type": "CLAUSE_BODY"
                                }
                            }
                        ]
                    }
                ]
            },
            {
                "id": "section-3",
                "level": 3,
                "page": 4,
                "title": "第二章 股东会",
                "title_tags": {
                    "role": "NON_CLAUSE",
                    "region": "MAIN",
                    "nc_type": ""
                },
                "content": "第二章 股东会",
                "content_tags": {
                    "role": "NON_CLAUSE",
                    "region": "MAIN",
                    "nc_type": ""
                },
                "children": [
                    {
                        "id": "clause-3",
                        "level": "3-1",
                        "page": 4,
                        "title": "第七条 公司股东会由全体股东组成，是公司的权力机构，行使下列职权：",
                        "title_tags": {
                            "role": "",
                            "region": "",
                            "nc_type": ""
                        },
                        "content": "第七条 公司股东会由全体股东组成，是公司的权力机构，行使下列职权：",
                        "content_tags": {
                            "role": "CLAUSE",
                            "region": "MAIN",
                            "nc_type": "TITLE"
                        },
                        "children": [
                            {
                                "id": "item-3",
                                "parent_id": "clause-3",
                                "level": "3-1-1",
                                "page": 4,
                                "content": "(1) 决定公司的经营方针和投资计划；",
                                "content_tags": {
                                    "role": "CLAUSE",
                                    "region": "MAIN",
                                    "nc_type": "CLAUSE_BODY"
                                }
                            },
                            {
                                "id": "item-4",
                                "parent_id": "clause-3",
                                "level": "3-1-2",
                                "page": 4,
                                "content": "(2) 选举和更换董事；",
                                "content_tags": {
                                    "role": "CLAUSE",
                                    "region": "MAIN",
                                    "nc_type": "CLAUSE_BODY"
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    },
    "vectorization": True
}


async def test_document_parsing():
    """测试文档解析功能"""
    base_url = "http://localhost:8000"
    
    print("开始测试文档解析功能...")
    
    # 使用httpx发送请求
    async with httpx.AsyncClient() as client:
        try:
            # 调用文档解析API
            print("发送文档解析请求...")
            response = await client.post(
                f"{base_url}/api/v1/document-parsing/parse_structured_document",
                json=test_document,
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print("文档解析成功！")
                print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                # 测试获取文档结构
                doc_id = result.get("doc_id")
                if doc_id:
                    print(f"\n获取文档结构: {doc_id}")
                    structure_response = await client.get(
                        f"{base_url}/api/v1/document-parsing/get_document_structure/{doc_id}"
                    )
                    
                    if structure_response.status_code == 200:
                        structure_result = structure_response.json()
                        print("获取文档结构成功！")
                        print(f"统计信息: {json.dumps(structure_result.get('statistics'), indent=2, ensure_ascii=False)}")
                        
                        # 测试向量搜索
                        print("\n测试向量搜索...")
                        search_response = await client.post(
                            f"{base_url}/api/v1/vector-search/semantic_search",
                            json={
                                "query": "股东会职权",
                                "top_k": 5,
                                "doc_ids": [doc_id]
                            }
                        )
                        
                        if search_response.status_code == 200:
                            search_result = search_response.json()
                            print("向量搜索成功！")
                            print(f"找到 {len(search_result.get('results', []))} 个相关结果")
                        else:
                            print(f"向量搜索失败: {search_response.status_code} - {search_response.text}")
                    else:
                        print(f"获取文档结构失败: {structure_response.status_code} - {structure_response.text}")
            else:
                print(f"文档解析失败: {response.status_code} - {response.text}")
                
        except httpx.ConnectError:
            print("连接失败，请确保服务器正在运行在 http://localhost:8000")
        except Exception as e:
            print(f"测试过程中发生错误: {str(e)}")


def print_usage():
    """打印使用说明"""
    print("""
    法务数据结构化系统 v2 测试脚本
    
    使用方法:
        python test_v2_system.py
    
    前提条件:
        1. 服务器正在运行 (uvicorn app.main:app --host 0.0.0.0 --port 8000)
        2. 数据库已连接并初始化
        3. Milvus服务正在运行
    
    测试内容:
        1. 文档解析 - 测试新的数据结构解析功能
        2. 文档结构获取 - 测试获取解析后的文档结构
        3. 向量搜索 - 测试基于向量的语义搜索
    """)


if __name__ == "__main__":
    print_usage()
    print("\n开始测试...")
    asyncio.run(test_document_parsing())
    print("\n测试完成！")