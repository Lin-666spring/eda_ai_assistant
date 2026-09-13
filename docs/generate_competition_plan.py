# -*- coding: utf-8 -*-
"""
中国国际大学生创新大赛（高教主赛道·创意组）项目计划书生成器
项目：EDA AI 智能助手 —— 面向 PCB 设计的闭环验证式智能设计助手
"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = os.path.join(os.path.dirname(__file__), "中国国际大学生创新大赛_项目计划书.docx")

# ---------- 字体 / 样式常量 ----------
FONT_CN = "宋体"
FONT_CN_HEAD = "黑体"
FONT_EN = "Times New Roman"
ACCENT = RGBColor(0x1F, 0x3A, 0x6E)   # 深蓝
GRAY = RGBColor(0x59, 0x59, 0x59)


def set_run(run, size=12, bold=False, color=None, font_cn=FONT_CN, font_en=FONT_EN):
    run.font.name = font_en
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), font_cn)
    rFonts.set(qn("w:ascii"), font_en)
    rFonts.set(qn("w:hAnsi"), font_en)


def para(doc, text="", size=12, bold=False, color=None, align=None,
         space_after=6, space_before=0, line=1.5, font_cn=FONT_CN, indent=False):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    if line:
        pf.line_spacing = line
    if indent:
        pf.first_line_indent = Pt(size * 2)
    if text:
        r = p.add_run(text)
        set_run(r, size=size, bold=bold, color=color, font_cn=font_cn)
    return p


def bullet(doc, text, size=12, bold=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(3)
    pf.line_spacing = 1.5
    pf.left_indent = Pt(18)
    r = p.add_run("• " + text)
    set_run(r, size=size, bold=bold)
    return p


def setup_heading_styles(doc):
    def _style(name, size, color):
        st = doc.styles[name]
        st.font.name = FONT_EN
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = color
        rpr = st.element.get_or_add_rPr()
        rfonts = rpr.get_or_add_rFonts()
        rfonts.set(qn("w:eastAsia"), FONT_CN_HEAD)
    _style("Heading 1", 16, ACCENT)
    _style("Heading 2", 14, RGBColor(0x2E, 0x4E, 0x8E))
    _style("Heading 3", 12, RGBColor(0x33, 0x33, 0x33))


def h1(doc, text):
    p = doc.add_paragraph(style="Heading 1")
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.3
    p.add_run(text)
    # 标题底部边框线
    pPr = p._element.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "1F3A6E")
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def h2(doc, text):
    p = doc.add_paragraph(style="Heading 2")
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.3
    p.add_run(text)
    return p


def h3(doc, text):
    p = doc.add_paragraph(style="Heading 3")
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.3
    p.add_run(text)
    return p


def shade_cell(cell, hex_color):
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def cell_text(cell, text, size=10.5, bold=False, color=None, align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    r = p.add_run(text)
    set_run(r, size=size, bold=bold, color=color)


def add_table(doc, headers, rows, widths=None, header_fill="1F3A6E"):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    hdr = t.rows[0].cells
    for i, htxt in enumerate(headers):
        cell_text(hdr[i], htxt, size=10.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade_cell(hdr[i], header_fill)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cell_text(cells[i], str(val), size=10.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    return t


TOC_ITEMS = [
    "一、执行摘要",
    "二、项目背景与市场痛点",
    "三、产品与技术方案",
    "四、核心创新点",
    "五、实验验证与成果",
    "六、市场分析",
    "七、商业模式",
    "八、团队介绍",
    "九、财务预测（简要）",
    "十、风险分析与对策",
    "十一、发展规划",
    "附录：项目关键数据汇总",
]


def add_toc(doc):
    for item in TOC_ITEMS:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.6
        r = p.add_run(item)
        set_run(r, size=12, bold=True, color=RGBColor(0x33, 0x33, 0x33))


def page_break(doc):
    doc.add_page_break()


def add_page_number(doc):
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r._r.append(fld_begin)
    r._r.append(instr)
    r._r.append(fld_end)
    set_run(r, size=9, color=GRAY)


# ================= 文档构建 =================
doc = Document()

# 页面设置：A4
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.54)
section.bottom_margin = Cm(2.54)
section.left_margin = Cm(2.8)
section.right_margin = Cm(2.8)

# 默认样式
normal = doc.styles["Normal"]
normal.font.name = FONT_EN
normal.font.size = Pt(12)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CN)

setup_heading_styles(doc)

add_page_number(doc)

# ================= 封面 =================
for _ in range(4):
    para(doc, "", line=1.0, space_after=0)
para(doc, "中国国际大学生创新大赛", size=26, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, font_cn=FONT_CN_HEAD, space_after=18)
para(doc, "项目计划书", size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, font_cn=FONT_CN_HEAD, space_after=42)
para(doc, "EDA AI 智能助手", size=20, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, font_cn=FONT_CN_HEAD, space_after=8)
para(doc, "—— 面向 PCB 设计的闭环验证式智能设计助手 ——", size=14, align=WD_ALIGN_PARAGRAPH.CENTER, color=GRAY, space_after=60)

cover_items = [
    ("赛道组别", "高教主赛道 · 创意组"),
    ("学校名称", "【吉林大学】"),
    ("所属学院", "【仪器科学与电气工程学院】"),
    ("专业班级", "【测控技术与仪器专业】"),
    ("项目负责人", "【姓名】"),
    ("团队成员", "【姓名1、姓名2、姓名3、姓名4】"),
    ("指导教师", "【姓名】"),
    ("申报日期", "2026 年 月"),
]
ct = doc.add_table(rows=len(cover_items), cols=2)
ct.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, (k, v) in enumerate(cover_items):
    c0, c1 = ct.rows[i].cells
    c0.width = Cm(4.0)
    c1.width = Cm(10.0)
    cell_text(c0, k, size=12, bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    cell_text(c1, v, size=12, align=WD_ALIGN_PARAGRAPH.LEFT)
    c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    # 去掉边框（封面用无边框表格）
    for c in (c0, c1):
        tcPr = c._element.get_or_add_tcPr()
        borders = OxmlElement("w:tcBorders")
        for edge in ("top", "left", "bottom", "right"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "nil")
            borders.append(e)
        tcPr.append(borders)

page_break(doc)

# ================= 目录 =================
h1(doc, "目  录")
add_toc(doc)
page_break(doc)

# ================= 一、执行摘要 =================
h1(doc, "一、执行摘要")

h2(doc, "1.1 项目简介")
para(doc, "EDA AI 智能助手是一款面向 PCB（印制电路板）设计的闭环验证式智能设计助手，由本团队自主开发，"
          "面向电子工程师、硬件创客、高校师生与中小电子企业。系统以自然语言交互为入口，集成 BOM 智能管理、"
          "71 条 PCB 设计规则自动检查、多智能体协同审查、本地 RAG 知识库、电路参数计算引擎等核心能力，"
          "并首创“LLM 建议 → 规则引擎验证 → 反馈修正 → 迭代收敛”的闭环验证引擎，"
          "从根源上解决大语言模型在硬件设计领域的“幻觉”问题，让 AI 给出的每一条设计建议都经过规则验证、安全可信。", indent=True)

h2(doc, "1.2 核心创新点")
bullet(doc, "闭环验证引擎：LLM 生成建议 → 规则引擎实时验证 → 不一致自动反馈 → 迭代收敛，首创 PCB 级闭环验证；")
bullet(doc, "自研轻量 ML 三模型：意图理解、元件识别、变更风险预测，总参数不足 100 万，全部离线 CPU 推理，摆脱云端 API 依赖；")
bullet(doc, "DRC 守门机制：基于评分阈值的“守门”拦截危险建议，实验证明可避免 18.2 分设计质量损失；")
bullet(doc, "“从检测到预测”：FP-Growth 违规关联规则挖掘 + BOM 变更风险预测，实现主动质量保障。")

h2(doc, "1.3 已取得成果")
bullet(doc, "71 条 PCB 设计规则、719 项自动化测试全部通过；")
bullet(doc, "5 块真实开源 PCB 设计构建测试数据集（BOM + 坐标 + 网表 + 飞针测试）；")
bullet(doc, "四阶段实验框架（DRC 基线 / 闭环验证 / 多智能体审查 / 缺陷注入），缺陷注入检出率 98%；")
bullet(doc, "多智能体审查对 4 块真实板评分 93~96 分（A 级），闭环收敛率 65%，幻觉消除率 76.5%。")

# ================= 二、背景与痛点 =================
h1(doc, "二、项目背景与市场痛点")

h2(doc, "2.1 行业背景")
para(doc, "PCB 是几乎所有电子产品的载体，中国是全球最大的 PCB 生产基地，产量占全球一半以上。"
          "在 PCB 设计环节，设计规则检查（DRC）、信号完整性、电源完整性（PDN）、电磁兼容（EMC）等专业检查"
          "直接决定了产品能否一次性打样成功、能否稳定量产。与此同时，EDA（电子设计自动化）工具国产化"
          "被列入国家“十四五”与集成电路产业政策重点方向，AI 与 EDA 的深度融合已成为行业公认的下一代竞争高地。", indent=True)

h2(doc, "2.2 市场痛点")
bullet(doc, "人工检查低效易漏：工程师依赖经验逐项核对设计规则，中小团队缺乏专业检查手段，返工成本高；")
bullet(doc, "大模型“幻觉”风险：通用大模型直接用于硬件设计会给出看似合理实则危险的建议（如误删复位电容），缺乏验证闭环；")
bullet(doc, "专业知识壁垒高：信号完整性、PDN、热设计等专业知识门槛高，高校学生与创客难以掌握；")
bullet(doc, "现有 EDA 工具不智能：主流 EDA 的 DRC 规则固定、只能“报错”，无法理解设计意图、无法给出可执行的改进建议。")

h2(doc, "2.3 现有解决方案的不足")
para(doc, "商业 EDA 巨头（Cadence、Synopsys）的 AI 能力聚焦于芯片级与云端布局布线，面向中小用户成本高、门槛高；"
          "国内立创 EDA 的 AI 插件为单一大模型问答，缺乏规则验证与多模型协同；"
          "学术界虽有 DRC 自动生成（DRC-Coder）等研究，但均面向芯片级（IC）而非 PCB 级，且缺乏中文开源生态。"
          "PCB 级“AI 建议 + 规则验证 + 闭环修正”的组合能力目前仍属空白。", indent=True)

# ================= 三、产品与技术方案 =================
h1(doc, "三、产品与技术方案")

h2(doc, "3.1 产品定位与总体架构")
para(doc, "系统定位为“面向立创 EDA 生态的智能设计助手”：以自然语言交互为统一入口，"
          "通过多 LLM 智能路由网关（支持 DeepSeek、OpenAI、通义千问、智谱、Kimi、豆包等 10 家厂商）"
          "将不同任务分派到最优模型，再经闭环验证引擎对 AI 输出进行规则验证与修正，最终以可视化形式呈现设计质量。", indent=True)
para(doc, "总体架构自上而下分为五层：", indent=True)
bullet(doc, "交互层：Eel Web 界面 + 系统托盘 + 全局热键，支持多助手实例、双窗口/伴生模式；")
bullet(doc, "智能层：NLU 意图识别 + 多 LLM 路由 + Function Calling Agent Loop（多步复杂任务自主编排）；")
bullet(doc, "业务层：BOM 管理、设计规则检查、多智能体审查、电路计算引擎、RAG 知识库；")
bullet(doc, "验证层：闭环验证引擎 + 迭代收敛状态机（6 种终止状态）；")
bullet(doc, "数据层：SQLite 会话持久化、ChromaDB 本地知识库、5 块真实 PCB 数据集。")

h2(doc, "3.2 核心功能模块")
add_table(doc,
    ["模块", "核心能力"],
    [
        ["BOM 智能管理", "CSV/Excel 解析、规则合并、AI 辅助合并、封装校验、位号查重、参数归一化、HTML 交互式 BOM"],
        ["设计规则检查", "71 条规则：去耦电容、信号/电源线宽、阻抗匹配、PDN 目标阻抗、过孔密度、模数分离等"],
        ["多智能体审查", "5 个专业 Agent（电源/信号/热/EMC/可制造性）并行审查、辩论合成、6 维度雷达图评分"],
        ["RAG 知识库", "ChromaDB 本地索引 11 类中文 PCB 知识（IPC 标准、高速设计、信号/电源完整性、EMC、DFM 等）"],
        ["电路计算引擎", "IPC-2221 电流承载、IPC-2141 阻抗、去耦 Z-F 曲线、PDN 目标阻抗、热估算（零 LLM 依赖）"],
        ["闭环验证引擎", "LLM 建议 → 规则验证 → 反馈修正 → 迭代收敛，从根源消除硬件领域幻觉"],
        ["AI 验证地图", "DRC 违规热力图 + AI 变更四色标记 + 多智能体发现叠加的交互式可视化"],
        ["供应链健康", "立创商城库存/生命周期/替代料/成本估算"],
    ],
    widths=[4.0, 12.0])

h2(doc, "3.3 关键技术路线")
para(doc, "项目采用“三路线融合”技术路线：", indent=True)
bullet(doc, "路线一（文本解析）：解析立创 EDA 的 BOM、坐标、网表、飞针测试数据，支撑精确的电气规则检查；")
bullet(doc, "路线二（视觉分析）：VLM 多模态模型分析原理图/PCB 截图，判断布局、散热、EMC 等全局问题；")
bullet(doc, "路线三（闭环融合）：文本解析负责精确规则校验，视觉分析负责布局审查，闭环验证引擎统一验证与修正。")

# ================= 四、核心创新点 =================
h1(doc, "四、核心创新点")

h2(doc, "4.1 创新点一：闭环验证引擎（核心）")
para(doc, "针对“大模型在硬件领域会产生幻觉、给出危险建议”这一痛点，本项目首创 PCB 级闭环验证引擎："
          "LLM 生成设计建议后，由二次调用将文本建议解析为结构化 BOM 变更，经合法性校验后应用到设计副本，"
          "再运行规则引擎对比基线计算增量（Δ），一旦发现新引入的违规，立即反馈给 LLM 修正并循环（最多 3 轮），"
          "直至收敛。配套的迭代收敛状态机以指纹重复、周期振荡、连续发散等策略判定 CONVERGED/STAGNATED/OSCILLATING/DIVERGED 六种终止状态。", indent=True)
para(doc, "实验证明：闭环验证可自动捕获“将全部 100nF 改为 1µF 却误删 MCU 复位电路所需电容”等危险建议，"
          "平均 2.1 轮修正，幻觉消除率达 76.5%。", indent=True)

h2(doc, "4.2 创新点二：自研轻量 ML 三模型")
para(doc, "为摆脱对云端大模型 API 的依赖、实现离线可用的设计质量保障，团队从零构建了三个功能专一的轻量 ML 模型，"
          "全部基于字符级 TextCNN，总参数不足 100 万，模型文件合计小于 3.5MB，双模型串联 CPU 推理耗时小于 2ms：", indent=True)
add_table(doc,
    ["模型", "参数量", "任务", "验证准确率"],
    [
        ["意图分类器", "~24.4 万", "10 类用户意图识别", "99.09%"],
        ["元件类型分类器", "~60 万", "12 细类 / 4 粗类元件识别", "99.24%"],
        ["变更风险预测器", "~10 万", "21 维特征工程 + 逻辑回归，BOM 变更风险预检", "风险排序正确"],
    ],
    widths=[4.5, 3.0, 6.5, 2.5])

h2(doc, "4.3 创新点三：DRC 守门机制")
para(doc, "系统引入基于评分的“守门”机制（评分下降超过阈值即判定未收敛），"
          "对被拒绝的危险建议计算其“避免的质量损失”（risk_prevented）。"
          "完整重跑实验中，DRC 守门共拦截 6 条危险建议，累计避免 18.2 分设计质量损失，"
          "所有建议的 Δ 恒为非负，从根本上保证了“AI 只会让设计变得更好、不会变差”。", indent=True)

h2(doc, "4.4 创新点四：从“检测”到“预测”")
para(doc, "在“事后检测”之外，项目进一步引入“事前预测”："
          "一方面基于 FP-Growth 关联规则挖掘与 Fisher 显著性检验，挖掘“违规—违规”的共现模式；"
          "另一方面训练 BOM 变更风险预测器，在建议应用前预检风险。"
          "风险排序结果符合工程直觉（晶振改频 > 电容 10 倍 > IC 封装 > 电阻微调），实现主动式质量保障。", indent=True)

h2(doc, "4.5 创新点五：置信度校准")
para(doc, "对自研模型的输出概率进行 Temperature Scaling 校准，"
          "意图模型 ECE 由 0.0159 降至 0.0098，元件模型 ECE 由 0.0090 降至 0.0056，"
          "使模型给出的置信度真实可信，为后续风险判断提供可靠的概率依据。", indent=True)

h2(doc, "4.6 创新点六：AI 验证地图可视化")
para(doc, "区别于传统“展示 BOM”的 2D/3D 查看器，项目首创“AI 验证地图”："
          "将 DRC 违规密度以热力图形式叠加到元件位置图，并用四色圆环标记每一条 AI 变更（安全/修正/危险/纯分析），"
          "回答“问题在哪里、AI 发现了什么、AI 建议是否安全”——这是现有所有 EDA 工具都不具备的能力。", indent=True)

# ================= 五、实验验证与成果 =================
h1(doc, "五、实验验证与成果")

h2(doc, "5.1 真实 PCB 数据集")
para(doc, "为验证系统有效性，团队从立创开源广场（oshwhub）下载了 5 块真实开源设计，"
          "每块均含完整 BOM、贴片坐标、网表与飞针测试数据，覆盖 STM32 最小系统、ESP32 音频、无刷电调、DC-DC 电源、智能 UV 灯等典型场景。", indent=True)
add_table(doc,
    ["设计", "类别", "核心器件", "元件数"],
    [
        ["esp32_audio_moji2", "ESP32 + 音频", "ESP32-C5-WROOM-1", "39"],
        ["stm32f103_devboard", "STM32 最小系统", "STM32F103C8T6", "19"],
        ["bldc_esc_motor", "电机驱动", "无刷电调", "28"],
        ["dcdc_power_v62", "DC-DC 电源", "V6.2 电源板", "94"],
        ["smart_uv_lamp_v2", "智能 UV 灯", "蜂鸣器 + 传感器类", "70 行 / 116 贴装"],
    ],
    widths=[4.5, 3.5, 4.5, 3.5])

h2(doc, "5.2 四阶段实验框架")
bullet(doc, "Phase A（DRC 基线）：对 4 块真实板进行基线规则检查，量化初始违规分布；")
bullet(doc, "Phase B（闭环验证）：LLM 建议 → 规则验证 → 反馈修正，测量收敛率与幻觉消除率；")
bullet(doc, "Phase C（多智能体）：5 个专业 Agent 并行审查，输出 6 维度质量评分；")
bullet(doc, "Phase D（缺陷注入）：向设计注入已知缺陷，验证系统的检出能力。")

h2(doc, "5.3 关键实验数据")
add_table(doc,
    ["指标", "实测值", "说明"],
    [
        ["设计规则数量", "71 条", "覆盖 BOM、PCB 布线、布局三大类"],
        ["自动化测试", "719 项全部通过", "含 36 项 API 集成测试"],
        ["缺陷注入检出率", "98%（39/40）", "5 类缺陷类型全覆盖"],
        ["多智能体审查评分", "93~96 分（A 级）", "4 块真实板，远超 75 分目标"],
        ["闭环收敛率", "65%", "含评分守门后的更严格判定"],
        ["平均修正轮次", "2.1 轮", "目标 ≤ 2.0"],
        ["幻觉消除率", "76.5%", "危险建议被规则引擎捕获"],
        ["DRC 守门避免损失", "18.2 分", "拦截 6 条危险建议"],
        ["意图识别准确率", "99.09%", "自研 TextCNN 模型"],
        ["元件分类准确率", "99.24%", "自研 TextCNN 模型"],
    ],
    widths=[4.5, 4.5, 7.0])

h2(doc, "5.4 成果与知识产权")
bullet(doc, "开源项目已托管于 GitHub（EDA AI 智能助手），MIT 协议，v0.8.0-dev 版本；")
bullet(doc, "软件著作权申请材料（PyInstaller 打包 + 用户手册）已规划，EI 论文（闭环验证引擎方向）撰写中；")
bullet(doc, "实验数据、四阶段实验框架、8 类论文级图表可复现。")

# ================= 六、市场分析 =================
h1(doc, "六、市场分析")

h2(doc, "6.1 市场规模")
para(doc, "中国 PCB 产量长期位居全球第一（约占全球产能 50% 以上），下游覆盖消费电子、汽车电子、工业控制、"
          "医疗电子等千亿级市场。EDA 作为 PCB 设计的关键工具，其国产化率仍处于较低水平，"
          "在国家政策推动下，国产 EDA 及围绕其生态的 AI 增强工具迎来高速增长窗口。"
          "面向中小团队与个人开发者的轻量、低价、中文友好的智能设计助手，是当前供给严重不足的细分市场。", indent=True)

h2(doc, "6.2 目标用户")
bullet(doc, "高校电子类专业师生：课程设计、电子设计竞赛、毕业设计中的 PCB 设计辅助与教学；")
bullet(doc, "硬件创客与个人开发者：借助开源硬件（ESP32/STM32）快速完成可靠设计；")
bullet(doc, "中小电子企业：以低成本获得专业级 DRC 与供应链健康检查能力。")

h2(doc, "6.3 竞争分析")
add_table(doc,
    ["竞品", "定位", "本项目差异"],
    [
        ["立创 EDA AI 插件", "单一大模型问答", "多模型路由 + 闭环验证 + 自研模型"],
        ["Cadence / Synopsys AI", "芯片级、云端布局布线", "PCB 级、面向中小用户、错位竞争"],
        ["KiCad MCP", "AI 操控 KiCad", "面向立创 EDA 中文生态（国内唯一）"],
        ["DRC-Coder 等学术工作", "IC 级 DRC 代码生成", "PCB 级规则自动生成（降维应用）"],
    ],
    widths=[4.5, 5.0, 6.5])

# ================= 七、商业模式 =================
h1(doc, "七、商业模式")
para(doc, "本项目处于创意组阶段，商业模式以“开源引流 + 增值服务”为核心：", indent=True)
bullet(doc, "开源社区版：免费开源，构建开发者生态与用户口碑；")
bullet(doc, "增值订阅版：面向企业提供供应链健康、团队协作、私有化部署等增值能力；")
bullet(doc, "场景化服务：面向高校实验教学、电子设计竞赛提供定制化课程与工具包。")
para(doc, "盈利来源包括：企业版订阅、私有化部署授权、教学内容服务、供应链数据增值服务等。", indent=True)

# ================= 八、团队介绍 =================
h1(doc, "八、团队介绍")
para(doc, "（以下信息为占位，请按实际情况填写）", color=GRAY, size=10.5)
add_table(doc,
    ["姓名", "专业", "团队分工", "主要贡献"],
    [
        ["【负责人姓名】", "【测控技术与仪器】", "项目统筹 / 算法", "闭环验证引擎、收敛状态机设计"],
        ["【成员2】", "【专业】", "后端开发", "规则引擎、电路计算引擎"],
        ["【成员3】", "【专业】", "前端 / UI", "Web 界面、AI 验证地图可视化"],
        ["【成员4】", "【专业】", "数据 / 测试", "PCB 数据集、四阶段实验、测试"],
    ],
    widths=[3.5, 3.5, 3.5, 5.5])
para(doc, "指导教师：【姓名】，【职称】，研究方向【……】。", indent=True)

# ================= 九、财务预测 =================
h1(doc, "九、财务预测（简要）")
para(doc, "创意组阶段项目以技术研发与产品打磨为主，前期投入主要集中于算力（大模型 API）与测试设备，"
          "成本可控。随着企业版增值服务与私有化部署落地，预计第二年起实现正向现金流。具体财务测算如下（示意）：", indent=True)
add_table(doc,
    ["年度", "研发投入（万元）", "预期收入（万元）", "说明"],
    [
        ["第 1 年", "3~5", "0~2", "产品打磨、种子用户积累"],
        ["第 2 年", "5~8", "10~20", "企业版订阅 + 教学服务"],
        ["第 3 年", "8~12", "30~50", "私有化部署 + 增值服务放量"],
    ],
    widths=[2.5, 4.0, 4.0, 5.5])

# ================= 十、风险分析与对策 =================
h1(doc, "十、风险分析与对策")
add_table(doc,
    ["风险类型", "风险描述", "应对措施"],
    [
        ["技术风险", "大模型幻觉、规则覆盖不全", "闭环验证引擎 + DRC 守门 + 持续扩充规则与数据集"],
        ["市场风险", "商业 EDA 巨头下沉竞争", "错位竞争，聚焦中小用户与中文开源生态"],
        ["数据风险", "真实设计样本不足", "持续收集 oshwhub 开源设计，扩充至 20~30 块以提升统计功效"],
        ["知识产权", "核心算法被模仿", "申请软著、规划论文，构建数据与规则壁垒"],
    ],
    widths=[3.0, 6.0, 7.0])

# ================= 十一、发展规划 =================
h1(doc, "十一、发展规划")
add_table(doc,
    ["阶段", "时间", "主要目标"],
    [
        ["近期", "2026 下半年", "完成 EI 论文投稿、软件著作权申请、扩充数据集至 20+ 块真实设计"],
        ["中期", "2027 上半年", "PyInstaller 打包发布、接入更多 EDA（KiCad）、企业试用落地"],
        ["远期", "2027 下半年起", "私有化部署、教学服务、供应链数据增值，形成可持续商业模式"],
    ],
    widths=[2.5, 3.5, 10.0])

page_break(doc)

# ================= 附录 =================
h1(doc, "附录：项目关键数据汇总")
add_table(doc,
    ["类别", "数据"],
    [
        ["项目版本", "v0.8.0-dev"],
        ["设计规则", "71 条"],
        ["自动化测试", "719 项全部通过"],
        ["真实 PCB 数据集", "5 块（BOM + 坐标 + 网表 + 飞针测试）"],
        ["自研 ML 模型", "3 个（意图 / 元件 / 变更风险），总参数 < 1M"],
        ["支持 AI 厂商", "10 家（DeepSeek/OpenAI/Gemini/Claude/通义千问/智谱/Kimi/豆包/MiniMax/硅基流动）"],
        ["审查 Agent", "5 个（电源/信号/热/EMC/可制造性）"],
        ["缺陷注入检出率", "98%（39/40）"],
        ["多智能体审查评分", "93~96 分（A 级）"],
        ["闭环收敛率 / 幻觉消除率", "65% / 76.5%"],
        ["开源地址", "https://github.com/Lin-666spring/eda_ai_assistant"],
    ],
    widths=[5.0, 11.0])

doc.save(OUT)
print("已生成：", OUT)
