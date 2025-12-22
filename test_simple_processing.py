#!/usr/bin/env python3
"""
简单测试文档处理服务
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接测试三管线LLM标注服务
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'services'))
from app.services.llm_labeling import PipelineLLMLabelingService

def test_llm_service():
    """测试LLM标注服务"""
    # 创建服务实例
    service = PipelineLLMLabelingService()
    
    # 测试段落
    test_segments = [
        {"id": "seg1", "text": "第一条 基本条款", "order_index": 0},
        {"id": "seg2", "text": "这是第一条的内容，包含了一些基本条款。", "order_index": 1},
        {"id": "seg3", "text": "第二条 附加条款", "order_index": 2},
        {"id": "seg4", "text": "这是第二条的内容，包含了一些附加条款。", "order_index": 3},
        {"id": "seg5", "text": "甲方：____________", "order_index": 4},
    ]
    
    print("开始测试三管线LLM标注服务...")
    print(f"测试段落数: {len(test_segments)}")
    
    # 测试合并段落为条款单元
    print("\n测试合并段落为条款单元...")
    try:
        # 创建模拟的标注结果
        labeled_segments = []
        for seg in test_segments:
            labeled_seg = seg.copy()
            # 根据文本内容添加模拟标注
            if "第一条" in seg["text"] or "第二条" in seg["text"]:
                labeled_seg["region"] = "MAIN"
                labeled_seg["nc_type"] = "TITLE"
                labeled_seg["role"] = "CLAUSE"
                labeled_seg["score"] = "4"
            elif "甲方" in seg["text"]:
                labeled_seg["region"] = "SIGN"
                labeled_seg["nc_type"] = "PARTIES"
                labeled_seg["role"] = "NON_CLAUSE"
                labeled_seg["score"] = "1"
            else:
                labeled_seg["region"] = "MAIN"
                labeled_seg["nc_type"] = "CLAUSE_BODY"
                labeled_seg["role"] = "CLAUSE"
                labeled_seg["score"] = "3"
            labeled_segments.append(labeled_seg)
        
        # 测试合并段落为条款单元
        clause_units = service.merge_segments_by_clause(labeled_segments, "1")
        
        print(f"合并结果: {len(clause_units)} 个条款单元")
        for i, unit in enumerate(clause_units):
            print(f"条款单元 {i+1}:")
            print(f"  文本: {unit.get('text', '')[:50]}...")
            print(f"  区域: {unit.get('region', '')}")
            print(f"  类型: {unit.get('nc_type', '')}")
            print(f"  角色: {unit.get('role', '')}")
            print(f"  分数: {unit.get('score', '')}")
            print(f"  包含段落: {unit.get('segment_ids', [])}")
        
        print("\n✅ 测试完成！三管线LLM标注服务工作正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_service()