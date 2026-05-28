"""
Prompt 模板库 — 重构版
面向测控/电子领域的专业术语与任务模板
用注册表替代 getattr 魔法方法
"""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class PromptTemplate:
    """单个 Prompt 模板"""
    name: str
    content: str
    description: str = ""


class PromptTemplates:
    """管理各种任务场景下的 System Prompt 模板"""

    SYSTEM_ROLE = """你是一个专业的 PCB 设计助手，专注于立创EDA（LCEDA）的 BOM 管理与 PCB 设计辅助。
你精通电子元器件知识，熟悉测控技术与仪器领域的常用电路设计。
你的用户是高校测控专业的学生，请用中文简洁、准确地回答问题。"""

    # ── BOM 管理模板 ──
    BOM_MERGE = """## 任务：合并BOM中的同类元件
请分析以下 BOM 数据，将相同型号、相同封装、相同参数的元件合并。
合并规则：
1. 型号（Part Number）完全一致
2. 封装（Package）完全一致
3. 阻值/容值/参数值一致（允许误差范围内的合并，如 ±5%）
4. 合并后输出：型号、封装、参数、合并后总数量、对应位号列表

BOM 数据如下：
{bom_data}

请以 JSON 格式返回合并结果。"""

    BOM_VALIDATE = """## 任务：校验BOM封装与型号匹配
请检查以下 BOM 数据中，每个元件的封装（Package）与型号（Part Number）是否匹配。
常见匹配关系：STM32F103C8T6 → LQFP-48, LM358 → SOP-8/DIP-8, AMS1117-3.3 → SOT-223

BOM 数据如下：
{bom_data}

请逐行检查，指出不匹配的项目，并给出建议封装。"""

    BOM_DUPLICATE_CHECK = """## 任务：检查BOM位号重复
请检查以下 BOM 数据中是否存在重复的位号（Reference Designator）。

BOM 数据如下：
{bom_data}

请列出所有重复的位号及其对应的元件信息。"""

    # ── 设计规则模板 ──
    RULE_DECOUPLING_CAP = """## 任务：去耦电容放置检查
请检查以下 PCB 设计中，每个 IC 的电源引脚附近是否放置了去耦电容。
常见规则：每个 IC VCC/VDD 引脚附近应有 0.1μF 陶瓷电容；大功率 IC 额外需要 10μF 电容。

{context_data}"""

    RULE_SIGNAL_TRACE = """## 任务：信号线走线检查
请检查信号线走线是否符合测控电路常见规则：模拟信号线远离数字信号线；差分信号线等长等间距；高频信号线避免直角拐弯；电源线宽度满足载流要求。

{context_data}"""

    PCB_ANALYSIS = """## 任务：PCB 布局分析
请根据已解析的 PCB 数据（网络连接、走线宽度、层信息、元件位置），分析以下方面：
1. 关键信号走线路径是否合理
2. 电源网络布线是否满足载流要求
3. 模拟与数字区域是否有效隔离
4. 是否存在明显的布局问题或改善空间

PCB 数据摘要：
{pcb_summary}

请给出专业的中文分析报告。"""

    PCB_DOC_QA = """## 任务：基于立创EDA知识库回答问题
请根据以下检索到的相关知识，回答用户关于立创EDA或PCB设计的问题。
如果知识库中没有相关信息，请根据你的专业知识进行补充说明。

相关知识：
{context}

用户问题：{question}"""

    # ── 通用模板 ──
    GENERAL_QA = """## 任务：回答用户的电子/PCB相关疑问
请根据你的专业知识，回答用户的问题。如果涉及具体元件参数，请给出典型值和建议。

用户问题：{question}"""

    BOM_AI_MERGE = """## 任务：AI 辅助 BOM 合并优化

以下是已按规则（型号+封装+参数值）初步合并的 BOM 分组。请检查是否有应该进一步合并的组。

常见可合并情况：
1. 参数值写法不同但实际相同（如 "10kΩ" 和 "10K"、"0.1μF" 和 "100nF"）
2. 同一芯片的不同后缀（如 STM32F103C8T6 和 STM32F103C8T6TR）
3. 同功能不同厂商型号可互换（如 LM358 和 LM358N）

当前分组：
{bom_data}

请返回 JSON 对象：{{"suggestions": [...], "analysis": "..."}}
suggestions 每项包含：
- references: 需要合并的位号列表（必填）
- suggested_value: 建议统一的值（可选）
- suggested_part_number: 建议统一的型号（可选）
- reason: 合并理由，中文（必填）

如果没有需要合并的，suggestions 为空数组。"""

    COMMAND_PARSE = """## 任务：将用户的自然语言指令解析为结构化操作

支持的操作类型：
- merge_bom: 合并BOM同类元件
- validate_package: 校验封装正确性
- check_duplicates: 检查位号重复
- filter_components: 筛选特定类型的元件
- generate_html_bom: 生成交互式HTML BOM
- check_rule: 执行设计规则检查
- ai_merge_bom: AI 智能分析并合并 BOM（用户说"AI合并"或"智能合并"时使用）
- load_pcb: 导入PCB文件（用户说"导入pcb"或"加载电路板"时使用）
- pcb_analysis: 分析PCB布局（用户说"分析pcb"或"pcb分析"时使用）

用户指令：{user_command}

请返回 JSON: {{"operation": "操作名", "params": {{...}}, "explanation": "..."}}"""

    # ── 模板注册表 ──
    _TEMPLATES: ClassVar[dict[str, str]] = {
        "bom_merge": BOM_MERGE,
        "bom_validate": BOM_VALIDATE,
        "bom_duplicate_check": BOM_DUPLICATE_CHECK,
        "rule_decoupling_cap": RULE_DECOUPLING_CAP,
        "rule_signal_trace": RULE_SIGNAL_TRACE,
        "general_qa": GENERAL_QA,
        "command_parse": COMMAND_PARSE,
        "bom_ai_merge": BOM_AI_MERGE,
        "pcb_analysis": PCB_ANALYSIS,
        "pcb_doc_qa": PCB_DOC_QA,
    }

    _SYSTEM_PROMPTS: ClassVar[dict[str, str]] = {
        "bom": SYSTEM_ROLE + "\n\n你当前专注于 BOM 物料清单管理任务。",
        "rule": SYSTEM_ROLE + "\n\n你当前专注于 PCB 设计规则检查任务。",
        "pcb": SYSTEM_ROLE + "\n\n你当前专注于 PCB 布局分析与设计规则检查。",
        "general": SYSTEM_ROLE,
    }

    @classmethod
    def get(cls, template_name: str, **kwargs) -> str:
        """获取指定模板并填充参数"""
        template = cls._TEMPLATES.get(template_name.lower(), cls.GENERAL_QA)
        return template.format(**kwargs) if kwargs else template

    @classmethod
    def get_system_prompt(cls, task_type: str = "general") -> str:
        """获取特定任务的系统提示词"""
        return cls._SYSTEM_PROMPTS.get(task_type, cls.SYSTEM_ROLE)
