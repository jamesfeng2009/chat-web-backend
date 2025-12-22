#!/usr/bin/env python3
"""
测试合并后的文档处理服务
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.document_processing import DocumentProcessingService

async def test_document_processing():
    """测试文档处理服务"""
    # 创建文档处理服务实例
    service = DocumentProcessingService()
    
    # 测试文档内容
    test_content = """
# 合同标题

## 第一条 基本条款

这是第一条的内容，包含了一些基本条款。

1. 子条款1
2. 子条款2

## 第二条 附加条款

这是第二条的内容，包含了一些附加条款。

（一）附加子条款1
（二）附加子条款2

# 签字页

甲方：_________________
乙方：_________________
日期：_________________
"""
    
    print("开始测试文档处理服务...")
    
    try:
        # 测试仅标注
        print("\n1. 测试仅标注功能...")
        result = await service.label_document_only(
            document_content=test_content,
            doc_id="test_doc_001",
            doc_name="测试合同"
        )
        
        print(f"标注结果: {result['success']}")
        if result['success']:
            data = result['data']
            print(f"总段落数: {data.get('total_segments', 0)}")
            print(f"条款单元数: {len(data.get('clause_units', []))}")
        
        # 测试完整处理（不包括向量摄入）
        print("\n2. 测试完整文档处理（不包括向量摄入）...")
        result = await service.process_document(
            document_content=test_content,
            doc_id="test_doc_002",
            doc_name="测试合同完整处理",
            embedding_model="text-embedding-3-large",
            collection_name="test_collection",
            lang="zh",
            score_threshold="1"
        )
        
        print(f"处理结果: {result['success']}")
        if result['success']:
            data = result['data']
            print(f"总段落数: {data.get('total_segments', 0)}")
            print(f"条款单元数: {len(data.get('clause_units', []))}")
            print(f"向量化成功: {data.get('ingested', 0)}")
        
        print("\n✅ 测试完成！文档处理服务工作正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_document_processing())