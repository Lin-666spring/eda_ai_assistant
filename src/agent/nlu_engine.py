"""
语义意图匹配引擎 — 混合向量相似度 + 关键词评分的 NLU 核心

设计原则：
- 不依赖 controller/router（避免循环导入）
- embedding 失败时自动降级为纯关键词匹配
- lazy init：首调用时才初始化 embedding（不需要 API key 即可 import）

使用方式:
    engine = NLUEngine()
    intent, confidence, debug = engine.classify("帮我合并BOM中的元件")
    # → (TaskIntent.BOM_ANALYSIS, 0.85, {"embedding_score": 0.9, ...})

    if confidence < 0.4:
        # 低置信 → 走 LLM 路径
    elif confidence < 0.7:
        question = engine.get_clarification_question(user_input)
        # → "请问您是想合并BOM还是检查设计规则？"
"""

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# 避免硬依赖 — TaskIntent 在 router 中定义，这里只做字符串映射
# 实际 import 在 router 调用 NLUEngine 时传入

# ══════════════════════════════════════════════════════
#  IntentDescriptor — 意图的语义描述
# ══════════════════════════════════════════════════════


@dataclass
class IntentDescriptor:
    """单个意图的完整语义描述，用于 embedding 相似度匹配和关键词评分"""

    intent_name: str  # TaskIntent 枚举名，如 "BOM_ANALYSIS"
    label: str  # 简短中文标签，如 "BOM分析"
    description: str  # 完整语义描述（会被 embedding），需覆盖所有同义表达
    keywords: list[str] = field(default_factory=list)  # 核心关键词（中英）
    examples: list[str] = field(default_factory=list)  # 典型用户例句
    negative_keywords: list[str] = field(default_factory=list)  # 消歧关键词


# ── 7 个意图的完整描述 ──

INTENT_DESCRIPTORS: list[IntentDescriptor] = [
    IntentDescriptor(
        intent_name="TEXT_CHAT",
        label="通用对话",
        description=(
            "通用电子技术问答、PCB设计知识咨询、元件参数查询、EDA工具使用帮助。"
            "用户可能在询问概念、学习方法、电路设计建议、测试测量技术问题。"
            "用户不是在要求执行具体操作，而是在获取知识或建议。"
        ),
        keywords=[
            "什么是", "怎么", "如何", "为什么", "介绍", "说明", "解释",
            "建议", "推荐", "区别", "对比", "选型", "参数", "datasheet",
            "数据手册", "典型值", "常用", "一般", "通常",
            "what is", "how to", "explain", "recommend", "suggest",
        ],
        examples=[
            "什么是去耦电容？",
            "STM32和GD32有什么区别？",
            "0603封装的电阻功率一般是多少？",
            "如何选择合适的LDO？",
        ],
        negative_keywords=[
            "帮我", "执行", "运行", "检查", "分析", "合并", "生成",
        ],
    ),
    IntentDescriptor(
        intent_name="BOM_ANALYSIS",
        label="BOM物料分析",
        description=(
            "BOM物料清单管理操作：合并同类元件、智能合并、校验封装匹配、检查位号重复、"
            "筛选特定类型元件、生成HTML BOM报表、BOM健康检查（库存/生命周期/替代料/成本）。"
            "用户想要对已导入的BOM数据执行处理操作。"
            "关键词包括物料清单、材料表、零件表、元件列表、元器件。"
        ),
        keywords=[
            "bom", "合并", "物料", "元件", "型号", "封装", "位号", "查重",
            "校验", "整理", "归类", "清单", "材料", "零件", "器件",
            "元器件", "物料清单", "bom表", "材料表", "零件表", "元件表",
            "同一型号", "同类元件", "重复位号", "重复检测", "封装匹配",
            "merge", "duplicate", "validate", "package", "part number",
        ],
        examples=[
            "帮我合并BOM中的同类元件",
            "检查一下元件的封装对不对",
            "看看有没有重复的位号",
            "整理物料清单",
            "BOM合并",
            "AI智能合并元件",
            "筛选出所有0603封装的电阻",
        ],
    ),
    IntentDescriptor(
        intent_name="RULE_CHECK",
        label="设计规则检查",
        description=(
            "PCB设计规则检查DRC：去耦电容放置、信号线走线规则、电源线宽度、"
            "模拟数字区域分离、走线锐角/直角检查、过孔密度、板边间距、"
            "差分对等长等间距、热焊盘检查、ESD保护、复位电路检查。"
            "用户想要验证PCB设计是否符合规范。"
        ),
        keywords=[
            "规则", "drc", "检查", "违规", "去耦", "信号线", "电源线",
            "线宽", "过孔", "间距", "安规", "爬电", "差分", "阻抗",
            "设计规则", "规则检查", "drc检查", "违规检查",
            "creepage", "clearance", "rule", "design rule",
        ],
        examples=[
            "检查设计规则",
            "运行DRC",
            "看看去耦电容放对没有",
            "电源线宽度够不够",
            "检查走线有没有问题",
        ],
    ),
    IntentDescriptor(
        intent_name="PCB_ANALYSIS",
        label="PCB布局分析",
        description=(
            "PCB电路板布局布线分析：走线路径合理性、电源网络载流能力、"
            "模拟数字区域隔离、层叠结构分析、阻抗控制、过孔分布、"
            "关键信号完整性、热管理分析。用户已导入PCB文件并想分析其设计质量。"
        ),
        keywords=[
            "pcb", "布局", "布线", "走线", "层", "板", "叠层",
            "阻抗", "载流", "信号完整性", "热管理", "电路板",
            "pcb分析", "pcb布局", "pcb布线", "层叠结构",
            "layout", "routing", "stackup", "impedance",
        ],
        examples=[
            "帮我分析一下PCB布局",
            "看看走线是否合理",
            "PCB的电源网络能承载多大电流？",
            "这块板的层叠结构有问题吗？",
        ],
        negative_keywords=[
            "生成", "创建", "编写", "画", "设计一个",
        ],
    ),
    IntentDescriptor(
        intent_name="CODE_RULE_GEN",
        label="代码/规则生成",
        description=(
            "生成或创建新的内容：DRC规则脚本、自动化脚本、PCB设计规则代码、"
            "批处理脚本。用户想要创建/编写/生成新的规则或代码，而不是检查已有设计。"
            "关键词包括生成、创建、编写、写一个。"
        ),
        keywords=[
            "生成", "创建", "编写", "写一个", "写一段", "新建",
            "脚本", "自动化", "批处理", "自定义规则", "生成规则",
            "generate", "create", "write", "build", "make a",
        ],
        examples=[
            "帮我写一个去耦电容检查的DRC规则",
            "生成自动化BOM校验脚本",
            "创建一个电源线宽检查规则",
        ],
    ),
    IntentDescriptor(
        intent_name="VISUAL",
        label="图像/截图分析",
        description=(
            "分析图片、截图、照片、原理图截图、PCB截图、电路图图像。"
            "用户上传或粘贴了图像，想要AI分析图像内容。"
            "需要多模态视觉模型才能处理。"
        ),
        keywords=[
            "图片", "截图", "图像", "看图", "照片", "原理图",
            "电路图", "pcb图", "版图", "波形", "示波器",
            "screenshot", "image", "picture", "photo",
        ],
        examples=[
            "帮我看看这张原理图",
            "分析这个PCB截图中的问题",
            "这张波形图有什么异常？",
        ],
    ),
    IntentDescriptor(
        intent_name="BOM_HEALTH",
        label="BOM供应链健康",
        description=(
            "BOM物料供应链健康检查：元器件库存状态查询、生命周期检查(NRND/EOL/停产)、"
            "替代料推荐、成本估算与价格查询、采购风险评估。"
            "用户关心元件能不能买到、会不会停产、有没有便宜的替代品。"
        ),
        keywords=[
            "库存", "缺货", "停产", "生命周期", "替代料", "替代",
            "采购", "报价", "成本", "价格", "货源", "供应",
            "lcsc", "立创商城", "健康", "供应风险",
            "stock", "lifecycle", "EOL", "NRND", "alternative",
            "cost", "price", "purchase",
        ],
        examples=[
            "检查BOM中哪些元件缺货",
            "这个物料有没有停产？",
            "帮我找更便宜的替代料",
            "估算一下所有元件的总成本",
            "这些料的生命周期如何？",
        ],
    ),
    IntentDescriptor(
        intent_name="REPORT_GEN",
        label="报告生成",
        description=(
            "生成和导出报告：交互式HTML BOM表格、设计规则检查报告(DRC Report)、"
            "PCB状态概览、元件统计摘要、成本汇总、BOM物料导出CSV。"
            "用户想要生成某个报告、导出数据或查看汇总。"
        ),
        keywords=[
            "报告", "报表", "导出", "生成", "html", "csv",
            "统计报表", "导出报告", "生成报告", "设计报告",
            "bom报表", "元件统计", "统计摘要",
            "export", "report", "generate", "summary",
        ],
        examples=[
            "生成HTML交互式BOM",
            "导出BOM到CSV",
            "生成设计规则检查报告",
            "给我一个元件统计摘要",
            "导出物料清单",
        ],
    ),
    IntentDescriptor(
        intent_name="COMPONENT_LOOKUP",
        label="元件信息查询",
        description=(
            "查询元器件的详细规格：datasheet数据手册查询、封装尺寸/焊盘图、"
            "电气参数(电压/电流/功率)、温度范围、制造商信息、RoHS/环保合规。"
            "用户想要查询某个具体元件的参数或规格。"
        ),
        keywords=[
            "查询", "搜索", "找", "规格", "参数", "datasheet",
            "数据手册", "封装尺寸", "引脚", "pinout", "封装",
            "耐压", "额定电流", "功耗", "温度范围",
            "什么封装", "什么参数", "规格书",
            "lookup", "search", "specification", "specs",
            "find component", "component info",
        ],
        examples=[
            "查询STM32F103C8T6的规格参数",
            "0603封装的尺寸是多少？",
            "AMS1117-3.3的datasheet",
            "找一个5V转3.3V的LDO",
            "这个电容的耐压是多少？",
        ],
    ),
    IntentDescriptor(
        intent_name="LOCAL_ONLY",
        label="本地处理",
        description=(
            "纯本地操作，不需要调用远程AI：查看统计、显示信息、"
            "本地文件操作、状态查询。这些操作完全由本地代码处理。"
        ),
        keywords=[
            "统计", "概览", "汇总", "总览", "摘要", "本地",
            "summary", "status", "info", "信息",
        ],
        examples=[
            "显示BOM统计信息",
            "查看当前状态",
            "汇总元件类型",
        ],
    ),
]

# ── 关键词权重配置 ──
DIRECT_KEYWORD_WEIGHT = 1.0  # 意图专属核心关键词
SYNONYM_WEIGHT = 0.7  # 扩展同义词
PARTIAL_MATCH_WEIGHT = 0.3  # 部分字符匹配（bigram）

# ── 混合评分权重 ──
EMBEDDING_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4

# ── 置信度阈值 ──
HIGH_CONFIDENCE = 0.70
MEDIUM_CONFIDENCE = 0.40
LOW_CONFIDENCE_FLOOR = 0.15

# ── 本地模型路径（相对于项目根目录）──
_LOCAL_MODEL_PATH = "data/intent_model.pt"
_LOCAL_VOCAB_PATH = "data/vocab.json"


# ══════════════════════════════════════════════════════
#  NLUEngine
# ══════════════════════════════════════════════════════


class NLUEngine:
    """混合语义 + 关键词意图分类器

    使用 BGE-M3 embedding（硅基流动 API）计算用户输入与意图描述的余弦相似度，
    结合加权关键词重叠评分，输出 (intent, confidence, debug_info)。

    特性：
    - embedding 失败自动降级纯关键词
    - 意图描述预计算并缓存
    - 不依赖 router/controller（避免循环导入）
    """

    def __init__(self, api_key: Optional[str] = None):
        self._embedding_fn: Optional[object] = None
        self._embedding_failed: bool = False
        self._api_key: Optional[str] = api_key
        self._intent_embeddings: dict[str, list[float]] = {}

        # 本地模型 (TextCNN)
        self._local_predictor = None
        self._local_model_attempted: bool = False

        # 从 INTENT_DESCRIPTORS 构建内部描述符表（补充 ToolRegistry 关键词）
        self._descriptors: dict[str, IntentDescriptor] = {}
        for d in INTENT_DESCRIPTORS:
            # 拷贝一份，避免修改模块级常量
            enriched = IntentDescriptor(
                intent_name=d.intent_name,
                label=d.label,
                description=d.description,
                keywords=list(d.keywords),  # 从 Registry 补充前先保留原有
                examples=list(d.examples),
                negative_keywords=list(d.negative_keywords),
            )
            self._descriptors[d.intent_name] = enriched

        # 从 ToolRegistry 聚合关键词补充到各意图
        self._enrich_keywords_from_registry()

    def _enrich_keywords_from_registry(self):
        """从 ToolRegistry 聚合工具关键词，补充到意图描述符"""
        try:
            from .tools import ToolRegistry
            for intent_name in self._descriptors:
                extra_kw = ToolRegistry.get_keywords_by_intent(intent_name)
                if extra_kw:
                    existing = set(self._descriptors[intent_name].keywords)
                    for kw in extra_kw:
                        if kw not in existing:
                            self._descriptors[intent_name].keywords.append(kw)
                            existing.add(kw)
        except ImportError:
            pass  # ToolRegistry 未就绪时使用默认关键词

    # ── 本地模型 ──

    def _init_local_model(self) -> bool:
        """lazy init 本地 TextCNN 意图分类器

        模型文件路径：data/intent_model.pt + data/vocab.json（相对项目根目录）

        Returns:
            True 如果本地模型加载成功
        """
        if self._local_predictor is not None:
            return True
        if self._local_model_attempted:
            return False

        self._local_model_attempted = True

        try:
            from ..ml.intent_classifier import IntentPredictor

            # 确定文件路径（相对于项目根目录）
            import os
            project_root = os.path.join(os.path.dirname(__file__), "..", "..")
            model_path = os.path.join(project_root, _LOCAL_MODEL_PATH)
            vocab_path = os.path.join(project_root, _LOCAL_VOCAB_PATH)

            predictor = IntentPredictor.from_path(model_path, vocab_path)
            if predictor is not None:
                self._local_predictor = predictor
                logger.info("NLU local model loaded: TextCNN IntentClassifier")
                return True
            else:
                logger.info("NLU local model not found, using embedding+keyword")
                return False
        except ImportError as e:
            logger.info("NLU local model unavailable (torch not installed?): %s", e)
            return False
        except Exception as e:
            logger.warning("NLU local model init failed: %s", e)
            return False

    # ── 公开 API ──

    def classify(self, user_input: str) -> tuple:
        """分类用户输入，返回 (intent_name, confidence, debug_info)

        Args:
            user_input: 用户输入文本

        Returns:
            intent_name: str — TaskIntent 枚举名 (如 "BOM_ANALYSIS")
            confidence: float — 0.0-1.0 置信度
            debug_info: dict — {"embedding_score": float, "keyword_score": float,
                                "scores": {name: float, ...}, "top_two": [...]}
        """
        if not user_input or not user_input.strip():
            return ("TEXT_CHAT", 0.0, {
                "embedding_score": 0.0, "keyword_score": 0.0,
                "scores": {}, "top_two": [],
                "reason": "empty_input",
            })

        # Step 0: 优先使用本地 TextCNN 模型（离线，< 1ms）
        if self._init_local_model():
            intent_name, confidence, debug = self._local_predictor.classify(user_input)
            # 补充 keyword_score 以保持 debug 结构兼容
            kw_scores = self._compute_keyword_score(user_input)
            debug["keyword_score"] = kw_scores.get(intent_name, 0.0)
            debug["embedding_score"] = confidence
            debug["embedding_used"] = False
            debug["model"] = "local_textcnn"

            # 低置信度时回退到关键词评分（模型对未知输入可能不可靠）
            if confidence < MEDIUM_CONFIDENCE:
                logger.debug(
                    "Local model low confidence (%.2f), falling back to keyword",
                    confidence,
                )
                hybrid_scores = self._hybrid_score({}, kw_scores)
                sorted_intents = sorted(hybrid_scores.items(), key=lambda x: -x[1])
                best_name, best_score = sorted_intents[0]
                # 关键词评分也低 → 强制 TEXT_CHAT（与原有 classify 逻辑一致）
                if best_score < LOW_CONFIDENCE_FLOOR:
                    debug["keyword_score"] = 0.0
                    debug["top_two"] = [("TEXT_CHAT", LOW_CONFIDENCE_FLOOR)]
                    debug["model"] = "local_textcnn+text_chat_default"
                    return ("TEXT_CHAT", LOW_CONFIDENCE_FLOOR, debug)
                if best_score > confidence:
                    debug["keyword_score"] = best_score
                    debug["top_two"] = sorted_intents[:2]
                    debug["model"] = "local_textcnn+keyword_fallback"
                    return (best_name, best_score, debug)

            return (intent_name, confidence, debug)

        # Step 1: 计算向量相似度（如果可用）
        emb_scores = self._compute_embedding_similarity(user_input)

        # Step 2: 计算关键词评分
        kw_scores = self._compute_keyword_score(user_input)

        # Step 3: 混合评分
        hybrid_scores = self._hybrid_score(emb_scores, kw_scores)

        # Step 4: 确定最佳意图 + 置信度
        sorted_intents = sorted(hybrid_scores.items(), key=lambda x: -x[1])
        best_name, best_score = sorted_intents[0]

        # 确定置信度
        if best_score >= HIGH_CONFIDENCE:
            confidence = best_score
        elif best_score >= MEDIUM_CONFIDENCE:
            # 中等置信度 — 检查与第二名的差距
            if len(sorted_intents) > 1:
                gap = best_score - sorted_intents[1][1]
                confidence = best_score * (0.5 + gap)  # 差距大则上调
            else:
                confidence = best_score
        else:
            confidence = max(best_score, LOW_CONFIDENCE_FLOOR)

        # 如果所有分数都极低，返回 TEXT_CHAT 兜底
        if best_score < LOW_CONFIDENCE_FLOOR:
            best_name = "TEXT_CHAT"
            confidence = LOW_CONFIDENCE_FLOOR

        top_two = sorted_intents[:2]
        debug = {
            "embedding_score": emb_scores.get(best_name, 0.0) if emb_scores else 0.0,
            "keyword_score": kw_scores.get(best_name, 0.0),
            "scores": {k: round(v, 4) for k, v in sorted_intents},
            "top_two": [(name, round(score, 4)) for name, score in top_two],
            "embedding_used": bool(emb_scores),
        }

        logger.debug(
            "NLU classify: '%s' → %s (conf=%.2f, emb=%.2f, kw=%.2f)",
            user_input[:50], best_name, confidence,
            debug["embedding_score"], debug["keyword_score"],
        )

        return (best_name, confidence, debug)

    def get_clarification_question(self, user_input: str) -> str:
        """为置信度中等的输入生成追问

        Returns:
            追问字符串，如 "请问您是想合并BOM还是检查设计规则？"
        """
        _, _, debug = self.classify(user_input)
        top_two = debug.get("top_two", [])

        if len(top_two) < 2:
            return (
                "🤔 不太确定您的意思，能再说详细一点吗？\n"
                "例如：\"合并BOM\"、\"检查设计规则\"、\"分析PCB布局\""
            )

        label1 = self._get_label(top_two[0][0])
        label2 = self._get_label(top_two[1][0])

        return f"🤔 请问您是想**{label1}**还是**{label2}**？请明确一下。\n\n💡 其他可用操作：合并BOM / 校验封装 / 检查重复 / 设计规则 / PCB分析 / BOM健康 / 生成HTML"

    # ── 内部：向量相似度 ──

    def _compute_embedding_similarity(self, user_input: str) -> dict[str, float]:
        """计算用户输入与每个意图描述的余弦相似度

        Returns:
            {intent_name: similarity_score, ...} 或空字典（降级）
        """
        if not self._init_embedding():
            return {}

        try:
            query_vec = self._embedding_fn.embed([user_input])[0]
        except Exception as e:
            logger.warning("Query embedding failed: %s, falling back to keyword", e)
            self._embedding_failed = True
            self._embedding_fn = None
            return {}

        scores = {}
        for name, intent_vec in self._intent_embeddings.items():
            scores[name] = self._cosine_similarity(query_vec, intent_vec)

        return scores

    def _init_embedding(self) -> bool:
        """lazy init embedding 函数 + 预计算意图向量"""
        if self._embedding_failed:
            return False
        if self._embedding_fn is not None:
            return True

        try:
            from ..rag.indexer import _SiliconFlowEmbedding

            self._embedding_fn = _SiliconFlowEmbedding(api_key=self._api_key)
            # 预计算所有意图描述的向量
            descriptions = [d.description for d in INTENT_DESCRIPTORS]
            vectors = self._embedding_fn.embed(descriptions)
            for desc, vec in zip(INTENT_DESCRIPTORS, vectors):
                self._intent_embeddings[desc.intent_name] = vec
            logger.info(
                "NLU embedding ready: %d intent vectors cached",
                len(self._intent_embeddings),
            )
            return True
        except Exception as e:
            logger.warning("NLU embedding init failed: %s, using keyword-only", e)
            self._embedding_failed = True
            self._embedding_fn = None
            return False

    # ── 内部：关键词评分 ──

    def _compute_keyword_score(self, user_input: str) -> dict[str, float]:
        """计算每个意图的关键词匹配评分

        评分策略：
        - 直接命中核心关键词：DIRECT_KEYWORD_WEIGHT (1.0)
        - 命中扩展同义词：SYNONYM_WEIGHT (0.7)
        - bigram 部分匹配：PARTIAL_MATCH_WEIGHT (0.3)
        - 命中 negative_keywords：扣分 (×0.5)
        """
        lowered = user_input.lower()
        scores: dict[str, float] = {}

        for desc in INTENT_DESCRIPTORS:
            score = 0.0
            total_possible = len(desc.keywords) + len(desc.examples)

            # 核心关键词子串匹配
            for kw in desc.keywords:
                if kw.lower() in lowered:
                    score += DIRECT_KEYWORD_WEIGHT

            # 例句中的关键短语匹配
            for ex in desc.examples:
                # 从例句提取关键词短语（2-5字片段）
                ex_lower = ex.lower()
                for i in range(len(ex_lower)):
                    for j in range(i + 2, min(i + 8, len(ex_lower) + 1)):
                        phrase = ex_lower[i:j]
                        if len(phrase) >= 2 and phrase in lowered:
                            score += PARTIAL_MATCH_WEIGHT
                            break

            # 消歧惩罚
            neg_hits = sum(
                1 for nk in desc.negative_keywords if nk.lower() in lowered
            )
            if neg_hits > 0:
                score *= 0.5 ** neg_hits  # 每命中一个减半

            # 归一化
            if total_possible > 0:
                scores[desc.intent_name] = min(score / max(total_possible * 0.3, 1), 1.0)
            else:
                scores[desc.intent_name] = 0.0

        return scores

    # ── 内部：混合评分 ──

    def _hybrid_score(
        self,
        emb_scores: dict[str, float],
        kw_scores: dict[str, float],
    ) -> dict[str, float]:
        """合并 embedding 和关键词评分

        当 embedding 不可用（空字典）时，纯关键词评分占 100%。
        """
        hybrid: dict[str, float] = {}
        has_embedding = bool(emb_scores)

        for desc in INTENT_DESCRIPTORS:
            name = desc.intent_name
            emb = emb_scores.get(name, 0.0)
            kw = kw_scores.get(name, 0.0)

            if has_embedding:
                # 归一化 embedding 分数
                max_emb = max(emb_scores.values()) if emb_scores else 1.0
                emb_norm = emb / max_emb if max_emb > 0 else 0.0
                hybrid[name] = EMBEDDING_WEIGHT * emb_norm + KEYWORD_WEIGHT * kw
            else:
                hybrid[name] = kw

        return hybrid

    # ── 工具方法 ──

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _get_label(self, intent_name: str) -> str:
        """获取意图的中文标签"""
        desc = self._descriptors.get(intent_name)
        return desc.label if desc else intent_name

    @property
    def embedding_available(self) -> bool:
        """embedding 是否可用"""
        return self._embedding_fn is not None and not self._embedding_failed

    @property
    def intent_count(self) -> int:
        """已注册的意图数量"""
        return len(INTENT_DESCRIPTORS)
