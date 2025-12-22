#!/usr/bin/env python3
"""
简单测试三管线LLM标注服务的核心功能
"""
import re
from bs4 import BeautifulSoup


def test_html_extraction():
    """测试HTML富文本提取功能"""
    
    # 测试富文本
    html_text = '<p class="MsoNormal"><span style="font-family: 宋体; font-size: 10.5pt;">协议各方约定，下列任何一种情形发生，天使轮投资方有权在各方协商一致的情况下选择将持有的公司股权部分或全部退出：</span></p>'
    
    print("原始HTML:")
    print(html_text)
    print("\n提取的纯文本:")
    
    # 使用BeautifulSoup提取文本
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
    print(text)
    
    # 测试简单正则表达式方法
    print("\n使用正则表达式提取:")
    simple_text = re.sub(r'<[^>]+>', '', html_text)
    print(simple_text)


def test_scoring():
    """测试加权评分系统"""
    
    # 权重配置
    weights = {
        "role": 0.4,      # role权重
        "region": 0.2,    # region权重
        "nc_type": 0.4    # nc_type权重
    }
    
    # 测试数据
    test_cases = [
        {
            "name": "典型条款",
            "role": "CLAUSE",
            "region": "MAIN",
            "nc_type": "CLAUSE_BODY"
        },
        {
            "name": "封面标题",
            "role": "NON_CLAUSE",
            "region": "COVER",
            "nc_type": "TITLE"
        },
        {
            "name": "目录",
            "role": "NON_CLAUSE",
            "region": "TOC",
            "nc_type": None
        },
        {
            "name": "附件内容",
            "role": "CLAUSE",
            "region": "APPENDIX",
            "nc_type": "CLAUSE_BODY"
        },
        {
            "name": "签字页",
            "role": "NON_CLAUSE",
            "region": "SIGN",
            "nc_type": "PARTIES"
        }
    ]
    
    print("\n\n评分测试:")
    for case in test_cases:
        # 计算role分数
        role_score = 4 if case["role"] == "CLAUSE" else 0
        
        # 计算region分数
        region_scores = {
            "MAIN": 2,       # 主体部分更可能是条款
            "COVER": 0,      # 封面不太可能是条款
            "TOC": 0,        # 目录不是条款
            "APPENDIX": 1,   # 附件有些可能是条款
            "SIGN": 0        # 签字页不是条款
        }
        region_score = region_scores.get(case["region"], 0)
        
        # 计算nc_type分数（简化版）
        nc_type_scores = {
            "TITLE": 1,           # 标题本身不一定是条款内容
            "PARTIES": 0,         # 当事人信息不是条款
            "CLAUSE_BODY": 4,     # 条款正文是典型的条款
            None: 1               # 未确定类型的内容
        }
        nc_type_score = nc_type_scores.get(case["nc_type"], 0)
        
        # 加权求和计算总分数
        total_score = (
            role_score * weights["role"] +
            region_score * weights["region"] +
            nc_type_score * weights["nc_type"]
        )
        
        # 将分数映射到1-4级别（不再有0分，所有内容都有分数）
        if total_score >= 3.5:
            score = "4"
        elif total_score >= 2.5:
            score = "3"
        elif total_score >= 1.5:
            score = "2"
        else:
            score = "1"
        
        print(f"\n{case['name']}:")
        print(f"  角色: {case['role']} (分数: {role_score})")
        print(f"  区域: {case['region']} (分数: {region_score})")
        print(f"  类型: {case['nc_type']} (分数: {nc_type_score})")
        print(f"  总分: {total_score:.2f} → 等级: {score}")


if __name__ == "__main__":
    print("=== 三管线LLM标注服务核心功能测试 ===")
    test_html_extraction()
    test_scoring()
    print("\n=== 测试完成 ===")