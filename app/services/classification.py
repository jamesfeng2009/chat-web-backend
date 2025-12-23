import re
import json
from typing import Any, Tuple

from dataclasses import dataclass
from enum import Enum

from app.core.logger import get_logger

logger = get_logger(__name__)


class DocumentType(Enum):
    """文档类型枚举"""
    CONTRACT = "contract"  # 合同
    AGREEMENT = "agreement"  # 协议
    REGULATION = "regulation"  # 规定
    POLICY = "policy"  # 政策
    LAW = "law"  # 法律
    OTHER = "other"  # 其他


class ContractDomain(Enum):
    """合同领域枚举"""
    PROPERTY = "property"  # 房地产
    FINANCE = "finance"  # 金融
    INTELLECTUAL_PROPERTY = "intellectual_property"  # 知识产权
    EMPLOYMENT = "employment"  # 劳动雇佣
    CORPORATE = "corporate"  # 公司事务
    PROCUREMENT = "procurement"  # 采购
    PARTNERSHIP = "partnership"  # 合作伙伴
    OTHER = "other"  # 其他


class ClauseCategory(Enum):
    """条款分类枚举"""
    DEFINITION = "definition"  # 定义
    SCOPE = "scope"  # 范围
    OBLIGATION = "obligation"  # 义务
    RIGHT = "right"  # 权利
    LIABILITY = "liability"  # 责任
    TERM = "term"  # 期限
    PAYMENT = "payment"  # 支付
    TERMINATION = "termination"  # 终止
    DISPUTE = "dispute"  # 争议
    CONFIDENTIALITY = "confidentiality"  # 保密
    INTELLECTUAL_PROPERTY = "intellectual_property"  # 知识产权
    FORCE_MAJEURE = "force_majeure"  # 不可抗力
    GOVERNING_LAW = "governing_law"  # 管辖法律
    MISCELLANEOUS = "miscellaneous"  # 其他


@dataclass
class ClassificationResult:
    """分类结果"""
    document_type: DocumentType | None = None
    document_type_confidence: float = 0.0
    contract_domain: ContractDomain | None = None
    contract_domain_confidence: float = 0.0
    clause_categories: list[Tuple[ClauseCategory, float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "document_type": {
                "value": self.document_type.value if self.document_type else None,
                "confidence": self.document_type_confidence
            },
            "contract_domain": {
                "value": self.contract_domain.value if self.contract_domain else None,
                "confidence": self.contract_domain_confidence
            },
            "clause_categories": [
                {"category": cat.value, "confidence": conf}
                for cat, conf in (self.clause_categories or [])
            ]
        }


class ClassificationService:
    """分类服务"""
    
    def __init__(self):
        # 文档类型关键词映射
        self.document_type_keywords = {
            DocumentType.CONTRACT: [
                "合同", "合约", "contract", "agreement"
            ],
            DocumentType.AGREEMENT: [
                "协议", "agreement", "pact", "accord"
            ],
            DocumentType.REGULATION: [
                "规定", "条例", "办法", "regulation", "rule", "ordinance"
            ],
            DocumentType.POLICY: [
                "政策", "policy", "guideline", "strategy"
            ],
            DocumentType.LAW: [
                "法", "法律", "law", "act", "statute", "legislation"
            ]
        }
        
        # 合同领域关键词映射
        self.contract_domain_keywords = {
            ContractDomain.PROPERTY: [
                "房产", "房屋", "土地", "不动产", "租赁", "买卖", "property", "real estate", "lease", "rental"
            ],
            ContractDomain.FINANCE: [
                "金融", "贷款", "融资", "投资", "资金", "finance", "loan", "investment", "funding"
            ],
            ContractDomain.INTELLECTUAL_PROPERTY: [
                "知识产权", "专利", "商标", "版权", "intellectual property", "patent", "trademark", "copyright"
            ],
            ContractDomain.EMPLOYMENT: [
                "雇佣", "劳动", "员工", "工作", "employment", "labor", "employee", "work"
            ],
            ContractDomain.CORPORATE: [
                "公司", "股权", "股东", "董事会", "corporate", "shareholder", "stock", "equity"
            ],
            ContractDomain.PROCUREMENT: [
                "采购", "供应", "招标", "procurement", "purchase", "supply", "tender"
            ],
            ContractDomain.PARTNERSHIP: [
                "合作", "合伙", "合资", "partnership", "cooperation", "joint venture"
            ]
        }
        
        # 条款分类关键词映射
        self.clause_category_keywords = {
            ClauseCategory.DEFINITION: [
                "定义", "解释", "含义", "definition", "interpretation", "meaning"
            ],
            ClauseCategory.SCOPE: [
                "范围", "适用", "scope", "application", "applicability"
            ],
            ClauseCategory.OBLIGATION: [
                "义务", "责任", "职责", "obligation", "duty", "responsibility"
            ],
            ClauseCategory.RIGHT: [
                "权利", "权益", "right", "entitlement", "privilege"
            ],
            ClauseCategory.LIABILITY: [
                "责任", "赔偿", "损失", "liability", "compensation", "damages"
            ],
            ClauseCategory.TERM: [
                "期限", "时间", "有效期", "term", "duration", "validity period"
            ],
            ClauseCategory.PAYMENT: [
                "支付", "付款", "费用", "payment", "pay", "fee", "cost"
            ],
            ClauseCategory.TERMINATION: [
                "终止", "解除", "结束", "termination", "end", "cancellation"
            ],
            ClauseCategory.DISPUTE: [
                "争议", "纠纷", "仲裁", "dispute", "controversy", "arbitration"
            ],
            ClauseCategory.CONFIDENTIALITY: [
                "保密", "机密", "confidentiality", "secret", "non-disclosure"
            ],
            ClauseCategory.INTELLECTUAL_PROPERTY: [
                "知识产权", "专利", "商标", "版权", "intellectual property", "patent", "trademark", "copyright"
            ],
            ClauseCategory.FORCE_MAJEURE: [
                "不可抗力", "天灾", "force majeure", "act of god", "natural disaster"
            ],
            ClauseCategory.GOVERNING_LAW: [
                "管辖法律", "适用法律", "法律适用", "governing law", "applicable law"
            ]
        }
    
    def classify_document(
        self,
        title: str,
        content: str,
        use_llm: bool = False
    ) -> ClassificationResult:
        """
        文档分类
        
        Args:
            title: 文档标题
            content: 文档内容
            use_llm: 是否使用LLM分类
            
        Returns:
            分类结果
        """
        if use_llm:
            return self._classify_with_llm(title, content)
        else:
            return self._classify_with_keywords(title, content)
    
    def classify_clause(
        self,
        title: str,
        content: str,
        use_llm: bool = False
    ) -> list[Tuple[ClauseCategory, float]]:
        """
        条款分类
        
        Args:
            title: 条款标题
            content: 条款内容
            use_llm: 是否使用LLM分类
            
        Returns:
            分类结果列表（分类，置信度）
        """
        if use_llm:
            return self._classify_clause_with_llm(title, content)
        else:
            return self._classify_clause_with_keywords(title, content)
    
    def _classify_with_keywords(
        self,
        title: str,
        content: str
    ) -> ClassificationResult:
        """基于关键词的文档分类"""
        # 合并标题和内容
        text = f"{title} {content}"
        text_lower = text.lower()
        
        # 文档类型分类
        doc_type_scores = {}
        for doc_type, keywords in self.document_type_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += 1
            doc_type_scores[doc_type] = score
        
        # 获取最高分的文档类型
        best_doc_type = max(doc_type_scores, key=doc_type_scores.get)
        doc_type_confidence = min(doc_type_scores[best_doc_type] / 5.0, 1.0)  # 归一化到0-1
        
        # 合同领域分类
        domain_scores = {}
        for domain, keywords in self.contract_domain_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += 1
            domain_scores[domain] = score
        
        # 获取最高分的合同领域
        best_domain = max(domain_scores, key=domain_scores.get)
        domain_confidence = min(domain_scores[best_domain] / 5.0, 1.0)  # 归一化到0-1
        
        # 如果文档类型不是合同或协议，则领域设置为其他
        if best_doc_type not in [DocumentType.CONTRACT, DocumentType.AGREEMENT]:
            best_domain = ContractDomain.OTHER
            domain_confidence = 0.0
        
        return ClassificationResult(
            document_type=best_doc_type,
            document_type_confidence=doc_type_confidence,
            contract_domain=best_domain,
            contract_domain_confidence=domain_confidence
        )
    
    def _classify_clause_with_keywords(
        self,
        title: str,
        content: str
    ) -> list[Tuple[ClauseCategory, float]]:
        """基于关键词的条款分类"""
        # 合并标题和内容
        text = f"{title} {content}"
        text_lower = text.lower()
        
        # 条款分类评分
        category_scores = {}
        for category, keywords in self.clause_category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    score += 1
            category_scores[category] = score
        
        # 按得分排序
        sorted_categories = sorted(
            category_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 转换为结果列表，归一化得分
        max_score = max(category_scores.values()) if category_scores else 1
        results = []
        for category, score in sorted_categories:
            if score > 0:  # 只包含有得分的分类
                confidence = min(score / max_score, 1.0)
                results.append((category, confidence))
        
        return results
    
    def _classify_with_llm(
        self,
        title: str,
        content: str
    ) -> ClassificationResult:
        """使用LLM进行文档分类"""
        # 这里应该调用LLM API进行分类
        # 为了简化，这里返回基于关键词的分类结果
        return self._classify_with_keywords(title, content)
    
    def _classify_clause_with_llm(
        self,
        title: str,
        content: str
    ) -> list[Tuple[ClauseCategory, float]]:
        """使用LLM进行条款分类"""
        # 这里应该调用LLM API进行分类
        # 为了简化，这里返回基于关键词的分类结果
        return self._classify_clause_with_keywords(title, content)
    
    def extract_business_tags(
        self,
        text: str,
        tag_types: list[str] | None = None
    ) -> dict[str, list[str]]:
        """
        提取业务标签
        
        Args:
            text: 文本
            tag_types: 标签类型列表
            
        Returns:
            标签字典
        """
        if not tag_types:
            tag_types = ["party", "date", "amount", "location", "person"]
        
        tags = {}
        
        for tag_type in tag_types:
            if tag_type == "party":
                tags[tag_type] = self._extract_parties(text)
            elif tag_type == "date":
                tags[tag_type] = self._extract_dates(text)
            elif tag_type == "amount":
                tags[tag_type] = self._extract_amounts(text)
            elif tag_type == "location":
                tags[tag_type] = self._extract_locations(text)
            elif tag_type == "person":
                tags[tag_type] = self._extract_persons(text)
        
        return tags
    
    def _extract_parties(self, text: str) -> list[str]:
        """提取合同方"""
        parties = []
        
        # 匹配常见合同方模式
        patterns = [
            r'甲方[：:]\s*([^，,。\n]+)',  # 甲方
            r'乙方[：:]\s*([^，,。\n]+)',  # 乙方
            r'丙方[：:]\s*([^，,。\n]+)',  # 丙方
            r'委托方[：:]\s*([^，,。\n]+)',  # 委托方
            r'受托方[：:]\s*([^，,。\n]+)',  # 受托方
            r'承租方[：:]\s*([^，,。\n]+)',  # 承租方
            r'出租方[：:]\s*([^，,。\n]+)',  # 出租方
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            parties.extend([match.strip() for match in matches])
        
        return list(set(parties))  # 去重
    
    def _extract_dates(self, text: str) -> list[str]:
        """提取日期"""
        dates = []
        
        # 匹配中文日期格式
        patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',  # 2023年12月1日
            r'(\d{4}年\d{1,2}月)',  # 2023年12月
            r'(\d{1,2}月\d{1,2}日)',  # 12月1日
            r'(\d{4}-\d{1,2}-\d{1,2})',  # 2023-12-1
            r'(\d{1,2}/\d{1,2}/\d{4})',  # 12/1/2023
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)
        
        return list(set(dates))  # 去重
    
    def _extract_amounts(self, text: str) -> list[str]:
        """提取金额"""
        amounts = []
        
        # 匹配金额模式
        patterns = [
            r'(\d+(?:\.\d+)?元)',  # 数字+元
            r'(\d+(?:\.\d+)?万元)',  # 数字+万元
            r'(\d+(?:,\d{3})*(?:\.\d+)?元)',  # 带逗号的数字+元
            r'(人民币\s*\d+(?:,\d{3})*(?:\.\d+)?元)',  # 人民币+金额
            r'(\$\s*\d+(?:,\d{3})*(?:\.\d+)?)',  # 美元金额
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            amounts.extend(matches)
        
        return list(set(amounts))  # 去重
    
    def _extract_locations(self, text: str) -> list[str]:
        """提取地点"""
        locations = []
        
        # 这里应该使用更复杂的地点提取规则
        # 为了简化，只提取常见的地点模式
        patterns = [
            r'([^，,。\n]*市[^，,。\n]*)',  # XXX市
            r'([^，,。\n]*省[^，,。\n]*)',  # XXX省
            r'([^，,。\n]*区[^，,。\n]*)',  # XXX区
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            locations.extend([match.strip() for match in matches])
        
        # 过滤掉过短或过长的结果
        locations = [loc for loc in locations if 2 <= len(loc) <= 10]
        
        return list(set(locations))  # 去重
    
    def _extract_persons(self, text: str) -> list[str]:
        """提取人名"""
        persons = []
        
        # 匹配常见人名模式
        patterns = [
            r'法定代表人[：:]\s*([^，,。\n]+)',  # 法定代表人
            r'代表人[：:]\s*([^，,。\n]+)',  # 代表人
            r'联系人[：:]\s*([^，,。\n]+)',  # 联系人
            r'签字[：:]?\s*([^，,。\n]+)',  # 签字人
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            persons.extend([match.strip() for match in matches])
        
        return list(set(persons))  # 去重


# 全局分类服务实例
classification_service = ClassificationService()