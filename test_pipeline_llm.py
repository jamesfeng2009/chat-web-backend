#!/usr/bin/env python3
"""
测试三管线LLM标注服务
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.llm_labeling import PipelineLLMLabelingService


async def test_pipeline_llm():
    """测试三管线LLM标注服务"""
    
    # 创建服务实例
    service = PipelineLLMLabelingService()
    
    # 测试数据：富文本和普通文本混合
    test_segments = [
        {
            "id": "seg1",
            "order_index": 1,
            "text": "投资协议",
            "page": 1
        },
        {
            "id": "seg2",
            "order_index": 2,
            "text": '<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">甲方：XX科技有限公司</span></p><p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">乙方：YY投资管理有限公司</span></p>',
            "page": 1
        },
        {
            "id": "seg3",
            "order_index": 3,
            "text": "第一条 投资金额",
            "page": 1
        },
        {
            "id": "seg4",
            "order_index": 4,
            "text": '<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">1.1 甲方同意向乙方投资人民币1000万元（大写：壹仟万元整）。</span></p>',
            "page": 1
        },
        {
            "id": "seg5",
            "order_index": 5,
            "text": "1.2 投资款应在本协议签署后30个工作日内支付完毕。",
            "page": 1
        },
        {
            "id": "seg6",
            "order_index": 6,
            "text": "第二条 股权安排",
            "page": 2
        },
        {
            "id": "seg7",
            "order_index": 7,
            "text": '<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">2.1 甲方投资后，将持有乙方10%的股权。</span></p>',
            "page": 2
        },
        {
            "id": "seg8",
            "order_index": 8,
            "text": "附件一：投资款支付计划",
            "page": 3
        },
        {
            "id": "seg9",
            "order_index": 9,
            "text": "甲方代表签字：______________",
            "page": 4
        },
        {
            "id": "seg10",
            "order_index": 10,
            "text": "乙方代表签字：______________",
            "page": 4
        }
    ]
    
    print("开始测试三管线LLM标注服务...")
    print(f"测试段落数量: {len(test_segments)}")
    
    # 执行标注
    labeled_segments = await service.label_segments(test_segments)
    
    print("\n标注结果:")
    for seg in labeled_segments:
        print(f"\n段落 ID: {seg['id']}")
        print(f"  原始文本: {seg['original_text'] if 'original_text' in seg else seg['text'][:50]}...")
        print(f"  处理后文本: {seg['text'][:50]}...")
        print(f"  区域: {seg['region']}")
        print(f"  类型: {seg['nc_type']}")
        print(f"  角色: {seg['role']}")
        print(f"  分数: {seg['score']} (原始: {seg.get('score_float', 0)})")
        print(f"  是富文本: {seg.get('is_rich_text', False)}")
    
    # 测试条款合并
    print("\n\n开始测试条款合并...")
    clause_units = service.merge_segments_by_clause(labeled_segments, score_threshold="1")
    
    print(f"\n合并后的条款单元数量: {len(clause_units)}")
    for i, unit in enumerate(clause_units):
        print(f"\n条款单元 {i+1}:")
        print(f"  ID: {unit['id']}")
        print(f"  区域: {unit['region']}")
        print(f"  类型: {unit['nc_type']}")
        print(f"  角色: {unit['role']}")
        print(f"  分数: {unit['score']} (原始: {unit['score_float']})")
        print(f"  段落数: {len(unit['segment_ids'])}")
        print(f"  内容: {unit['text'][:100]}...")


if __name__ == "__main__":
    asyncio.run(test_pipeline_llm())