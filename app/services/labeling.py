"""
三管线标签系统
独立处理region、nc_type和role三个维度的标注，最后合并加权评分
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.core.logger import logger
from app.core.config import settings


class LabelingService:
    """三管线标签系统"""
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        
        # 定义各类标签的权重
        self.weights = {
            "region": 0.3,
            "nc_type": 0.3,
            "role": 0.4
        }
        
        # 详细nc_type定义
        self.NC_TYPE_COVER = {
            "COVER_TITLE": "合同名称、封面大标题",
            "TOC": "目录",
            "COVER_META": "编号、版本号、日期",
            "COVER_PARTIES": "封面处的甲方/乙方信息",
            "COVER_OTHER": "封面杂项（二维码、水印等）"
        }
        
        self.NC_TYPE_MAIN = {
            "TITLE": "正文标题（章节/条款标题）",
            "CLAUSE_BODY": "条款正文（需要进入向量库）",
            "RECITAL": "鉴于/前言段落",
            "MAIN_OTHER": "正文内部但不属于条款的其他内容"
        }
        
        self.NC_TYPE_APPENDIX = {
            "APPENDIX_TITLE": "附件/附录标题",
            "APPENDIX_BODY": "附件正文内容",
            "APPENDIX_OTHER": "附件内的其他内容"
        }
        
        self.NC_TYPE_SIGN = {
            "SIGN_PAGE_TITLE": "签字页标题",
            "SIGN_PAGE_PARTY": "签署方名称（甲方/乙方）",
            "SIGN_PAGE_BODY": "签名栏、盖章区、日期等内容"
        }
        
        # 获取所有nc_type定义
        self.NC_TYPE_DEFINITIONS = {}
        self.NC_TYPE_DEFINITIONS.update(self.NC_TYPE_COVER)
        self.NC_TYPE_DEFINITIONS.update(self.NC_TYPE_MAIN)
        self.NC_TYPE_DEFINITIONS.update(self.NC_TYPE_APPENDIX)
        self.NC_TYPE_DEFINITIONS.update(self.NC_TYPE_SIGN)
        
        # Pipeline提示词
        self.region_prompt = """
        {
          "task": "contract_region_labeling",
          "instruction": [
            "Segment window_text into non-overlapping spans.",
            "Assign ONLY a region label to each span.",
            "No clause detection. No nc_type.",
            "If unsure, default to MAIN."
          ],
          "region_labels": ["COVER", "TOC", "MAIN", "APPENDIX", "SIGN"],
          "region_definitions": {
            "COVER": "Front/title pages before the main body. Contains contract name, metadata, and parties info.",
            "TOC": "Table of contents listing article/section titles and page numbers.",
            "MAIN": "Core body text of the contract: substantive provisions.",
            "APPENDIX": "Annexes/attachments/schedules after the main body.",
            "SIGN": "Signature blocks, seals, signatories, signing dates."
          },
          "input_format": {
            "window_text": "<PUT_WINDOW_TEXT_HERE>"
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
        """
        
        self.nc_type_prompt = """
        {
          "task": "contract_nctype_labeling",
          "instruction": [
            "You receive window_text and region-labeled spans.",
            "Assign nc_type strictly based on region + visible structure.",
            "Do NOT change start, end, or region.",
            "If unsure, assign null."
          ],
          "allowed_nc_types": {
            "COVER": ["TITLE", "PARTIES", null],
            "TOC": [null],
            "MAIN": ["TITLE", "CLAUSE_BODY", null],
            "APPENDIX": ["TITLE", "CLAUSE_BODY", null],
            "SIGN": ["PARTIES", "TITLE", null]
          },
          "nc_type_definitions": {
            "TITLE": "This span is a heading/title of a contract, a section, a clause, or an appendix.",
            "PARTIES": "This span lists or describes party information: names, addresses, contacts, signature lines.",
            "CLAUSE_BODY": "Substantive clause text stating rights, obligations, responsibilities, conditions.",
            "null": "Not TITLE, not PARTIES, not CLAUSE_BODY."
          },
          "input_format": {
            "window_text": "<PUT_WINDOW_TEXT_HERE>",
            "spans": [
              {
                "start": "int",
                "end": "int",
                "region": "COVER | TOC | MAIN | APPENDIX | SIGN"
              }
            ]
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
        """
        
        self.role_prompt = """
        {
          "task": "contract_clause_semantic_detection",
          "instruction": [
            "Decide if each span is a contract clause based on meaning only.",
            "A clause states rights, obligations, responsibilities, prohibitions, conditions, or definitions.",
            "Descriptive or administrative text is NON_CLAUSE.",
            "If unsure, choose NON_CLAUSE."
          ],
          "labels": ["CLAUSE", "NON_CLAUSE"],
          "input_format": {
            "window_text": "<PUT_WINDOW_TEXT_HERE>",
            "spans": [
              {
                "start": "int",
                "end": "int"
              }
            ]
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
        """
    
    def label_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        对段落片段进行三管线标注
        
        Args:
            segments: 包含id和text的段落列表
            
        Returns:
            标注后的段落列表，包含region、nc_type、role和score字段
        """
        if not segments:
            return []
        
        # 将段落连接成文本，记录位置信息
        text_with_positions = self._merge_segments_with_positions(segments)
        full_text = text_with_positions["text"]
        positions = text_with_positions["positions"]
        
        # 分割为窗口，避免上下文过长
        windows = self._split_into_windows(full_text, positions)
        
        # 并行处理三个管线
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交任务
            region_future = executor.submit(self._process_region_pipeline, windows)
            nc_type_future = executor.submit(self._process_nc_type_pipeline, windows)
            role_future = executor.submit(self._process_role_pipeline, windows)
            
            # 等待结果
            region_results = region_future.result()
            nc_type_results = nc_type_future.result()
            role_results = role_future.result()
        
        # 合并结果
        labeled_segments = self._merge_labeling_results(
            segments, region_results, nc_type_results, role_results
        )
        
        return labeled_segments
    
    def _merge_segments_with_positions(self, segments: list[dict[str, Any]]) -> dict[str, Any]:
        """合并段落并记录位置信息"""
        text_parts = []
        positions = []
        current_pos = 0
        
        for segment in segments:
            segment_text = segment["text"]
            text_parts.append(segment_text)
            
            start = current_pos
            end = start + len(segment_text)
            positions.append({
                "segment_id": segment["id"],
                "start": start,
                "end": end
            })
            
            # 添加分隔符
            current_pos = end
            if segment != segments[-1]:  # 不是最后一个
                separator = "\n"
                text_parts.append(separator)
                current_pos += len(separator)
        
        return {
            "text": "".join(text_parts),
            "positions": positions
        }
    
    def _split_into_windows(self, text: str, positions: list[dict[str, Any]], window_size: int = 4000, overlap: int = 200) -> list[dict[str, Any]]:
        """将文本分割为重叠的窗口"""
        windows = []
        text_len = len(text)
        
        start = 0
        while start < text_len:
            end = min(start + window_size, text_len)
            
            # 获取当前窗口中的段落位置
            window_positions = [
                pos for pos in positions 
                if pos["start"] >= start and pos["end"] <= end
            ]
            
            windows.append({
                "text": text[start:end],
                "global_start": start,
                "global_end": end,
                "positions": window_positions
            })
            
            # 移动窗口，保留重叠部分
            start = end - overlap if end < text_len else text_len
        
        return windows
    
    def _process_region_pipeline(self, windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """处理区域标注管线"""
        results = []
        
        for window in windows:
            window_text = window["text"]
            window_positions = window["positions"]
            
            # 生成提示
            prompt = self.region_prompt.replace("<PUT_WINDOW_TEXT_HERE>", window_text)
            
            # 调用LLM
            try:
                response = self._call_llm(prompt)
                labeled_spans = self._parse_llm_response(response)
                
                # 映射回段落
                for position in window_positions:
                    segment_id = position["segment_id"]
                    start, end = position["start"] - window["global_start"], position["end"] - window["global_start"]
                    
                    # 查找包含此位置的span
                    region = self._find_span_label(labeled_spans, start, end, "region")
                    if not region:
                        region = "MAIN"  # 默认值
                    
                    results.append({
                        "segment_id": segment_id,
                        "region": region
                    })
            except Exception as e:
                logger.error(f"Error in region pipeline: {str(e)}")
                # 发生错误时，使用默认值
                for position in window_positions:
                    results.append({
                        "segment_id": position["segment_id"],
                        "region": "MAIN"
                    })
        
        return results
    
    def _process_nc_type_pipeline(self, windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """处理非条款类型标注管线"""
        results = []
        
        for window in windows:
            window_text = window["text"]
            window_positions = window["positions"]
            
            # 首先获取region信息
            region_spans = []
            for position in window_positions:
                segment_id = position["segment_id"]
                start, end = position["start"] - window["global_start"], position["end"] - window["global_start"]
                region_spans.append({
                    "start": start,
                    "end": end,
                    "region": "MAIN"  # 默认值，实际应从region管线获取
                })
            
            # 生成提示
            input_json = {
                "window_text": window_text,
                "spans": region_spans
            }
            prompt = self.nc_type_prompt.replace(
                "<PUT_WINDOW_TEXT_HERE>", 
                json.dumps(input_json, ensure_ascii=False)
            )
            
            # 调用LLM
            try:
                response = self._call_llm(prompt)
                labeled_spans = self._parse_llm_response(response)
                
                # 映射回段落
                for position in window_positions:
                    segment_id = position["segment_id"]
                    start, end = position["start"] - window["global_start"], position["end"] - window["global_start"]
                    
                    # 查找包含此位置的span
                    nc_type = self._find_span_label(labeled_spans, start, end, "nc_type")
                    
                    results.append({
                        "segment_id": segment_id,
                        "nc_type": nc_type
                    })
            except Exception as e:
                logger.error(f"Error in nc_type pipeline: {str(e)}")
                # 发生错误时，使用默认值
                for position in window_positions:
                    results.append({
                        "segment_id": position["segment_id"],
                        "nc_type": None
                    })
        
        return results
    
    def _process_role_pipeline(self, windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """处理角色标注管线"""
        results = []
        
        for window in windows:
            window_text = window["text"]
            window_positions = window["positions"]
            
            # 生成提示
            spans = []
            for position in window_positions:
                start, end = position["start"] - window["global_start"], position["end"] - window["global_start"]
                spans.append({
                    "start": start,
                    "end": end
                })
            
            input_json = {
                "window_text": window_text,
                "spans": spans
            }
            prompt = self.role_prompt.replace(
                "<PUT_WINDOW_TEXT_HERE>", 
                json.dumps(input_json, ensure_ascii=False)
            )
            
            # 调用LLM
            try:
                response = self._call_llm(prompt)
                labeled_spans = self._parse_llm_response(response)
                
                # 映射回段落
                for position in window_positions:
                    segment_id = position["segment_id"]
                    start, end = position["start"] - window["global_start"], position["end"] - window["global_start"]
                    
                    # 查找包含此位置的span
                    role = self._find_span_label(labeled_spans, start, end, "role")
                    if not role:
                        role = "NON_CLAUSE"  # 默认值
                    
                    results.append({
                        "segment_id": segment_id,
                        "role": role
                    })
            except Exception as e:
                logger.error(f"Error in role pipeline: {str(e)}")
                # 发生错误时，使用默认值
                for position in window_positions:
                    results.append({
                        "segment_id": position["segment_id"],
                        "role": "NON_CLAUSE"
                    })
        
        return results
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM服务"""
        # 如果没有LLM服务，使用基于规则的简化方法
        if not self.llm_service:
            return self._rule_based_labeling(prompt)
        
        # 实际调用LLM
        return self.llm_service.generate(prompt)
    
    def _rule_based_labeling(self, prompt: str) -> str:
        """基于规则的简化标注（用于没有LLM的情况）"""
        # 这是一个简化的实现，实际应该使用真实的LLM
        # 这里返回一个基本的JSON结构
        if "region" in prompt:
            # 区域标注
            return """{"spans": [{"start": 0, "end": 1000, "region": "MAIN"}]}"""
        elif "nc_type" in prompt:
            # 非条款类型标注
            return """{"spans": [{"start": 0, "end": 1000, "region": "MAIN", "nc_type": "TITLE"}]}"""
        else:
            # 角色标注
            return """{"spans": [{"start": 0, "end": 1000, "role": "NON_CLAUSE"}]}"""
    
    def _parse_llm_response(self, response: str) -> list[dict[str, Any]]:
        """解析LLM响应，提取spans"""
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
    
    def _find_span_label(self, spans: list[dict[str, Any]], start: int, end: int, label_key: str) -> Any:
        """查找包含给定位置区间的span标签"""
        for span in spans:
            if span["start"] <= start and span["end"] >= end:
                return span.get(label_key)
        return None
    
    def _merge_labeling_results(
        self,
        segments: list[dict[str, Any]],
        region_results: list[dict[str, Any]],
        nc_type_results: list[dict[str, Any]],
        role_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """合并三个管线的结果，计算加权分数"""
        # 创建segment_id到结果的映射
        region_map = {r["segment_id"]: r["region"] for r in region_results}
        nc_type_map = {r["segment_id"]: r["nc_type"] for r in nc_type_results}
        role_map = {r["segment_id"]: r["role"] for r in role_results}
        
        labeled_segments = []
        
        for segment in segments:
            segment_id = segment["id"]
            
            # 获取标签
            region = region_map.get(segment_id, "MAIN")
            nc_type = nc_type_map.get(segment_id)
            role = role_map.get(segment_id, "NON_CLAUSE")
            
            # 计算置信度分数（1-4）
            score = self._calculate_confidence_score(region, nc_type, role)
            
            labeled_segments.append({
                "id": segment_id,
                "text": segment["text"],
                "region": region,
                "nc_type": nc_type,
                "role": role,
                "score": score
            })
        
        return labeled_segments
    
    def _calculate_confidence_score(self, region: str, nc_type: str | None, role: str) -> int:
        """根据三个维度的标签计算置信度分数"""
        score = 0
        
        # 权重
        region_weight = self.weights["region"]
        nc_type_weight = self.weights["nc_type"]
        role_weight = self.weights["role"]
        
        # 根据标签给分
        region_score = 0
        if region == "MAIN":
            region_score = 4
        elif region in ["COVER", "APPENDIX"]:
            region_score = 3
        elif region in ["TOC", "SIGN"]:
            region_score = 2
        else:
            region_score = 1
        
        nc_type_score = 0
        if nc_type == "CLAUSE_BODY":
            nc_type_score = 4
        elif nc_type == "TITLE":
            nc_type_score = 3
        elif nc_type == "PARTIES":
            nc_type_score = 2
        elif nc_type is None:
            nc_type_score = 1
        else:
            nc_type_score = 1
        
        role_score = 0
        if role == "CLAUSE":
            role_score = 4
        else:
            role_score = 1
        
        # 加权求和并四舍五入
        weighted_score = (region_score * region_weight + 
                         nc_type_score * nc_type_weight + 
                         role_score * role_weight)
        
        return max(1, min(4, int(round(weighted_score))))