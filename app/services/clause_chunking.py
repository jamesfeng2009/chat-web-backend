"""
条款切分服务
基于结构特征和语义相似度的智能切分算法
"""
import numpy as np
from dataclasses import dataclass
import regex
from sentence_transformers import SentenceTransformer

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Block:
    """文本块数据结构"""
    text: str
    indent: int = 0  # 建议用像素或空格数，越大表示越深
    page_num: int = 0
    bbox: tuple[int, int, int, int] | None = None
    
    @classmethod
    def from_text_block(cls, text_block):
        """从TextBlock转换为Block"""
        return cls(
            text=text_block.text,
            indent=text_block.level,
            page_num=text_block.page_num,
            bbox=text_block.bbox
        )


class ClauseChunkingService:
    """条款切分服务"""
    
    def __init__(self):
        # 初始化模型（延迟加载）
        self._emb_model = None
        self._cross_encoder = None
        self.model_configs = {
            "default": {
                "embedding_model": "BAAI/bge-m3",  # 多语，归一化开启
                "cross_encoder": "cross-encoder/ms-marco-MiniLM-L-12-v2"
            }
        }
        
        # ------------------- 形态判定（无关键词，仅形态/符号/标点） -------------------
        # 序号形态： (1) 1. 1) I. i) A. a) ① ② … 等
        self._RE_ENUM = re.compile(r"""
            ^\s*
            (?:                                  # 多类编号前缀
                [\(\[\{]?\s*(?:\d{1,3}|[ivxlcdm]{1,8}|[IVXLCDM]{1,8}|[a-zA-Z])\s*[\)\]\}]   # (1)  (iv)  (A)
              | (?:\d{1,3}|[ivxlcdm]{1,8}|[IVXLCDM]{1,8}|[a-zA-Z])\s*[.、]                  # 1.  I.  A.
              | [①-⑳⑴-⒇Ⓐ-Ⓩⓐ-ⓩ]                                                           # 圆圈序号等
            )
            (?:\s+|$)
        """, re.X)
        
        # 项目符号：常见 Unicode bullet（非穷举，基于符号类别）
        self._BULLETS = set("•‣⁃◦▪▫●○◆◇▶►▸▹▻▯▮■□－–—·∙・・❖✦✧")
    
    def _ensure_embedding_model(self):
        """确保嵌入模型已加载"""
        if self._emb_model is None:
            model_name = self.model_configs["default"]["embedding_model"]
            try:
                self._emb_model = SentenceTransformer(model_name)
                logger.info(f"Loaded embedding model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model {model_name}: {e}")
                raise
    
    def _ensure_cross_encoder(self):
        """确保交叉编码器已加载"""
        if self._cross_encoder is None:
            model_name = self.model_configs["default"]["cross_encoder"]
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder(model_name, max_length=256)
                logger.info(f"Loaded cross encoder model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load cross encoder model {model_name}: {e}")
                raise
    
    def embed_batch(self, texts: list[str], batch_size=64) -> np.ndarray:
        """批量文本嵌入"""
        if not texts: 
            return np.zeros((0,1), dtype=np.float32)
        
        self._ensure_embedding_model()
        return self._emb_model.encode(
            texts, batch_size=batch_size, convert_to_numpy=True, 
            normalize_embeddings=True, show_progress_bar=False
        ).astype(np.float32)
    
    def looks_bullet_char(self, s: str) -> bool:
        """检查是否为项目符号字符"""
        s = s.lstrip()
        return bool(s) and (s[0] in self._BULLETS)
    
    def is_enum_like(self, s: str) -> bool:
        """检查是否为枚举项"""
        if not s: return False
        return bool(self._RE_ENUM.search(s)) or self.looks_bullet_char(s)
    
    def is_heading_shape(self, b: Block) -> bool:
        """纯形态判断：短、标点收束、大小写占比、数字+分隔等"""
        t = (b.text or "").strip()
        if not t: return False
        # 很短的标题型
        if len(t) <= 8 and (t.endswith((':','：')) or re.search(r'[一二三四五六七八九十]+\s*[、.．)]?$', t)):
            return True
        # 中等长度，标点结束或带编号+短语
        if len(t) <= 60:
            if t.endswith((':','：')): return True
            if self._RE_ENUM.match(t) and len(t) <= 40: return True
            # 大写占比高或"词首大写率"较高
            letters = [c for c in t if c.isalpha()]
            if letters:
                up = sum(1 for c in letters if c.isupper())
                if up / max(1, len(letters)) >= 0.6: return True
        return False
    
    def ends_colon(self, s: str) -> bool:
        """检查是否以冒号结束"""
        return (s or "").rstrip().endswith((':','：'))
    
    def ends_soft(self, s: str) -> bool:
        """软结尾：逗号/分号/顿号/冒号 等，表示更可能续写"""
        return (s or "").rstrip().endswith(('，',',','；',';','、','：',':'))
    
    def unclosed_bracket(self, s: str) -> bool:
        """成对括号未闭合则更可能续写"""
        if not s: return False
        pairs = {'(':')','（':'）','[':']','【':'】','{':'}','〈':'〉','《':'》','<':'>'}
        cnt = 0
        for ch in s:
            if ch in pairs: cnt += 1
            elif any(ch == v for v in pairs.values()): cnt -= 1
        return cnt > 0
    
    def _post_fix_spans(self, spans: list[list[int]], blocks: list[Block], V: np.ndarray) -> list[list[int]]:
        """轻量二次修正：合并过短段；标题强切"""
        if not spans: return spans
        def cos(i,j):
            if i is None or j is None: return 0.0
            v = float(np.dot(V[i], V[j]))
            return v if np.isfinite(v) else 0.0

        # 标题强切：若某段第一行像标题，且段长>1且第二行不像枚举，则将标题单独成段
        fixed = []
        for span in spans:
            if len(span) >= 2 and self.is_heading_shape(blocks[span[0]]) and not self.is_enum_like(blocks[span[1]].text):
                fixed.append([span[0]])
                fixed.append(span[1:])
            else:
                fixed.append(span)
        spans = fixed

        # 合并极短段：单行且与相邻段头高度相似时合并到更相似一侧
        if len(spans) >= 2:
            merged = []
            i = 0
            while i < len(spans):
                span = spans[i]
                if len(span) == 1:
                    head_i = span[0]
                    left_sim = right_sim = -1.0
                    if i-1 >= 0:
                        left_head = spans[i-1][0]
                        left_sim = cos(head_i, left_head)
                    if i+1 < len(spans):
                        right_head = spans[i+1][0]
                        right_sim = cos(head_i, right_head)
                    if max(left_sim, right_sim) >= 0.60:
                        if left_sim >= right_sim and i-1 >= 0:
                            merged[-1].extend(span)  # 向左合
                        elif i+1 < len(spans):
                            spans[i+1] = span + spans[i+1]  # 向右合
                        i += 1
                        continue
                merged.append(span)
                i += 1
            spans = merged

        return spans
    
    def chunk_blocks(self, blocks: list[Block], mode: str = "contract", use_cross_encoder=False) -> dict[str, any]:
        """
        对文本块进行条款切分
        
        Args:
            blocks: 文本块列表
            mode: 切分模式 - "contract"(合同模式), "summary"(汇总模式), "single"(单条款模式)
            use_cross_encoder: 是否使用交叉编码器进行低置信复核
            
        Returns:
            包含分段结果和文本的字典
        """
        # 根据模式使用不同的参数配置
        config_map = {
            "contract": {
                "w_heading": 1.2, "w_indent_back": 1.8, "w_enum": 1.5,
                "w_sem_start": 1.0, "w_sem_cont": 0.8, "sem_margin_neg": -0.06, 
                "sem_margin_pos": 0.10, "pen_SS": -0.6, "pen_CC": 0.15
            },
            "summary": {
                "w_heading": 1.0, "w_indent_back": 1.2, "w_enum": 1.6,
                "w_sem_start": 1.2, "w_sem_cont": 0.6, "sem_margin_neg": -0.04,
                "sem_margin_pos": 0.12, "pen_SS": -0.8, "pen_CC": 0.1
            },
            "single": {
                "w_heading": 0.6, "w_indent_back": 1.0, "w_enum": 1.2,
                "w_sem_start": 0.6, "w_sem_cont": 1.0, "sem_margin_neg": -0.08,
                "sem_margin_pos": 0.06, "pen_SS": -1.2, "pen_CC": 0.2,
                "short_len_cont_bonus": 0.8, "ema_alpha": 0.35
            }
        }
        
        cfg = config_map.get(mode, config_map["contract"])
        if use_cross_encoder:
            self._ensure_cross_encoder()
        
        # 调用核心切分算法
        return self._clause_chunk(blocks, use_cross_encoder, cfg)
    
    def _clause_chunk(self, blocks: list[Block], use_cross_encoder=False, cfg: dict[str, any] | None = None):
        """
        准确度优先分段：
        - 仅用形态与相似度，无关键词表
        - 动态规划做全局最优
        - 低置信边界可用 Cross-Encoder 复核
        返回: {"spans": [[i...], ...], "texts": ["...", ...]}
        """
        cfg = {
            # 结构权重
            "indent_jump": 16,
            "w_enum": 1.5,
            "w_indent_back": 1.6,
            "w_indent_forward": 0.4,
            "w_lead": 1.0,
            "w_heading": 0.8,
            "w_soft": 1.0,
            # 语义权重与门限
            "w_sem_start": 1.0,
            "w_sem_cont": 0.8,
            "sem_margin_pos": 0.10,  # sp - sh >= + → 偏续写
            "sem_margin_neg": -0.06, # sp - sh <= - → 偏起始
            # EMA 平滑与阈值，仅用于形成本地打分（DP仍用原始两类分数）
            "ema_alpha": 0.30,
            "short_len_bias": 8,     # 很短行偏向续写
            "short_len_cont_bonus": 0.6,
            # DP 转移与先验
            "bias_start": -0.8,      # 每次起始的先验惩罚（负值=不鼓励过分割）
            "pen_SS": -0.6,          # START→START 额外惩罚，避免连发
            "pen_CC": +0.1,          # CONT→CONT 小幅奖励，鼓励合理段长
            "pen_SC": 0.0,           # START→CONT
            "pen_CS": 0.0,           # CONT→START
            # Cross-Encoder 复核
            "tie_margin": 0.25,      # |d| 小于此值认为低置信
            "ce_delta_start": -0.05, # (prev,curr)-(head,curr) <= 此阈值 → START
            "ce_delta_cont":  +0.05, # >= 此阈值 → CONT
            # 其它
            "batch_size": 64,
        } | (cfg or {})

        # 1) 预筛空块
        _blocks = [b for b in blocks if b and (b.text or "").strip()]
        n = len(_blocks)
        if n == 0:
            return {"spans": [], "texts": []}

        texts = [b.text for b in _blocks]
        V = self.embed_batch(texts, cfg["batch_size"])  # [n,d], 已单位化

        # 预计算结构信号
        enum_like   = [self.is_enum_like(b.text) for b in _blocks]
        heading_sh  = [self.is_heading_shape(b) for b in _blocks]
        ends_soft_  = [self.ends_soft(b.text) for b in _blocks]
        ends_colon_ = [self.ends_colon(b.text) for b in _blocks]
        unclosed_   = [self.unclosed_bracket(b.text) for b in _blocks]
        lengths     = [len((b.text or "").strip()) for b in _blocks]

        def cos_idx(i, j):
            if i is None or j is None: return 0.0
            v = float(np.dot(V[i], V[j]))
            return v if np.isfinite(v) else 0.0

        # 2) 局部打分（s_start[i], s_cont[i]）
        s_start = np.zeros(n, dtype=np.float32)
        s_cont  = np.zeros(n, dtype=np.float32)

        prev_idx = None
        head_idx = None
        d_prev = 0.0
        alpha = float(cfg["ema_alpha"])
        use_ema = 0 < alpha <= 1

        for i in range(n):
            # 结构信号
            if enum_like[i]:
                s_start[i] += cfg["w_enum"]
            if prev_idx is not None:
                d_indent = _blocks[prev_idx].indent - _blocks[i].indent
                if d_indent >= cfg["indent_jump"]:
                    s_start[i] += cfg["w_indent_back"]
                elif -d_indent >= cfg["indent_jump"]:
                    s_start[i] += cfg["w_indent_forward"]
                if ends_colon_[prev_idx] and enum_like[i]:
                    s_start[i] += cfg["w_lead"]
                if ends_soft_[prev_idx] or unclosed_[prev_idx]:
                    s_cont[i]  += cfg["w_soft"]
            if heading_sh[i]:
                s_start[i] += cfg["w_heading"]

            # 语义信号：prev vs head
            sh = cos_idx(head_idx, i) if head_idx is not None else 0.0
            sp = cos_idx(prev_idx, i) if prev_idx is not None else 0.0
            margin = sp - sh
            if margin <= cfg["sem_margin_neg"]:
                s_start[i] += cfg["w_sem_start"]
            elif margin >= cfg["sem_margin_pos"]:
                s_cont[i]  += cfg["w_sem_cont"]

            # 短句偏续写
            if lengths[i] < cfg["short_len_bias"]:
                s_cont[i] += cfg["short_len_cont_bonus"]

            # 本地迟滞（仅用于更新 head/prev 的决策参考，不直接改 s_start/s_cont）
            d_raw = s_start[i] - s_cont[i]
            d = alpha * d_prev + (1 - alpha) * d_raw if use_ema else d_raw

            # 依据形态与局部分数，更新"当前簇头"参考
            # 初行必为 START
            if i == 0 or (prev_idx is not None and _blocks[prev_idx].indent - _blocks[i].indent >= cfg["indent_jump"]) or heading_sh[i]:
                head_idx = i
            else:
                # 若强烈续写信号，占用原 head；若强烈起始信号，刷新 head
                if d >= 2 * cfg["sem_margin_pos"]:
                    head_idx = head_idx  # 保持
                elif d <= 2 * cfg["sem_margin_neg"]:
                    head_idx = i

            prev_idx = i
            d_prev = d

        # 3) 强制/先验
        # 起始加入惩罚，避免过分割；第一行强制 START
        s_start = s_start + cfg["bias_start"]
        s_start[0] += 10.0  # 强制第一行 START

        # 4) 动态规划解码（全局最优：START/CONT 序列）
        # dp[i,0]=START, dp[i,1]=CONT
        dp = np.full((n, 2), -1e9, dtype=np.float32)
        bt = np.full((n, 2), -1, dtype=np.int16)

        dp[0, 0] = s_start[0]  # 第0行只能 START
        dp[0, 1] = -1e9

        pen_SS = float(cfg["pen_SS"])
        pen_CC = float(cfg["pen_CC"])
        pen_SC = float(cfg["pen_SC"])
        pen_CS = float(cfg["pen_CS"])

        for i in range(1, n):
            # START at i
            cand0 = dp[i-1, 0] + pen_SS + s_start[i]  # SS
            cand1 = dp[i-1, 1] + pen_CS + s_start[i]  # CS
            if cand0 >= cand1:
                dp[i,0] = cand0; bt[i,0] = 0
            else:
                dp[i,0] = cand1; bt[i,0] = 1
            # CONT at i
            cand0 = dp[i-1, 0] + pen_SC + s_cont[i]   # SC
            cand1 = dp[i-1, 1] + pen_CC + s_cont[i]   # CC
            if cand0 >= cand1:
                dp[i,1] = cand0; bt[i,1] = 0
            else:
                dp[i,1] = cand1; bt[i,1] = 1

        # 5) 回溯状态
        states = [0] * n  # 0=START, 1=CONT
        cur = 0 if dp[-1,0] >= dp[-1,1] else 1
        for i in range(n-1, -1, -1):
            states[i] = cur
            cur = bt[i, cur] if i > 0 else cur

        # 6) 低置信边界，用 Cross-Encoder 复核（可选）
        if use_cross_encoder and self._cross_encoder:
            # 找出 |(s_start-s_cont)| 小于 tie_margin 的位置，做三元组(prev, head, curr) 打分
            to_review = []
            # 先走一遍，记录每个位置所属段头索引
            head_idx = None
            head_of = [None] * n
            for i in range(n):
                if states[i] == 0: 
                    head_idx = i
                head_of[i] = head_idx
            
            # 第二遍真正复核
            for i in range(n):
                dgap = float(s_start[i] - s_cont[i])
                if states[i] == 0: 
                    head_idx = i
                prev_i = i-1 if i-1 >= 0 else None
                if prev_i is None or head_idx is None: 
                    continue
                if abs(dgap) <= cfg["tie_margin"]:
                    to_review.append((prev_i, head_of[i], i))
            
            if to_review:
                pairs = []
                for prev_i, head_i, cur_i in to_review:
                    # 两个pair：(prev,curr) 与 (head,curr)
                    pairs.append((_blocks[prev_i].text, _blocks[cur_i].text))
                    pairs.append((_blocks[head_i].text, _blocks[cur_i].text))
                scores = self._cross_encoder.predict(pairs)  # 交叉编码相似度
                for k, (prev_i, head_i, cur_i) in enumerate(to_review):
                    sp = float(scores[2*k])
                    sh = float(scores[2*k+1])
                    delta = sp - sh
                    # 以 cross-encoder 结果微调状态
                    if delta <= cfg["ce_delta_start"]:
                        states[cur_i] = 0
                    elif delta >= cfg["ce_delta_cont"]:
                        states[cur_i] = 1
                    # 其他则保持原判

        # 7) 生成分段
        spans = []
        cur_span = [0]
        for i in range(1, n):
            if states[i] == 0:  # START
                spans.append(cur_span)
                cur_span = [i]
            else:
                cur_span.append(i)
        spans.append(cur_span)

        # 8) 二次修正：过短段合并、标题强切校正
        spans = self._post_fix_spans(spans, _blocks, V)

        texts_out = ["\n".join(_blocks[j].text for j in span) for span in spans]
        return {"spans": spans, "texts": texts_out}


# 全局服务实例
clause_chunking_service = ClauseChunkingService()