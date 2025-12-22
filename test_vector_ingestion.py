#!/usr/bin/env python3
"""
测试向量摄入服务
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接测试向量摄入服务
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'services'))
from vector_ingestion import VectorIngestionService
from app.schemas.vector_ingestion import VectorIngestItem, VectorIngestRequest

def test_vector_ingestion():
    """测试向量摄入服务"""
    # 创建服务实例
    service = VectorIngestionService()
    
    # 测试数据
    test_items = [
        VectorIngestItem(
            unit_type="CLAUSE",
            doc_id="test_doc_001",
            doc_name="测试合同",
            clause_id="clause_001",
            clause_title="第一条 基本条款",
            clause_order_index=0,
            item_id="clause_001",
            parent_item_id=None,
            item_order_index=0,
            lang="zh",
            role="CLAUSE",
            region="MAIN",
            nc_type="TITLE",
            score="4",
            content="这是第一条的内容，包含了一些基本条款。",
            loc={"segment_ids": ["seg1", "seg2"], "order_index": 0},
            biz_tags={"score_float": 4.0, "segment_count": 2}
        ),
        VectorIngestItem(
            unit_type="CLAUSE",
            doc_id="test_doc_001",
            doc_name="测试合同",
            clause_id="clause_002",
            clause_title="第二条 附加条款",
            clause_order_index=1,
            item_id="clause_002",
            parent_item_id=None,
            item_order_index=0,
            lang="zh",
            role="CLAUSE",
            region="MAIN",
            nc_type="TITLE",
            score="3",
            content="这是第二条的内容，包含了一些附加条款。",
            loc={"segment_ids": ["seg3", "seg4"], "order_index": 1},
            biz_tags={"score_float": 3.0, "segment_count": 2}
        )
    ]
    
    print("开始测试向量摄入服务...")
    print(f"测试数据项: {len(test_items)}")
    
    try:
        # 测试准备列数据
        print("\n测试准备列数据...")
        embeddings = [[0.1 * i for i in range(1536)] for _ in test_items]  # 模拟向量
        columns = service._prepare_columns(test_items, embeddings)
        
        print(f"列数据键: {list(columns.keys())}")
        for key, value in columns.items():
            print(f"  {key}: {len(value)} 项")
        
        print("\n✅ 测试完成！向量摄入服务工作正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vector_ingestion()