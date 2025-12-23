from typing import Any
"""
三管线独立的LLM标注服务
实现区域识别、结构类型判断和语义条款检测的并行处理
"""
import json
import asyncio
from collections import defaultdict
import re

# 简单的HTML标签移除函数，避免使用bs4
def _remove_html_tags(html_text: str) -> str:
    """简单的HTML标签移除函数"""
    import re
    return re.sub(r'<[^>]+>', '', html_text)

from app.core.logger import get_logger

logger = get_logger(__name__)


class PipelineLLMLabelingService:
    """三管线独立的LLM标注服务"""
    
    def __init__(self, llm_service: Any | None = None):
        # 区域标签定义（简化版）
        self.REGION_LABELS = ["COVER", "TOC", "MAIN", "APPENDIX", "SIGN"]
        
        # NC_TYPE标签定义，根据region映射（简化版）
        self.NC_TYPE_MAPPING = {
            "COVER": ["TITLE", "PARTIES", None],
            "TOC": [None],
            "MAIN": ["TITLE", "CLAUSE_BODY", None],
            "APPENDIX": ["TITLE", "CLAUSE_BODY", None],
            "SIGN": ["PARTIES", "TITLE", None]
        }
        
        # 语义角色标签
        self.ROLE_LABELS = ["CLAUSE", "NON_CLAUSE"]
        
        # 条款分数级别
        self.SCORE_LEVELS = ["1", "2", "3", "4"]
        
        # 权重配置
        self.weights = {
            "role": 0.4,      # role权重
            "region": 0.2,    # region权重
            "nc_type": 0.4    # nc_type权重
        }
        
        # LLM服务
        self.llm_service = llm_service
    
    async def label_segments(self, segments: list[dict[str, Any]], window_size: int = 10, overlap: int = 2) -> list[dict[str, Any]]:
        """
        使用三管线并行标注文档段落
        
        Args:
            segments: 待标注的段落列表
            window_size: 滑动窗口大小
            overlap: 窗口重叠大小
            
        Returns:
            标注结果列表
        """
        if not segments:
            return []
        
        # 预处理富文本
        processed_segments = self._preprocess_segments(segments)
        
        # 创建滑动窗口
        windows = self._create_sliding_windows(processed_segments, window_size, overlap)
        
        # 并行执行三个管线
        pipeline_tasks = []
        for window in windows:
            pipeline_tasks.append(self._pipeline_region_labeling(window))
            pipeline_tasks.append(self._pipeline_nc_type_labeling(window))
            pipeline_tasks.append(self._pipeline_semantic_clause_detection(window))
        
        # 等待所有任务完成
        pipeline_results = await asyncio.gather(*pipeline_tasks, return_exceptions=True)
        
        # 过滤掉异常结果
        valid_results: list[dict[str, Any]] = [result for result in pipeline_results if isinstance(result, dict)]
        
        # 合并三个管线的结果
        merged_results = self._merge_pipeline_results(
            valid_results, 
            processed_segments,
            window_size, 
            overlap
        )
        
        # 计算条款分数
        scored_results = self._calculate_clause_scores(merged_results)
        
        return scored_results
    
    def _preprocess_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        预处理段落，处理富文本内容
        
        Args:
            segments: 原始段落列表
            
        Returns:
            处理后的段落列表
        """
        processed = []
        
        for seg in segments:
            text = seg.get("text", "")
            
            # 检查是否是HTML富文本
            if self._is_html_content(text):
                # 提取纯文本内容
                plain_text = self._extract_text_from_html(text)
                processed.append({
                    **seg,
                    "original_text": text,
                    "text": plain_text,
                    "is_rich_text": True
                })
            else:
                processed.append({
                    **seg,
                    "is_rich_text": False
                })
        
        return processed
    
    def _is_html_content(self, text: str) -> bool:
        """检查文本是否包含HTML标签"""
        return bool(re.search(r'<[^>]+>', text))
    
    def _extract_text_from_html(self, html_text: str) -> str:
        """
        从HTML富文本中提取纯文本
        
        Args:
            html_text: HTML富文本
            
        Returns:
            提取的纯文本
        """
        try:
            return _remove_html_tags(html_text)
        except Exception as e:
            logger.error(f"HTML解析失败: {str(e)}")
            # 如果解析失败，返回原始文本
            return html_text
    
    def _create_sliding_windows(self, segments: list[dict[str, Any]], window_size: int, overlap: int) -> list[list[dict[str, Any]]]:
        """创建滑动窗口"""
        windows = []
        n = len(segments)
        
        i = 0
        while i < n:
            # 确定窗口范围
            start = i
            end = min(i + window_size, n)
            window = segments[start:end]
            windows.append(window)
            
            # 下一个窗口的起始位置（考虑重叠）
            i = end - overlap
        
        return windows
    
    async def _pipeline_region_labeling(self, window: list[dict[str, Any]]) -> dict[str, Any]:
        """
        管线1：区域识别
        只判断 COVER / TOC / MAIN / APPENDIX / SIGN
        
        Args:
            window: 窗口段落列表
            
        Returns:
            区域标注结果
        """
        window_text = self._concatenate_window_text(window)
        
        # 构建区域识别的prompt
        prompt = {
            "task": "contract_region_labeling",
            "instruction": [
                "Segment window_text into non-overlapping spans.",
                "Assign ONLY a region label to each span.",
                "No clause detection. No nc_type.",
                "If unsure, default to MAIN."
            ],
            "region_labels": self.REGION_LABELS,
            "region_definitions": {
                "COVER": "Front/title pages before main body. Contains contract name, metadata, and parties info.",
                "TOC": "Table of contents listing article/section titles and page numbers.",
                "MAIN": "Core body text of contract: substantive provisions.",
                "APPENDIX": "Annexes/attachments/schedules after the main body.",
                "SIGN": "Signature blocks, seals, signatories, signing dates."
            },
            "input_format": {
                "window_text": window_text
            },
            "output_format": {
                "spans": [
                    {
                        "start": "int",
                        "end": "int",
                        "region": "COVER | TOC | MAIN | APPENDIX | SIGN"
                    }
                ]
            },
            "constraints": [
                "JSON only.",
                "Spans must be ordered and not overlap.",
                "Do not quote window_text."
            ]
        }
        
        try:
            # 调用LLM API，如果没有LLM服务则回退到规则方法
            result = await self._call_llm_api(prompt)
            return {"pipeline": "region", "window": window, "result": result}
        except Exception as e:
            logger.error(f"区域管线处理失败: {str(e)}")
            return {"pipeline": "region", "window": window, "result": []}
    
    async def _pipeline_nc_type_labeling(self, window: list[dict[str, Any]]) -> dict[str, Any]:
        """
        管线2：结构/格式判断
        根据region给每段选nc_type
        
        Args:
            window: 窗口段落列表
            
        Returns:
            NC_TYPE标注结果
        """
        window_text = self._concatenate_window_text(window)
        
        # 先获取区域标注（在实际应用中应该等待管线1完成）
        region_spans = self._mock_region_labeling(window)
        
        # 构建NC_TYPE识别的prompt
        prompt = {
            "task": "contract_nctype_labeling",
            "instruction": [
                "You receive window_text and region-labeled spans.",
                "Assign nc_type strictly based on region + visible structure.",
                "Do NOT change start, end, or region.",
                "If unsure, assign null."
            ],
            "allowed_nc_types": self.NC_TYPE_MAPPING,
            "nc_type_definitions": {
                "TITLE": "This span is a heading/title of contract, a section, a clause, or an appendix.",
                "PARTIES": "This span lists or describes party information: names, addresses, contacts, signature lines.",
                "CLAUSE_BODY": "Substantive clause text stating rights, obligations, responsibilities, conditions.",
                "null": "Not TITLE, not PARTIES, not CLAUSE_BODY."
            },
            "input_format": {
                "window_text": window_text,
                "spans": region_spans
            },
            "output_format": {
                "spans": [
                    {
                        "start": "same",
                        "end": "same",
                        "region": "same",
                        "nc_type": "TITLE | PARTIES | CLAUSE_BODY | null"
                    }
                ]
            },
            "constraints": [
                "JSON only.",
                "Do not add or remove spans."
            ]
        }
        
        try:
            # 调用LLM API，如果没有LLM服务则回退到规则方法
            result = await self._call_llm_api(prompt)
            return {"pipeline": "nc_type", "window": window, "result": result}
        except Exception as e:
            logger.error(f"NC_TYPE管线处理失败: {str(e)}")
            return {"pipeline": "nc_type", "window": window, "result": []}
    
    async def _pipeline_semantic_clause_detection(self, window: list[dict[str, Any]]) -> dict[str, Any]:
        """
        管线3：语义是否条款
        纯语义判断，这段内容，看上去是不是一条合同条款
        
        Args:
            window: 窗口段落列表
            
        Returns:
            语义角色标注结果
        """
        window_text = self._concatenate_window_text(window)
        
        # 构建语义条款检测的prompt
        prompt = {
            "task": "contract_clause_semantic_detection",
            "instruction": [
                "Decide if each span is a contract clause based on meaning only.",
                "A clause states rights, obligations, responsibilities, prohibitions, conditions, or definitions.",
                "Descriptive or administrative text is NON_CLAUSE.",
                "If unsure, choose NON_CLAUSE."
            ],
            "labels": self.ROLE_LABELS,
            "input_format": {
                "window_text": window_text,
                "spans": [{"start": 0, "end": len(window_text)}]  # 简化为整个窗口作为一个span
            },
            "output_format": {
                "spans": [
                    {
                        "start": "same",
                        "end": "same",
                        "role": "CLAUSE | NON_CLAUSE"
                    }
                ]
            },
            "constraints": [
                "Use meaning only. Ignore region and nc_type.",
                "Do not modify start/end.",
                "JSON only."
            ]
        }
        
        try:
            # 调用LLM API，如果没有LLM服务则回退到规则方法
            result = await self._call_llm_api(prompt)
            return {"pipeline": "semantic", "window": window, "result": result}
        except Exception as e:
            logger.error(f"语义管线处理失败: {str(e)}")
            return {"pipeline": "semantic", "window": window, "result": []}
    
    async def _call_llm_api(self, prompt: dict[str, Any]) -> list[dict[str, Any]]:
        """
        调用LLM API进行标注
        
        Args:
            prompt: 包含任务、指令和输入数据的提示
            
        Returns:
            标注结果
        """
        # 如果没有LLM服务，使用基于规则的简化方法
        if not self.llm_service:
            return self._rule_based_llm_fallback(prompt)
        
        # 实际调用LLM
        try:
            prompt_str = json.dumps(prompt, ensure_ascii=False)
            response = self.llm_service.generate(prompt_str)
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM API调用失败: {str(e)}")
            # 回退到基于规则的方法
            return self._rule_based_llm_fallback(prompt)
    
    def _rule_based_llm_fallback(self, prompt: dict[str, Any]) -> list[dict[str, Any]]:
        """
        基于规则的简化标注（用于没有LLM的情况）
        
        Args:
            prompt: 包含任务、指令和输入数据的提示
            
        Returns:
            模拟的标注结果
        """
        task = prompt.get("task", "")
        
        if task == "contract_region_labeling":
            # 区域标注回退
            return self._mock_region_labeling_from_prompt(prompt)
        elif task == "contract_nctype_labeling":
            # NC_TYPE标注回退
            return self._mock_nc_type_labeling_from_prompt(prompt)
        elif task == "contract_clause_semantic_detection":
            # 语义条款检测回退
            return self._mock_semantic_clause_detection_from_prompt(prompt)
        else:
            # 默认返回空结果
            return []
    
    def _mock_region_labeling_from_prompt(self, prompt: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从提示中提取窗口内容并模拟区域标注
        
        Args:
            prompt: 包含任务、指令和输入数据的提示
            
        Returns:
            模拟的区域标注结果
        """
        window_text = prompt.get("input_format", {}).get("window_text", "")
        
        # 简单的规则判断
        results = []
        text_lines = window_text.split("\n")
        current_pos = 0
        
        for line in text_lines:
            if not line.strip():
                current_pos += len(line) + 1
                continue
                
            region = self._rule_based_region_detection(line)
            
            results.append({
                "start": current_pos,
                "end": current_pos + len(line),
                "region": region
            })
            
            current_pos += len(line) + 1
        
        return results
    
    def _mock_nc_type_labeling_from_prompt(self, prompt: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从提示中提取窗口内容并模拟NC_TYPE标注
        
        Args:
            prompt: 包含任务、指令和输入数据的提示
            
        Returns:
            模拟的NC_TYPE标注结果
        """
        input_format = prompt.get("input_format", {})
        window_text = input_format.get("window_text", "")
        spans = input_format.get("spans", [])
        
        results = []
        
        for span in spans:
            start = span.get("start", 0)
            end = span.get("end", len(window_text))
            region = span.get("region", "MAIN")
            
            # 提取span对应的文本
            if start < len(window_text) and end <= len(window_text):
                text = window_text[start:end]
            else:
                text = ""
            
            # 基于区域和文本内容判断NC_TYPE
            nc_type = self._rule_based_nc_type_detection(text, region)
            
            results.append({
                "start": start,
                "end": end,
                "region": region,
                "nc_type": nc_type
            })
        
        return results
    
    def _mock_semantic_clause_detection_from_prompt(self, prompt: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从提示中提取窗口内容并模拟语义条款检测
        
        Args:
            prompt: 包含任务、指令和输入数据的提示
            
        Returns:
            模拟的语义条款检测结果
        """
        input_format = prompt.get("input_format", {})
        window_text = input_format.get("window_text", "")
        spans = input_format.get("spans", [])
        
        results = []
        
        for span in spans:
            start = span.get("start", 0)
            end = span.get("end", len(window_text))
            
            # 提取span对应的文本
            if start < len(window_text) and end <= len(window_text):
                text = window_text[start:end]
            else:
                text = ""
            
            # 基于规则判断是否是条款
            role = self._rule_based_semantic_detection(text)
            
            results.append({
                "start": start,
                "end": end,
                "role": role
            })
        
        return results
    
    def _parse_llm_response(self, response: str) -> list[dict[str, Any]]:
        """
        解析LLM响应，提取spans
        
        Args:
            response: LLM的响应字符串
            
        Returns:
            解析后的spans列表
        """
        try:
            # 尝试解析JSON
            result = json.loads(response)
            if "spans" in result:
                return result["spans"]
            else:
                logger.warning(f"LLM response doesn't contain 'spans': {response}")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            return []

    def _concatenate_window_text(self, window: list[dict[str, Any]]) -> str:
        """
        将窗口中的段落连接成一段连续文本
        
        Args:
            window: 窗口段落列表
            
        Returns:
            连接后的文本
        """
        return " ".join([seg.get("text", "") for seg in window])
    
    def _mock_region_labeling(self, window: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        模拟区域标注结果（用于演示）
        
        Args:
            window: 窗口段落列表
            
        Returns:
            模拟的区域标注结果
        """
        results = []
        current_pos = 0
        
        for seg in window:
            text = seg.get("text", "")
            seg_id = seg.get("id")
            
            # 简单的规则判断（模拟LLM的判断过程）
            region = self._rule_based_region_detection(text)
            
            results.append({
                "seg_id": seg_id,
                "start": current_pos,
                "end": current_pos + len(text),
                "region": region
            })
            
            current_pos += len(text) + 1  # +1 for space
        
        return results
    
    def _rule_based_region_detection(self, text: str) -> str:
        """
        基于规则的区域检测（模拟LLM判断）
        
        Args:
            text: 文本内容
            
        Returns:
            区域标签
        """
        text = text.strip().lower()
        
        # 检查目录特征
        if any(keyword in text for keyword in ["目录", "目 录", "table of contents"]):
            return "TOC"
        
        # 检查封面特征
        if any(keyword in text for keyword in ["合同", "协议", "协议编号", "甲方", "乙方", "签订日期", "签订地点"]):
            return "COVER"
        
        # 检查签字页特征
        if any(keyword in text for keyword in ["签字", "签署", "法定代表人", "授权代表", "日期"]):
            return "SIGN"
        
        # 检查附件特征
        if any(keyword in text for keyword in ["附件", "附录", "补充协议", "附表"]):
            return "APPENDIX"
        
        # 默认返回MAIN
        return "MAIN"
    
    def _mock_nc_type_labeling(self, window: list[dict[str, Any]], region_spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        模拟NC_TYPE标注结果（用于演示）
        
        Args:
            window: 窗口段落列表
            region_spans: 区域标注结果
            
        Returns:
            模拟的NC_TYPE标注结果
        """
        results = []
        
        for seg in window:
            seg_id = seg.get("id")
            text = seg.get("text", "")
            
            # 找到对应的区域标注
            region = "MAIN"  # 默认值
            for span in region_spans:
                if span.get("seg_id") == seg_id:
                    region = span.get("region", "MAIN")
                    break
            
            # 基于区域和文本内容判断NC_TYPE
            nc_type = self._rule_based_nc_type_detection(text, region)
            
            results.append({
                "seg_id": seg_id,
                "region": region,
                "nc_type": nc_type
            })
        
        return results
    
    def _rule_based_nc_type_detection(self, text: str, region: str) -> str | None:
        """
        基于规则的NC_TYPE检测（模拟LLM判断）
        
        Args:
            text: 文本内容
            region: 区域标签
            
        Returns:
            NC_TYPE标签
        """
        text = text.strip().lower()
        
        if region == "COVER":
            if any(keyword in text for keyword in ["合同名称", "协议名称", "标题"]):
                return "TITLE"
            elif any(keyword in text for keyword in ["甲方", "乙方", "当事人", "公司"]):
                return "PARTIES"
            else:
                return None
        
        elif region == "TOC":
            return None
        
        elif region == "MAIN":
            if any(keyword in text for keyword in ["第", "条", "款", "章", "节"]):
                return "TITLE"
            elif any(keyword in text for keyword in ["约定", "应当", "有权", "义务", "责任", "禁止", "定义"]):
                return "CLAUSE_BODY"
            else:
                return None
        
        elif region == "APPENDIX":
            if any(keyword in text for keyword in ["附件", "附录", "补充"]):
                return "TITLE"
            elif any(keyword in text for keyword in ["约定", "应当", "有权", "义务", "责任", "禁止", "定义"]):
                return "CLAUSE_BODY"
            else:
                return None
        
        elif region == "SIGN":
            if any(keyword in text for keyword in ["甲方", "乙方", "当事人", "公司"]):
                return "PARTIES"
            elif any(keyword in text for keyword in ["签字", "签署"]):
                return "TITLE"
            else:
                return None
        
        return None
    
    def _mock_semantic_clause_detection(self, window: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        模拟语义条款检测结果（用于演示）
        
        Args:
            window: 窗口段落列表
            
        Returns:
            模拟的语义条款检测结果
        """
        results = []
        
        for seg in window:
            seg_id = seg.get("id")
            text = seg.get("text", "")
            
            # 基于规则判断是否是条款（模拟LLM判断）
            role = self._rule_based_semantic_detection(text)
            
            results.append({
                "seg_id": seg_id,
                "role_llm": role
            })
        
        return results
    
    def _rule_based_semantic_detection(self, text: str) -> str:
        """
        基于规则的语义条款检测（模拟LLM判断）
        
        Args:
            text: 文本内容
            
        Returns:
            角色标签
        """
        text = text.strip().lower()
        
        # 检查条款特征
        clause_keywords = [
            "约定", "应当", "有权", "义务", "责任", "禁止", "定义",
            "权利", "承诺", "保证", "赔偿", "违约", "解除", "终止",
            "履行", "支付", "交付", "提供", "承担", "遵守", "符合"
        ]
        
            # 如果文本中包含足够的条款关键词，则认为是条款
        if sum(1 for keyword in clause_keywords if keyword in text) >= 2:
            return "CLAUSE"
        
        # 检查是否包含条款编号
        clause_patterns = [
            r'第[一二三四五六七八九十\d]+条',
            r'^\d+[\.\s]',
            r'^\d+\.\d+',
        ]
        
        for pattern in clause_patterns:
            if re.search(pattern, text):
                return "CLAUSE"
        
        return "NON_CLAUSE"
    
    def _merge_pipeline_results(self, pipeline_results: list[dict[str, Any]], original_segments: list[dict[str, Any]], window_size: int = 0, overlap: int = 0) -> list[dict[str, Any]]:
        """
        合并三个管线的标注结果
        
        Args:
            pipeline_results: 三个管线的标注结果
            original_segments: 原始段落列表
            window_size: 窗口大小
            overlap: 窗口重叠
            
        Returns:
            合并后的标注结果
        """
        # 按管线分组结果
        region_results = []
        nc_type_results = []
        semantic_results = []
        
        for result in pipeline_results:
            if isinstance(result, dict):
                pipeline = result.get("pipeline")
                if pipeline == "region":
                    region_results.append(result)
                elif pipeline == "nc_type":
                    nc_type_results.append(result)
                elif pipeline == "semantic":
                    semantic_results.append(result)
        
        # 收集所有预测结果
        all_region_predictions = defaultdict(list)
        all_nc_type_predictions = defaultdict(list)
        all_semantic_predictions = defaultdict(list)
        
        # 统计每个段落的所有预测结果
        for result in region_results:
            for pred in result.get("result", []):
                seg_id = pred.get("seg_id")
                if seg_id:
                    all_region_predictions[seg_id].append(pred.get("region"))
        
        for result in nc_type_results:
            for pred in result.get("result", []):
                seg_id = pred.get("seg_id")
                if seg_id:
                    all_nc_type_predictions[seg_id].append({
                        "region": pred.get("region"),
                        "nc_type": pred.get("nc_type")
                    })
        
        for result in semantic_results:
            for pred in result.get("result", []):
                seg_id = pred.get("seg_id")
                if seg_id:
                    all_semantic_predictions[seg_id].append(pred.get("role_llm"))
        
        # 为每个段落生成最终标注
        final_results = []
        for segment in original_segments:
            seg_id = segment.get("id")
            
            # 获取预测结果
            region_preds = all_region_predictions.get(seg_id, ["MAIN"])
            nc_type_preds = all_nc_type_predictions.get(seg_id, [{"region": "MAIN", "nc_type": None}])
            semantic_preds = all_semantic_predictions.get(seg_id, ["NON_CLAUSE"])
            
            # 选择最常见的预测结果
            region = max(set(region_preds), key=region_preds.count) if region_preds else "MAIN"
            
            # 对于nc_type，选择最常见的预测
            nc_type_values = [pred.get("nc_type") for pred in nc_type_preds if pred.get("nc_type") is not None]
            nc_type = max(set(nc_type_values), key=nc_type_values.count) if nc_type_values else None
            
            # 对于role，选择最常见的预测
            role = max(set(semantic_preds), key=semantic_preds.count) if semantic_preds else "NON_CLAUSE"
            
            # 构建最终结果
            final_result = {
                **segment,
                "region": region,
                "nc_type": nc_type,
                "role": role,
                "original_text": segment.get("original_text", segment.get("text", ""))
            }
            
            final_results.append(final_result)
        
        return final_results
    
    def _calculate_clause_scores(self, merged_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        计算条款分数
        给内容（role）、区域（region）、格式（nc_type）三类信号赋权，加权求和形成一个"条款分数"
        
        Args:
            merged_results: 合并后的标注结果
            
        Returns:
            带有条款分数的标注结果
        """
        scored_results = []
        
        for result in merged_results:
            role = result.get("role", "NON_CLAUSE")
            region = result.get("region", "MAIN")
            nc_type = result.get("nc_type", None)
            
            # 计算role分数
            role_score = 4 if role == "CLAUSE" else 0
            
            # 计算region分数
            region_scores = {
                "MAIN": 2,       # 主体部分更可能是条款
                "COVER": 0,      # 封面不太可能是条款
                "TOC": 0,        # 目录不是条款
                "APPENDIX": 1,   # 附件有些可能是条款
                "SIGN": 0        # 签字页不是条款
            }
            region_score = region_scores.get(region, 0)
            
            # 计算nc_type分数（简化版）
            nc_type_scores = {
                "TITLE": 1,           # 标题本身不一定是条款内容
                "PARTIES": 0,         # 当事人信息不是条款
                "CLAUSE_BODY": 4,     # 条款正文是典型的条款
                None: 1               # 未确定类型的内容
            }
            nc_type_score = nc_type_scores.get(nc_type, 0)
            
            # 加权求和计算总分数
            total_score = (
                role_score * self.weights["role"] +
                region_score * self.weights["region"] +
                nc_type_score * self.weights["nc_type"]
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
            
            # 添加分数到结果中
            scored_result = {
                **result,
                "score": score,
                "score_float": round(total_score, 2)  # 保留原始浮点分数用于调试
            }
            
            scored_results.append(scored_result)
        
        return scored_results
    
    def merge_segments_by_clause(self, scored_segments: list[dict[str, Any]], score_threshold: str = "1") -> list[dict[str, Any]]:
        """
        根据条款分数合并段落为条款单元
        
        Args:
            scored_segments: 带有分数的段落列表
            score_threshold: 分数阈值，低于此值的段落不视为条款
            
        Returns:
            合并后的条款单元列表
        """
        # 过滤出分数不低于阈值的段落
        clause_segments = [
            seg for seg in scored_segments 
            if seg.get("score", "0") >= score_threshold
        ]
        
        # 按order_index排序
        sorted_segments = sorted(clause_segments, key=lambda x: x.get("order_index", 0))
        
        clause_units = []
        current_unit = None
        
        for seg in sorted_segments:
            # 判断是否需要开始新的条款单元
            nc_type = seg.get("nc_type")
            
            # 如果是标题或者当前没有活动单元，则开始新单元
            if nc_type == "TITLE" or current_unit is None:
                # 保存当前单元（如果有）
                if current_unit:
                    clause_units.append(current_unit)
                
                # 开始新单元
                current_unit = {
                    "id": f"clause_{len(clause_units)}",
                    "segment_ids": [seg.get("id")],
                    "texts": [seg.get("original_text", seg.get("text", ""))],
                    "order_index": seg.get("order_index"),
                    "region": seg.get("region"),
                    "nc_type": seg.get("nc_type"),
                    "role": seg.get("role"),
                    "score": seg.get("score"),
                    "score_float": seg.get("score_float", 0)
                }
            else:
                # 添加到当前单元
                seg_id = seg.get("id")
                text = seg.get("original_text", seg.get("text", ""))
                
                # 确保segment_ids和texts是列表
                segment_ids = current_unit.get("segment_ids")
                if segment_ids is None or not isinstance(segment_ids, list):
                    current_unit["segment_ids"] = [seg_id]
                else:
                    # 使用列表操作避免类型检查器问题
                    current_unit["segment_ids"] = segment_ids + [seg_id]
                
                # 确保texts是列表
                texts = current_unit.get("texts")
                if texts is None or not isinstance(texts, list):
                    current_unit["texts"] = [text]
                else:
                    # 使用列表操作避免类型检查器问题
                    current_unit["texts"] = texts + [text]
                
                # 更新分数（取最低分）
                current_unit["score_float"] = min(
                    current_unit["score_float"], 
                    seg.get("score_float", 0)
                )
                
                # 重新计算整数分数
                total_score = current_unit["score_float"]
                if total_score >= 3.5:
                    current_unit["score"] = "4"
                elif total_score >= 2.5:
                    current_unit["score"] = "3"
                elif total_score >= 1.5:
                    current_unit["score"] = "2"
                elif total_score >= 0.5:
                    current_unit["score"] = "1"
                else:
                    current_unit["score"] = "0"
        
        # 处理最后一个未完成的单元
        if current_unit:
            clause_units.append(current_unit)
        
        # 合并每个单元的文本
        for unit in clause_units:
            unit["text"] = "\n".join(unit["texts"])
            unit.pop("texts", None)  # 移除临时字段
        
        return clause_units