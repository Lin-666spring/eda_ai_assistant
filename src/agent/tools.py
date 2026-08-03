"""
统一工具注册表 — 系统中所有操作能力的单一事实来源 (Single Source of Truth)

每个 ToolDef 定义了一个系统能力。所有其他模块从这里**派生**数据：
- NLU 关键词匹配 ← get_keyword_map()
- LLM Prompt 操作列表 ← get_operation_descriptions()
- Controller dispatch 表 ← get_dispatch_map()
- 方法名→中文标签 ← get_labels()
- Function Calling schema ← get_function_definitions()  [PLANNED]

新增能力只需在此文件添加一个 ToolDef，所有派生自动生效。

使用方式:
    from src.agent.tools import ToolRegistry
    registry = ToolRegistry()
    keywords = registry.get_keyword_map()      # → [(("合并",...), "merge_bom"), ...]
    labels   = registry.get_labels()           # → {"merge_bom": "合并BOM", ...}
"""

import json
import logging
from dataclasses import dataclass, field
from typing import ClassVar

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  ToolDef
# ══════════════════════════════════════════════════════


@dataclass
class ToolDef:
    """单个系统能力的完整定义"""

    name: str                 # 规范操作名: "merge_bom"
    label: str                # 中文标签: "合并BOM"
    description: str          # LLM 可读描述（一句话）
    keywords: tuple[str, ...] # NLU/本地匹配关键词
    intent: str               # 归属意图 (TaskIntent 枚举名)
    handler: str              # Controller 方法名
    params_schema: dict = field(default_factory=dict)  # JSON Schema (function calling)
    requires_data: bool = True  # 需要 BOM 已加载?
    category: str = "bom"     # "bom" | "pcb" | "report" | "health" | "vision"

    def to_function_definition(self) -> dict:
        """生成 OpenAI 兼容的 function definition

        [PLANNED] 供 Agent Loop 使用:
            LLMClient.function_call(prompt, functions=[
                t.to_function_definition() for t in ToolRegistry.get_all()
            ])
        """
        props = self.params_schema.get("properties", {})
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": self.params_schema.get("required", []),
                },
            },
        }


# ══════════════════════════════════════════════════════
#  工具注册表 — 24 个系统能力
# ══════════════════════════════════════════════════════

TOOLS: list[ToolDef] = [
    # ── BOM 操作 ──
    ToolDef(
        name="ai_merge_bom",
        label="AI智能合并",
        description="先用规则合并BOM同类元件，再用AI分析是否有可进一步合并的元件组",
        keywords=("ai合并", "智能合并", "ai_merge", "AI合并", "AI 合并",
                  "智能识别", "ai识别", "ai分析合并", "ai分析"),
        intent="BOM_ANALYSIS",
        handler="ai_merge_bom",
        params_schema={"properties": {}, "required": []},
        category="bom",
    ),
    ToolDef(
        name="merge_bom",
        label="合并BOM",
        description="将型号、封装、参数值完全相同的BOM元件合并为一行，汇总数量",
        keywords=("合并", "merge", "整理", "同类", "归类", "合并同类",
                  "综合", "合并bom", "bom合并", "物料清单", "bom表",
                  "材料表", "零件表"),
        intent="BOM_ANALYSIS",
        handler="merge_bom",
        params_schema={"properties": {}, "required": []},
        category="bom",
    ),
    ToolDef(
        name="validate_package",
        label="校验封装",
        description="逐行检查BOM中每个元件的封装是否与其型号匹配，标记不匹配项",
        keywords=("校验", "验证", "封装", "validate", "封装检查",
                  "封装校验", "封装验证", "封装匹配", "封装对不对"),
        intent="BOM_ANALYSIS",
        handler="validate_packages",  # handler 方法名保持复数
        params_schema={"properties": {}, "required": []},
        category="bom",
    ),
    ToolDef(
        name="check_duplicates",
        label="检查位号重复",
        description="扫描BOM中所有Reference Designator，检测并报告重复的位号",
        keywords=("重复", "查重", "duplicate", "位号", "重复位号",
                  "重复检查", "重复检测", "重复的位号"),
        intent="BOM_ANALYSIS",
        handler="check_duplicates",
        params_schema={"properties": {}, "required": []},
        category="bom",
    ),
    ToolDef(
        name="filter_components",
        label="筛选元件",
        description="按关键词从BOM中筛选符合条件的元件",
        keywords=("筛选", "过滤", "查找元件", "搜索元件", "filter",
                  "search", "找出", "找出所有", "筛选出"),
        intent="BOM_ANALYSIS",
        handler="_filter_input",  # → _resolve_handler
        params_schema={
            "properties": {"keyword": {"type": "string", "description": "筛选关键词"}},
            "required": ["keyword"],
        },
        category="bom",
    ),
    # ── 报告导出 ──
    ToolDef(
        name="generate_html_bom",
        label="生成HTML BOM",
        description="将BOM导出为可搜索、排序、筛选的交互式HTML表格",
        keywords=("html", "网页", "交互", "导出", "ibom",
                  "网页bom", "bom网页", "web bom", "生成html"),
        intent="REPORT_GEN",
        handler="generate_html_bom",
        params_schema={"properties": {}, "required": []},
        category="report",
    ),
    ToolDef(
        name="export_bom_csv",
        label="导出BOM CSV",
        description="将当前BOM数据导出为标准CSV文件，可被Excel/立创EDA打开",
        keywords=("导出csv", "csv", "excel", "导出表格", "保存bom",
                  "导出bom", "bom导出", "导出到excel", "表格导出",
                  "csv导出", "保存为csv"),
        intent="REPORT_GEN",
        handler="export_bom_csv",
        params_schema={"properties": {}, "required": []},
        category="report",
    ),
    ToolDef(
        name="bom_cost_summary",
        label="BOM成本汇总",
        description="汇总估算BOM中所有元件的总成本和各项成本分布",
        keywords=("成本", "总价", "预算", "费用", "花费", "每个多少钱",
                  "价格汇总", "成本汇总", "成本估算", "总成本",
                  "多少钱", "cost", "price total"),
        intent="BOM_HEALTH",
        handler="check_bom_health",
        params_schema={"properties": {}, "required": []},
        category="health",
    ),
    # ── PCB & 规则 ──
    ToolDef(
        name="check_rule",
        label="设计规则检查",
        description="执行PCB设计规则检查(DRC)：去耦电容、信号线宽、电源载流、走线锐角、过孔密度、模数分离等21条规则",
        keywords=("规则", "rule", "去耦", "信号", "电源", "模数", "drc",
                  "设计规则", "违规检查", "间距", "安规", "爬电",
                  "过孔", "差分", "线宽检查", "检查规则",
                  "信号线", "电源线", "线宽",
                  # 注意: "检查" 不在此列表 — 太通用
                  ),
        intent="RULE_CHECK",
        handler="check_design_rules",  # handler 方法名保持
        params_schema={"properties": {}, "required": []},
        category="pcb",
    ),
    ToolDef(
        name="pcb_status",
        label="查看PCB状态",
        description="查看已加载的PCB文件基本信息（网络数、走线数、过孔数、层结构）",
        keywords=("pcb状态", "导入pcb", "电路板", "加载pcb", "打开pcb",
                  "pcb文件", "查看pcb"),
        intent="PCB_ANALYSIS",
        handler="_pcb_status",
        params_schema={"properties": {}, "required": []},
        requires_data=False,
        category="pcb",
    ),
    ToolDef(
        name="pcb_analysis",
        label="PCB布局分析",
        description="分析PCB布局布线：走线路径、电源载流、模数隔离、层叠结构、信号完整性",
        keywords=("布局", "布线", "走线", "层叠", "叠层", "routing",
                  "layout", "pcb分析", "分析pcb", "分析布局", "分析布线",
                  "pcb布局", "pcb布线", "载流", "信号完整性",
                  "stackup", "impedance", "阻抗"),
        intent="PCB_ANALYSIS",
        handler="_pcb_analysis_cmd",
        params_schema={"properties": {}, "required": []},
        category="pcb",
    ),
    # ── BOM 健康 / 供应链 ──
    ToolDef(
        name="bom_health",
        label="BOM健康检查",
        description="通过立创商城API检查每个元件的库存状态、生命周期(NRND/EOL)、可替代料推荐、成本估算",
        keywords=("健康", "库存", "采购", "报价", "替代料", "缺货",
                  "生命周期", "lcsc", "立创商城", "供应", "货源",
                  "成本", "价格"),
        intent="BOM_HEALTH",
        handler="check_bom_health",
        params_schema={"properties": {}, "required": []},
        category="health",
    ),
    ToolDef(
        name="find_alternatives",
        label="查找替代料",
        description="为指定元件在立创商城中查找可替代型号（pin-to-pin兼容或功能兼容）",
        keywords=("替代", "替换", "替代料", "替代型号", "代替", "换一个",
                  "有什么替代", "替换料", "替代方案", "可替代",
                  "alternative", "replace", "substitute"),
        intent="BOM_HEALTH",
        handler="check_bom_health",  # 复用健康检查，其已包含替代料
        params_schema={
            "properties": {"keyword": {"type": "string", "description": "要查找替代的元件型号或描述"}},
            "required": [],
        },
        category="health",
    ),
    ToolDef(
        name="supply_risk",
        label="供应链风险评估",
        description="评估BOM整体供应链风险：缺货率、停产风险、单一供应商依赖、交期风险",
        keywords=("供应风险", "缺货风险", "停产风险", "交期", "供应链",
                  "采购风险", "风险评估", "风险分析", "供货风险"),
        intent="BOM_HEALTH",
        handler="check_bom_health",
        params_schema={"properties": {}, "required": []},
        category="health",
    ),
    # ── 元件信息查询 ──
    ToolDef(
        name="component_lookup",
        label="元件信息查询",
        description="查询元器件的详细规格参数：封装尺寸、电气参数、datasheet信息、制造商详情",
        keywords=("查询元件", "规格", "datasheet", "数据手册", "参数查询",
                  "什么封装", "尺寸", "引脚定义", "pinout", "规格书",
                  "技术参数", "电气参数", "额定电压", "额定电流",
                  "lookup", "specs", "datasheet"),
        intent="COMPONENT_LOOKUP",
        handler="_filter_input",  # LLM Agent Loop 处理查询
        params_schema={
            "properties": {"part_number": {"type": "string", "description": "要查询的元件型号"}},
            "required": ["part_number"],
        },
        requires_data=False,
        category="bom",
    ),
    ToolDef(
        name="search_component",
        label="搜索元件",
        description="在元件库中搜索符合需求的元件型号（如：找一款5V转3.3V的LDO）",
        keywords=("找", "搜索", "查找", "选型", "选一个", "找一个",
                  "有什么", "哪种", "推荐一款", "选型推荐",
                  "find", "search", "recommend", "suggest"),
        intent="COMPONENT_LOOKUP",
        handler="_filter_input",
        params_schema={
            "properties": {"requirement": {"type": "string", "description": "元件需求描述"}},
            "required": ["requirement"],
        },
        requires_data=False,
        category="bom",
    ),
    # ── PCB 设计工具 ──
    ToolDef(
        name="calc_trace_width",
        label="计算走线宽度",
        description="根据电流和温升计算所需PCB走线宽度（IPC-2221标准）",
        keywords=("走线宽度", "线宽计算", "载流计算", "铜厚", "温升",
                  "多宽走线", "线宽要多少", "走多宽", "载流能力",
                  "trace width", "current capacity", "ipc2221"),
        intent="PCB_ANALYSIS",
        handler="_pcb_analysis_cmd",
        params_schema={
            "properties": {
                "current_a": {"type": "number", "description": "电流(A)"},
                "temp_rise": {"type": "number", "description": "允许温升(°C)，默认10"},
                "copper_oz": {"type": "number", "description": "铜厚(oz)，默认1"},
            },
            "required": ["current_a"],
        },
        requires_data=False,
        category="pcb",
    ),
    ToolDef(
        name="explain_design_rule",
        label="解释设计规则",
        description="详细解释某条PCB设计规则的理论依据和实际应用",
        keywords=("解释规则", "设计规则说明", "为什么需要", "原理",
                  "什么原理", "解释一下", "这条规则", "为什么这样",
                  "explain rule", "rule explanation"),
        intent="RULE_CHECK",
        handler="check_design_rules",
        params_schema={
            "properties": {"rule_name": {"type": "string", "description": "要解释的规则名称"}},
            "required": ["rule_name"],
        },
        category="pcb",
    ),
    # ── 视觉分析 ──
    ToolDef(
        name="analyze_image",
        label="图片分析",
        description="分析上传的PCB截图、原理图或波形图，识别布局问题和电路设计缺陷",
        keywords=("图片", "截图", "图像", "看图", "照片", "原理图"),
        intent="VISUAL",
        handler="_analyze_image",
        params_schema={
            "properties": {
                "image_data": {"type": "string", "description": "base64 编码的图片数据"},
            },
            "required": ["image_data"],
        },
        requires_data=False,
        category="vision",
    ),
    # ── 统计报告 ──
    ToolDef(
        name="summary_report",
        label="元件统计",
        description="按类型统计BOM元件数量和分布",
        keywords=("统计", "概览", "summary", "汇总", "总览",
                  "统计信息", "摘要"),
        intent="REPORT_GEN",
        handler="_summary_report",
        params_schema={"properties": {}, "required": []},
        category="report",
    ),
    # ── 多智能体协同审查 ──
    ToolDef(
        name="review_multi_agent",
        label="多智能体审查",
        description="启动5个专业AI Agent并行审查PCB设计（电源/信号/热/EMC/可制造性），生成综合评分报告和雷达图",
        keywords=("多智能体", "全面审查", "综合检查", "质量评分", "多维度",
                  "全面分析", "agent审查", "多agent", "五个agent",
                  "review", "multi agent", "full review", "audit"),
        intent="RULE_CHECK",
        handler="review_design_multi_agent",
        params_schema={"properties": {}, "required": []},
        category="pcb",
    ),
    # ── 闭环验证 (路线三核心) ──
    ToolDef(
        name="verify_suggestion",
        label="闭环验证",
        description="对PCB设计建议执行闭环验证：LLM建议 → DRC规则引擎实时检查 → 发现新违规 → LLM自动修正 → 迭代至收敛（最多3轮）。确保任何AI建议不会引入新的设计违规",
        keywords=("闭环验证", "验证建议", "检查建议", "设计验证", "建议验证",
                  "闭环检查", "校验建议", "确认建议", "设计审查验证",
                  "verify", "validation", "闭环", "设计规则验证",
                  "drc验证", "规则验证", "设计建议检查"),
        intent="RULE_CHECK",
        handler="verify_suggestion",
        params_schema={
            "properties": {
                "suggestion": {"type": "string", "description": "需要验证的PCB设计建议或变更方案"},
            },
            "required": ["suggestion"],
        },
        category="pcb",
    ),
    # ── DRC 规则自动生成 ──
    ToolDef(
        name="generate_drc_rule",
        label="生成DRC规则",
        description="根据自然语言描述自动生成PCB设计规则检查代码，返回完整的RuleViolation格式Python代码",
        keywords=("生成规则", "创建规则", "编写drc", "写一个检查", "新增规则",
                  "自定义规则", "生成drc", "dr规则生成", "写规则",
                  "generate rule", "create rule", "new drc"),
        intent="CODE_RULE_GEN",
        handler="_generate_drc_rule",
        params_schema={
            "properties": {
                "rule_description": {"type": "string", "description": "用户对需要生成的设计规则的文字描述"},
            },
            "required": ["rule_description"],
        },
        requires_data=False,
        category="pcb",
    ),
    # ── RAG 知识库查询 ──
    ToolDef(
        name="rag_query",
        label="知识库查询",
        description="查询PCB设计知识库，获取IPC标准、高速数字设计、信号完整性、EMC、DFM、热管理、BGA封装、射频设计等专业工程知识和设计规范",
        keywords=("知识库", "文档查询", "标准", "规范", "IPC", "设计指南", "知识",
                  "查询知识", "手册", "指南", "规格", "参数查询", "知识查询",
                  "pcb知识", "工程知识", "技术资料", "资料查询", "文档"),
        intent="PCB_ANALYSIS",
        handler="query_knowledge_base",
        params_schema={
            "properties": {
                "query": {"type": "string", "description": "知识查询的具体问题，如'IPC-2221载流计算公式'或'DDR5布线规范'"},
            },
            "required": ["query"],
        },
        requires_data=False,
        category="pcb",
    ),
]

# ── 路由优先级: 同名关键词谁排前面谁优先 ──
# ai_merge_bom 排在 merge_bom 前面 → "ai合并" 优先匹配 ai_merge_bom
# pcb_status 排在 pcb_analysis 前面 → "pcb" 优先匹配状态查看


# ══════════════════════════════════════════════════════
#  ToolRegistry — 查询接口
# ══════════════════════════════════════════════════════


class ToolRegistry:
    """统一工具注册表查询接口（类方法，无需实例化）"""

    _tools: ClassVar[list[ToolDef]] = TOOLS

    # ── 基础查询 ──

    @classmethod
    def get_all(cls) -> list[ToolDef]:
        """获取全部工具定义"""
        return list(cls._tools)

    @classmethod
    def get_by_name(cls, name: str) -> ToolDef | None:
        """按规范名查找"""
        for t in cls._tools:
            if t.name == name:
                return t
        return None

    @classmethod
    def get_by_intent(cls, intent_name: str) -> list[ToolDef]:
        """按意图查找"""
        return [t for t in cls._tools if t.intent == intent_name]

    @classmethod
    def get_by_category(cls, category: str) -> list[ToolDef]:
        """按类别查找: bom | pcb | report | health"""
        return [t for t in cls._tools if t.category == category]

    # ── 派生数据: 供其他模块消费 ──

    @classmethod
    def get_keyword_map(cls) -> list[tuple[tuple[str, ...], str]]:
        """生成关键词→工具名的优先级映射

        替代 controller._KEYWORD_ROUTES 和 router._classify_by_keyword。
        返回格式: [((kw1, kw2, ...), tool_name), ...]
        顺序即优先级 — ai_merge_bom 在 merge_bom 之前。
        """
        return [(t.keywords, t.name) for t in cls._tools]

    @classmethod
    def get_keywords_by_intent(cls, intent_name: str) -> list[str]:
        """聚合某意图下所有工具的关键词（供 nlu_engine 使用）"""
        keywords: list[str] = []
        for t in cls.get_by_intent(intent_name):
            keywords.extend(t.keywords)
        return keywords

    @classmethod
    def get_operation_descriptions(cls) -> str:
        """生成 LLM prompt 用的操作列表描述

        替代 prompt_templates.get_operation_descriptions()。
        """
        lines = []
        for t in cls._tools:
            lines.append(f"- {t.name}: {t.label}\n  用途：{t.description}")
        return "\n".join(lines)

    @classmethod
    def get_labels(cls) -> dict[str, str]:
        """生成 name→label 映射

        替代 controller._method_label。
        """
        return {t.name: t.label for t in cls._tools}

    @classmethod
    def get_label(cls, name: str) -> str:
        """获取单个工具的标签"""
        t = cls.get_by_name(name)
        return t.label if t else name

    @classmethod
    def get_dispatch_map(cls) -> dict[str, str]:
        """生成 operation_name→handler_method 映射

        替代 controller._dispatch_operation 内联字典。
        """
        return {t.name: t.handler for t in cls._tools}

    @classmethod
    def get_help_text(cls) -> str:
        """生成用户帮助文本（供 _local_fallback 使用）"""
        lines = ["可用指令:"]
        by_cat = {"bom": [], "pcb": [], "report": [], "health": []}
        for t in cls._tools:
            if t.category in by_cat:
                by_cat[t.category].append(t)

        for t in by_cat.get("bom", []):
            lines.append(f"  • {t.label:10s} — {t.description[:20]}")
        for t in by_cat.get("pcb", []):
            lines.append(f"  • {t.label:10s} — {t.description[:20]}")
        for t in by_cat.get("health", []):
            lines.append(f"  • {t.label:10s} — {t.description[:20]}")
        for t in by_cat.get("report", []):
            lines.append(f"  • {t.label:10s} — {t.description[:20]}")
        return "\n".join(lines)

    # ── [PLANNED] Function Calling 接口 ──

    @classmethod
    def get_function_definitions(cls) -> list[dict]:
        """生成 OpenAI/DeepSeek function calling 工具定义

        [PLANNED] Agent Loop 接入方式:
            definitions = ToolRegistry.get_function_definitions()
            result = llm_client.function_call(prompt, functions=definitions)
            tool_name = result["name"]
            tool_args = result["arguments"]
            output = controller._dispatch_operation(tool_name, tool_args)
        """
        return [t.to_function_definition() for t in cls._tools if t.params_schema]

    # ── 统计 ──

    @classmethod
    def count(cls) -> int:
        return len(cls._tools)

    @classmethod
    def list_names(cls) -> list[str]:
        return [t.name for t in cls._tools]


# ══════════════════════════════════════════════════════
#  [PLANNED] 未来集成点
# ══════════════════════════════════════════════════════

# [PLANNED] Agent Loop — 多步推理
#   接入方式:
#     tools = ToolRegistry.get_function_definitions()
#     result = llm_client.function_call(prompt, functions=tools)
#     while result["name"] != "__done__":
#         output = controller._dispatch_operation(result["name"], result["arguments"])
#         result = llm_client.function_call(output, functions=tools)

