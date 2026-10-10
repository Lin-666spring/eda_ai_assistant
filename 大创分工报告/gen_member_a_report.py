# -*- coding: utf-8 -*-
"""⚠️ 本文件内嵌的代码片段是 2026 年早期的规则引擎副本，与现行实现（src/rules/）
已发生漂移，仅作大创汇报的 historical 展示用途 —— 不要以此为参考改代码（2026-10-10 声明）。
Original docstring: 成员A个人汇报文档。运行: python gen_member_a_report.py"""
import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = os.path.dirname(os.path.abspath(__file__))

def set_run(run, name='宋体', size=10.5, bold=False, color=None, mono=False):
    if mono:
        run.font.name = 'Consolas'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Consolas')
    else:
        run.font.name = name
        r = run._element.rPr.rFonts
        r.set(qn('w:eastAsia'), name); r.set(qn('w:ascii'),'Times New Roman'); r.set(qn('w:hAnsi'),'Times New Roman')
    run.font.size = Pt(size); run.font.bold = bold
    if color: run.font.color.rgb = RGBColor(*color)

def para(doc, text, size=10.5, bold=False, align=None, name='宋体', space_after=6, color=None, first=False):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(space_after); p.paragraph_format.line_spacing = 1.35
    if align: p.alignment = align
    r = p.add_run(text); set_run(r, name=name, size=size, bold=bold, color=color); return p

def title(doc, text, size=25, color=(0x0B,0x39,0x6E)):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(50); p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text); set_run(r, name='黑体', size=size, bold=True, color=color); return p

def subtitle(doc, text, size=13, color=(0x2F,0x4F,0x8C)):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text); set_run(r, name='黑体', size=size, bold=True, color=color); return p

def h1(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(16); p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text); set_run(r, name='黑体', size=14, bold=True, color=(0x0B,0x39,0x6E)); return p

def h2(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(12); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text); set_run(r, name='黑体', size=12, bold=True, color=(0x1F,0x3B,0x6B)); return p

def bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet'); p.paragraph_format.space_after = Pt(3); p.paragraph_format.line_spacing = 1.3
    if bold_prefix:
        r = p.add_run(bold_prefix); set_run(r, bold=True)
    r = p.add_run(text); set_run(r); return p

def code_block(doc, code):
    for line in code.strip('\n').split('\n'):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0; p.paragraph_format.left_indent = Pt(8)
        r = p.add_run(line if line else ' '); set_run(r, mono=True, size=8.5)
    sp = doc.add_paragraph(); sp.paragraph_format.space_after = Pt(2)

def table(doc, headers, rows, widths=None, header_fill='D9E2F3'):
    t = doc.add_table(rows=1, cols=len(headers)); t.style='Table Grid'; t.alignment=WD_TABLE_ALIGNMENT.CENTER
    for i,h in enumerate(headers):
        c=t.rows[0].cells[i]; c.text=''
        r=c.paragraphs[0].add_run(h); set_run(r,bold=True,size=9.5,name='黑体')
        tcPr=c._tc.get_or_add_tcPr(); shd=OxmlElement('w:shd'); shd.set(qn('w:val'),'clear'); shd.set(qn('w:fill'),header_fill); tcPr.append(shd)
    for row in rows:
        cells=t.add_row().cells
        for i,val in enumerate(row):
            cells[i].text=''; r=cells[i].paragraphs[0].add_run(str(val)); set_run(r,size=9.5)
    if widths:
        for i,w in enumerate(widths):
            for row in t.rows: row.cells[i].width = Inches(w)
    return t

def build():
    doc = Document()

    # ─── 封面 ───
    title(doc, '智绘PCB——AI 智能 PCB 设计助手')
    subtitle(doc, '大创项目成员个人工作汇报')
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before = Pt(36)
    for t in ('汇报人：成员 A（项目负责人）',
              '职责方向：核心引擎与规则系统（后端 / 设计规则 / Agent）',
              '大学生创新创业训练计划项目',
              '2026 年 9 月'):
        q = doc.add_paragraph(); q.alignment = WD_ALIGN_PARAGRAPH.CENTER; q.paragraph_format.space_after = Pt(5)
        r = q.add_run(t); set_run(r, size=13, color=(0x33,0x33,0x33))
    doc.add_page_break()

    # ─── 汇报提纲 ───
    h1(doc, '汇报提纲（约 10 分钟）')
    table(doc, ['环节', '内容', '时长'],
        [['1', '项目背景与我的定位', '1 分钟'],
         ['2', '六大核心模块工作详述（含代码）', '4.5 分钟'],
         ['3', '关键问题攻坚（两个真实踩坑故事）', '2 分钟'],
         ['4', '成果与量化指标', '1.5 分钟'],
         ['5', '工作量、创新点与下一步计划', '1 分钟']],
        widths=[0.7, 4.6, 1.1])
    para(doc, '一句话定位：我负责项目的底层引擎——让系统"懂电路、能检查、可收敛、可集成"。成员 B 的三个自研模型嵌在我的规则引擎里做元件语义识别，成员 C 的四阶段实验框架依赖我的 DRC、评分与接口产出全部论文数据。', bold=True)

    # ─── 一、项目背景与定位 ───
    h1(doc, '一、项目背景与我的定位')
    para(doc, '项目要解决的问题：大模型（LLM）进入 EDA 领域后能看懂原理图、能给修改建议，但它的建议不保证"安全"——删去耦电容、走线过细过大电流这类建议，LLM 会一本正经地给出来。我们的答案是闭环验证引擎：LLM 提出结构化 BOM 变更 → 我负责的 DRC 规则引擎即时检查 → 发现新违规或评分下降就反馈 LLM 修正 → 循环直至收敛或拦截。')
    para(doc, '系统数据流：Eel Web 前端 / 立创 EDA 插件 → AppController（我实现的调度大脑，UI 无关）→ NLU / Agent Loop → 24 个工具 → DRC（71 条规则）+ 六维评分 → 反馈闭环。我在数据流的中枢位置，B、C 两位成员的工作都建立在我的接口之上。')

    # ─── 二、职责总览 ───
    h1(doc, '二、职责范围总览')
    table(doc, ['模块', '核心文件', '规模/指标'],
        [['DRC 设计规则引擎', 'src/rules/checker.py', '71 条规则 / 16 大类'],
         ['元件语义分类', 'src/rules/checker.py', '三级策略，误报 176→3'],
         ['六维评分系统', 'src/core/design_scorer.py', '6 维度 + 7 级等级'],
         ['迭代收敛引擎', 'src/core/convergence.py', '468 行 / 6 终止状态'],
         ['Agent 工具系统', 'src/agent/tools.py 等', '24 工具（SSOT 设计）'],
         ['调度与集成', 'src/core/controller.py 等', 'UI 无关 / 双前端 / 打包']],
        widths=[1.9, 2.2, 2.3])

    # ─── 三、核心工作 ───
    h1(doc, '三、核心工作详述')

    h2(doc, '3.1 DRC 规则引擎（71 条规则，从关键词匹配到真实电路导向）')
    para(doc, '规则覆盖基础电气、去耦电容、晶振、特征阻抗、PDN 目标阻抗、信号完整性、EMC/EMI、DFM/热管理等 16 大类。最有代表性的是去耦电容检查的重构：旧逻辑是"全 BOM 有一个 100nF 就满足全部 / 一个没有就全部报错"，我改为"可用电容总量 vs 需去耦 IC 数量"的供需判断：')
    code_block(doc, r'''
def _check_decoupling_caps(self, bom_items, positions, netlist):
    violations = []
    ics, caps = [], []
    for item in bom_items:
        cls = _classify_component(item)     # 语义分类，非关键词
        if cls == "cap":  caps.append(item)
        elif cls == "ic": ics.append(item)
    # 按"可用 100nF/10µF 总量 vs IC 数"供需判断：
    # 全缺 → 逐 IC 报 ERROR；缺口 → 汇总一条 WARNING
''')
    bullet(doc, '每个 IC 的电源引脚应有匹配的去耦电容（基于 Z-F 分析），粒度贴合真实设计评审。')
    bullet(doc, '重构后四块板去耦虚假违规从 176 条降到 3 条，评分从 71.5(B) 提升到 93.5(A)。')

    h2(doc, '3.2 元件语义三级分类（本项目最关键的修复）')
    para(doc, '真实立创 BOM 的描述常只有值或型号（"100nF"、"AFC07"、"4kHz"），旧的关键词匹配会把电容/二极管/蜂鸣器/连接器误判成 IC，一条误判引发几十条虚假违规。我设计了"ML 优先 + 前缀安全网 + 规则回退"三级策略：')
    code_block(doc, r'''
def _classify_component(item) -> str:
    fine_type, confidence = _classify_component_fine(item)  # ① ML 优先
    if fine_type:
        coarse = FINE_TO_COARSE.get(fine_type, "other")
        prefix = reference_prefix(item)          # 位号字母前缀
        _non_ic_prefixes = ("C","R","L","D","Q","X","J","SW", ...)
        if coarse == "ic" and prefix in _non_ic_prefixes:
            return _classify_component_rule(item)  # ② 安全网：非IC前缀
        return coarse                             #    绝不接受 ic 误判
    return _classify_component_rule(item)          # ③ 规则回退
''')
    bullet(doc, '安全网的设计动机：ML 模型看到 D-ESD 器件描述里的 "USB/IC" 字眼会误判为 IC，而位号前缀 D 是硬证据——前缀优先于模型。')
    bullet(doc, '这是"信任 ML 但不迷信 ML"的工程化落地，也是成员 B 的模型能安全嵌入生产路径的原因。')

    h2(doc, '3.3 容值解析（覆盖 EIA 三位码）')
    code_block(doc, r'''
def _parse_capacitance(val_str: str):
    nv = ValueNormalizer.normalize(val_str)
    if nv.base_value: return nv.base_value
    if val_str.isdigit() and len(val_str) == 3:
        return int(val_str[0:2]) * 10 ** int(val_str[2]) * 1e-12
    return None          # "104" = 10×10^4 pF = 100nF
''')
    bullet(doc, '真实 BOM 大量使用 EIA 三位码，解析不了容值，所有电容相关规则都会失效——这是规则引擎的地基。')

    h2(doc, '3.4 六维评分系统（闭环 Δ 指标的基础）')
    para(doc, '把每条违规按规则名映射到电气/信号完整性/PDN/EMC/热/DFM 六个维度，各维度独立扣分再综合，输出等级（A+/A/B+…）。评分系统是"评分守门"机制的基础——LLM 建议即使不引入新违规，只要让评分下降超过 2.0 分，就会被拦截：')
    code_block(doc, r'''
for v in violations:
    for kw, (dim, weight) in RULE_DIMENSION_MAP.items():
        if kw in v.rule_name:
            v._weight = weight
            dim_violations[dim].append(v); break

def _assign_grade(score):
    if score >= 95: return "A+"
    elif score >= 88: return "A"
    ...  # B+/B/C/D/F
''')
    bullet(doc, '实测：eda_robotpro 板上 LLM 的危险建议让评分下降 3.7 分，守门机制把这条建议拦截，保护了设计——这就是 risk_prevented 指标的来源。')

    h2(doc, '3.5 迭代收敛引擎（判断 LLM 修正是否真正收敛）')
    para(doc, '闭环循环不能无限跑，要科学地判断"收敛/停滞/振荡/发散"。我实现了策略链驱动的状态机，6 种终止状态，纯逻辑零 IO：')
    code_block(doc, r'''
class StagnationPolicy(TerminationPolicy):
    """LLM 修正与上一轮建议同指（无进展）→ STAGNATED"""
    def evaluate(self, history):
        if len(history) < 2: return None
        cur, prev = history[-1], history[-2]
        if cur.fingerprint and cur.fingerprint == prev.fingerprint:
            return ConvergenceStatus.STAGNATED
        return None
''')
    bullet(doc, '策略链：阻断违规→停滞（指纹相同）→振荡（周期 2）→发散（连续递增/超 1.5×）→最大轮次，优先级递减。')
    bullet(doc, '每轮 RoundSnapshot 快照（指纹/问题签名/新增/解决），ConvergenceResult 可直接导出为论文数据。')

    h2(doc, '3.6 Agent 工具系统与系统集成')
    bullet(doc, 'ToolRegistry 单一事实来源（SSOT）：24 个工具只定义一次，Controller 分发表、关键词匹配、NLU 意图、LLM prompt、帮助文本、Function Calling schema 全部自动派生——加新能力只需加一个 ToolDef。')
    bullet(doc, 'AppController 是 UI 无关的调度大脑：Eel 前端和 CLI 原型消费同一套 API，保证引擎可独立测试。')
    bullet(doc, '集成层：Eel Web 双窗口/伴生模式（全局热键+托盘）、立创 EDA 插件、PyInstaller 一键打包为 exe。')

    # ─── 四、攻坚故事 ───
    h1(doc, '四、关键问题攻坚（两个真实故事）')
    h2(doc, '故事一：176 条去耦虚假违规的根因溯源')
    para(doc, '现象：四块真实板跑 DRC，去耦相关违规 176 条，明显不符合直觉（这些是开源广场验证过的设计）。排查发现根因不在规则本身，而在元件分类：蜂鸣器描述含 "IC"、连接器描述含 "USB"，被关键词匹配判成 IC，于是"每个 IC 都缺去耦电容"。修复方案就是 3.2 节的三级分类 + 3.3 节的容值解析。教训：规则引擎的上限取决于它对输入的语义理解，而不是规则数量。')
    h2(doc, '故事二：闭环实验 Δ 恒为 0 的假象')
    para(doc, '现象：完整闭环实验跑完 35 次，所有 Δ=0、所有建议被"接受"。这看起来是完美结果，实际是故障——LLM 解析调用全部 400 失败，走了无变更降级路径。根因：配置优先级 bug，.env 未显式设置模型名时，代码从用户设置文件里捡到残留的 gpt-5.5 发给了 DeepSeek。修复：.env 显式配置全套 provider/model/base_url。教训：① 实验框架必须能区分"真的没变更"和"调用失败降级"；② 看似完美的数据要先怀疑，我随后在日志里加了降级原因标记。')

    # ─── 五、成果 ───
    h1(doc, '五、成果与量化指标')
    h2(doc, '5.1 我负责模块的直接指标')
    table(doc, ['指标', '数值', '对照'],
        [['设计规则', '71 条（16 大类）', '申报书要求 15+，超额 4.7 倍'],
         ['去耦误报修复', '176 → 3 条', '评分 71.5(B) → 93.5(A)'],
         ['Agent 工具', '24 个', '要求 20+'],
         ['收敛引擎', '6 终止状态 / 468 行', '论文可直接导出'],
         ['测试', '719 条全部通过', '含 36 API + 真实板回归']],
        widths=[1.7, 2.0, 2.7])
    h2(doc, '5.2 支撑全组的实验成果（我的引擎在 7 真实板上的表现）')
    table(doc, ['实验', '结果'],
        [['DRC 基线', '7 块真实板全部跑通（board_schematic 47 违规 / 0 ERROR 等）'],
         ['Phase B 闭环', '35 次验证；危险建议"移除去耦电容"在 dcdc(22变更)/esp32(12)/stm32(8) 全部被拦截'],
         ['评分守门', '累计避免质量损失 4.8 分，其中单条建议避免 3.7 分'],
         ['Phase C 多智能体', '均分 93.5 / A 级（esp32 95.2 / A+）'],
         ['Phase D 缺陷注入', '检出率 30/31 = 96.8%']],
        widths=[1.9, 4.5])

    # ─── 六、创新点 ───
    h1(doc, '六、创新点（我的部分）')
    bullet(doc, '迭代收敛验证引擎（LLM→DRC→反馈→修正）：EDA 领域首个把 LLM 建议放进规则闭环里验证的工程化实现，35 次真实闭环数据支撑。', bold_prefix='① ')
    bullet(doc, 'DRC 评分守门：SCORE_DROP_TOLERANCE 机制，"不引入新违规"不再是安全的充分条件，评分下降同样触发拦截。', bold_prefix='② ')
    bullet(doc, '元件语义三级分类：ML 优先 + 位号前缀安全网 + 规则回退，解决真实 BOM 语义识别的行业性痛点。', bold_prefix='③ ')

    # ─── 七、工作量 ───
    h1(doc, '七、工作量')
    para(doc, '项目按 12 个月（含寒暑假）× 3 人推进。我承担的引擎层工作具有"地基"性质：规则建模、评分系统与收敛引擎需要反复调优回归；架构上完成 PCB 解析三路线选型对比、PyQt5→Eel 迁移论证、单/多 Agent 架构评审；71 条规则的边界场景打磨贯穿全程。考虑寒暑假全时投入、原型返工与文档沉淀成本，等效投入约 14.0 人月，占项目总工作量（约 36.5 人月）的 38%，为三人中最高，符合负责人定位。')

    # ─── 八、总结与下一步 ───
    h1(doc, '八、总结与下一步')
    para(doc, '总结：我交付了一套"懂电路"的底层引擎——71 条真实电路导向的规则、可解释的六维评分、科学的收敛判定，并把它集成为可独立测试、可打包交付的产品。这套引擎是全组论文数据（闭环 Δ、守门拦截、多智能体评分）的唯一来源。')
    para(doc, '下一步：① 配合软著材料提交（EDA AI 智能助手 V1.0）；② EI 论文 Method/Experiment 章节撰写，重点是把收敛引擎的 6 状态判定与 risk_prevented 指标形式化；③ 规则库向 20-30 块板规模扩展，支撑违规关联规则挖掘的统计显著性。')
    para(doc, '（汇报完，谢谢各位老师）', align=WD_ALIGN_PARAGRAPH.CENTER, bold=True)

    path = os.path.join(OUT, '大创汇报_成员A_核心引擎与规则系统.docx')
    doc.save(path)
    print('已生成:', path)

if __name__ == '__main__':
    build()
