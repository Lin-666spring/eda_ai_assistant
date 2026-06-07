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

    # ── 视觉分析模板 ──
    VISION_ANALYSIS = """## 任务：分析 PCB/原理图截图

请仔细分析用户上传的图片，判断图片类型并给出专业意见。

### 如果是 PCB 布局截图：
1. 识别走线布局特点（蛇形走线、差分对、电源区域等）
2. 检查明显的布局问题（锐角走线、过孔过于密集、电源线偏细等）
3. 评估元件布局合理性（去耦电容是否靠近 IC、模数区域是否分离）
4. 给出改进建议

### 如果是原理图截图：
1. 识别电路拓扑结构和关键芯片
2. 检查常见设计问题（上拉电阻缺失、滤波电容遗漏等）
3. 评估电路功能合理性
4. 给出改进建议

### 如果是示波器/波形截图：
1. 分析波形特征（频率、幅值、噪声、抖动）
2. 诊断可能的电路问题
3. 给出调试建议

用户指令：{user_command}

请用中文给出结构化的分析报告。如果图片不清晰或无法识别，请诚实说明。"""

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

    ENTITY_EXTRACT = """## 任务：从用户指令中提取 EDA 相关实体

请从用户指令中识别并提取以下实体信息：
- component_type: 元件类型（电阻、电容、电感、IC芯片、连接器、二极管、三极管、晶振等）
- value: 参数值（如 10kΩ、100nF、3.3V、1A 等）
- package: 封装型号（如 0603、0805、SOP-8、LQFP-48、SOT-23 等）
- reference: 位号/参考标识（如 R1、C2、U3、D1 等）
- operation_target: 操作目标对象（BOM、PCB、原理图、封装库等）
- quantity: 数量信息
- rule_type: 规则类型（去耦、信号、电源、间距、ESD等）

用户指令：{user_command}

只提取指令中明确存在的实体，不臆造。返回 JSON:
{{"entities": {{"component_type": "...", "value": "...", ...}}, "ambiguous_fields": [...], "clarification_needed": false}}"""

    COMMAND_PARSE = """## 任务：将用户的自然语言指令解析为结构化操作

你是一个专业的 PCB 设计助手，专门解析 EDA 领域的用户指令。

### 步骤1：理解 EDA 术语
- "位号" = Reference Designator = R1, C2, U3, D1...
- "封装" = Package = SOP-8, QFN-32, 0603, 0805, LQFP-48...
- "BOM" = Bill of Materials = 物料清单 = 材料表
- "原理图" = Schematic
- "走线" = Trace / Routing
- "去耦" = Decoupling
- "DRC" = Design Rule Check = 设计规则检查
- "过孔" = Via
- "焊盘" = Pad
- "载流" = Current carrying capacity

### 步骤2：确定操作
{operations_description}

### 步骤3：参考示例

示例1 — 合并BOM：
用户："帮我合并BOM中的同类元件"
→ {{"operation": "merge_bom", "params": {{}}, "explanation": "用户想把相同型号、相同封装的元件合并统计"}}

示例2 — 校验封装：
用户："检查一下R5的封装对不对"
→ {{"operation": "validate_package", "params": {{"reference": "R5"}}, "explanation": "用户想单独验证位号R5的封装是否匹配其型号"}}

示例3 — 位号查重：
用户："看看有没有重复的位号"
→ {{"operation": "check_duplicates", "params": {{}}, "explanation": "用户想要检测BOM中是否有重复的Reference Designator"}}

示例4 — 筛选元件：
用户："帮我找出所有0603封装的电阻"
→ {{"operation": "filter_components", "params": {{"keyword": "0603"}}, "explanation": "用户想要筛选出0603封装的所有元件（隐含电阻）"}}

示例5 — AI智能合并：
用户："用AI智能识别还能合并哪些元件"
→ {{"operation": "ai_merge_bom", "params": {{}}, "explanation": "用户想用AI辅助分析是否有更多可合并的元件组"}}

示例6 — BOM健康检查：
用户："看看BOM里的元件有没有缺货的"
→ {{"operation": "bom_health", "params": {{}}, "explanation": "用户想检查BOM中元件的库存和供应状态"}}

示例7 — 设计规则：
用户："检查一下PCB的设计规则"
→ {{"operation": "check_rule", "params": {{}}, "explanation": "用户想要运行设计规则检查（DRC）"}}

### 重要规则
1. 操作名必须从上述支持列表中选择
2. params 只包含用户明确表达的参数，不要臆造
3. explanation 用中文简短说明你的理解（一句内）
4. 如果指令同时涉及多个操作，选择最核心/最先提到的
5. 如果指令极其模糊无法判断，用 operation: "__clarify__"

用户指令：{user_command}
{entity_context}

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
        "entity_extract": ENTITY_EXTRACT,
        "bom_ai_merge": BOM_AI_MERGE,
        "pcb_analysis": PCB_ANALYSIS,
        "pcb_doc_qa": PCB_DOC_QA,
        "vision_analysis": VISION_ANALYSIS,
    }

    _SYSTEM_PROMPTS: ClassVar[dict[str, str]] = {
        "bom": SYSTEM_ROLE + "\n\n你当前专注于 BOM 物料清单管理任务。",
        "rule": SYSTEM_ROLE + "\n\n你当前专注于 PCB 设计规则检查任务。",
        "pcb": SYSTEM_ROLE + "\n\n你当前专注于 PCB 布局分析与设计规则检查。",
        "general": SYSTEM_ROLE,
        "vision": (
            SYSTEM_ROLE
            + "\n\n你当前专注于 PCB 视觉分析任务。你是 PCB 布局和原理图的视觉分析专家，"
            "能够从截图中识别走线、元件布局、电路拓扑，并给出专业的设计审查意见。"
            "请用中文回答，分析要具体、结构化。"
        ),
        "clarify": (
            SYSTEM_ROLE
            + "\n\n你当前正在与用户对话，帮助澄清他们的意图。请用友好的语气引导用户明确需求。"
        ),
    }

    @classmethod
    def get(cls, template_name: str, **kwargs) -> str:
        """获取指定模板并填充参数

        对 command_parse 模板，会自动填充 {operations_description} 和 {entity_context}。
        """
        template = cls._TEMPLATES.get(template_name.lower(), cls.GENERAL_QA)
        if template_name.lower() == "command_parse":
            kwargs.setdefault("operations_description", cls.get_operation_descriptions())
            kwargs.setdefault("entity_context", "")
        return template.format(**kwargs) if kwargs else template

    @classmethod
    def get_system_prompt(cls, task_type: str = "general") -> str:
        """获取特定任务的系统提示词"""
        return cls._SYSTEM_PROMPTS.get(task_type, cls.SYSTEM_ROLE)

    @classmethod
    def get_operation_descriptions(cls) -> str:
        """生成操作列表描述（用于 COMMAND_PARSE 模板）

        从 ToolRegistry 派生，保持单一事实来源。
        """
        try:
            from .tools import ToolRegistry
            return ToolRegistry.get_operation_descriptions()
        except ImportError:
            # 降级：ToolRegistry 不可用时的最小硬编码列表
            return (
                "- merge_bom: 合并BOM同类元件\n  用途：合并相同型号封装的元件\n"
                "- validate_package: 校验封装匹配\n  用途：检查封装与型号是否匹配\n"
                "- check_duplicates: 检查位号重复\n  用途：查找重复位号\n"
                "- check_rule: 设计规则检查\n  用途：PCB DRC 检查\n"
                "- bom_health: BOM健康检查\n  用途：库存/生命周期/替代料检查"
            )
