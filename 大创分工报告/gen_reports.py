# -*- coding: utf-8 -*-
"""生成大创项目三人任务分工 Word 报告。运行: python gen_reports.py"""
import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------- 字体 ----------
def set_run(run, name='宋体', size=10.5, bold=False, color=None, mono=False):
    if mono:
        run.font.name = 'Consolas'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Consolas')
    else:
        run.font.name = name
        r = run._element.rPr.rFonts
        r.set(qn('w:eastAsia'), name)
        r.set(qn('w:ascii'), 'Times New Roman')
        r.set(qn('w:hAnsi'), 'Times New Roman')
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def para(doc, text, size=10.5, bold=False, align=None, name='宋体', space_after=6, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.35
    if align: p.alignment = align
    r = p.add_run(text)
    set_run(r, name=name, size=size, bold=bold, color=color)
    return p

def title(doc, text, size=26, color=(0x0B,0x39,0x6E)):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(60); p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text); set_run(r, name='黑体', size=size, bold=True, color=color)
    return p

def subtitle(doc, text, size=14, color=(0x2F,0x4F,0x8C)):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text); set_run(r, name='黑体', size=size, bold=True, color=color)
    return p

def h1(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(14); p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text); set_run(r, name='黑体', size=14, bold=True, color=(0x0B,0x39,0x6E))
    return p

def h2(doc, text):
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text); set_run(r, name='黑体', size=12, bold=True, color=(0x1F,0x3B,0x6B))
    return p

def bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(3); p.paragraph_format.line_spacing = 1.3
    if bold_prefix:
        r = p.add_run(bold_prefix); set_run(r, bold=True)
    r = p.add_run(text); set_run(r)
    return p

def code_block(doc, code):
    for line in code.strip('\n').split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.left_indent = Pt(8)
        r = p.add_run(line if line else ' ')
        set_run(r, mono=True, size=8.5)
    # 加个间隙
    sp = doc.add_paragraph(); sp.paragraph_format.space_after = Pt(2)

def shade_para(p, fill='F2F2F2'):
    shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill)
    p._p.get_or_add_pPr().append(shd)

def table(doc, headers, rows, widths=None, header_fill='D9E2F3'):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ''
        r = hdr[i].paragraphs[0].add_run(h); set_run(r, bold=True, size=9.5, name='黑体')
        tcPr = hdr[i]._tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd'); shd.set(qn('w:val'),'clear'); shd.set(qn('w:fill'), header_fill)
        tcPr.append(shd)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ''
            r = cells[i].paragraphs[0].add_run(str(val)); set_run(r, size=9.5)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    return t

def cover(doc, title_text, sub_text, member, role):
    title(doc, title_text)
    subtitle(doc, sub_text)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(40)
    for t in (member, role, '大学生创新创业训练计划项目 分工报告', '2026年9月'):
        q = doc.add_paragraph(); q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        q.paragraph_format.space_after = Pt(4)
        rr = q.add_run(t); set_run(rr, size=13, color=(0x33,0x33,0x33))
    doc.add_page_break()

# ============ 报告A ============
def report_a():
    doc = Document()
    cover(doc, '智绘PCB——AI 智能 PCB 设计助手', '大学生创新创业训练计划项目', '成员 A（负责人）', '核心引擎与规则系统 · 后端 / 规则 / Agent')

    para(doc, '本报告为项目「智绘PCB——AI智能PCB设计助手」三人分工报告中成员 A 的分册，聚焦核心引擎、设计规则系统与智能体编排。成员 A 担任项目负责人，承担最底层的规则引擎、评分系统、收敛引擎与系统集成，是项目技术架构的奠基人。')
    para(doc, '协作关系：成员 B 提供三自研 ML 模型与知识库（依赖 A 的规则引擎做元件语义分类与校验），成员 C 提供前端可视化与实验验证（依赖 A 的 agent/rest 接口做数据交互）。A 的产出被 B、C 广泛调用，为全项目数据流的中枢。')

    h1(doc, '一、主要研究内容')

    h2(doc, '1.1 DRC 设计规则引擎（71 条规则，16 大类）')
    para(doc, '设计规则检查（Design Rule Check）是项目的核心能力，覆盖基础电气、去耦电容、晶振、特征阻抗匹配、PDN 目标阻抗、信号完整性、EMC/EMI、DFM/热管理等 16 大类。共编码 71 条规则，从关键词匹配升级为基于真实电路计算与元件语义分类的智能检查。')
    para(doc, '关键技术：元件语义分类。真实立创 EDA 的 BOM 描述常只是值或型号（如 "100nF"、"AFC07"），靠关键词分类会把电容/二极管/连接器误判为 IC，造成大量虚假违规。为此实现"ML 模型优先 + 位号前缀安全网 + 规则回退"的三级分类策略：')
    code_block(doc, r'''
def _classify_component(item) -> str:
    """按位号前缀 + 描述关键词分类：'ic'|'cap'|'passive'|'other'。"""
    from src.ml.component_classifier import FINE_TO_COARSE
    # ── ① ML 模型优先 ──
    fine_type, confidence = _classify_component_fine(item)
    if fine_type:
        coarse = FINE_TO_COARSE.get(fine_type, "other")
        # 安全网：明确非 IC 的前缀绝不接受 ML 的 ic 分类
        ref_list = item.reference_list
        ref = ref_list[0] if ref_list else ""
        prefix = "".join(ch for ch in ref if ch.isalpha()).upper()
        _non_ic_prefixes = (
            "C","R","RN","RNC","L","FB",            # 电容/电阻/电感
            "D","LED","Q","T","SCR","TRIAC",        # 二极管/三极管/MOSFET
            "X","Y","XTAL","OSC",                   # 晶振
            "J","CN","CON","HDR","P","FPC","TP",    # 连接器
            "SW","K","S","BUTTON","BUZZ","BZ",      # 开关/蜂鸣器
            "F","FU","RL","RELAY",                 # 保险丝/继电器
        )
        if coarse == "ic" and prefix in _non_ic_prefixes:
            return _classify_component_rule(item)   # ML 误判，回退规则
        return coarse
    return _classify_component_rule(item)
''')
    para(doc, '同时实现容值解析（含 EIA 三位码，如 "104" = 100nF）、元件计数（quantity × 多位号，真实 BOM 常以逗号分隔多位号同行）。修复后四块板的去耦虚假违规从 176 条降为 3 条，评分从 71.5(B) 提升至 93.5(A)。')

    h2(doc, '1.2 DesignScorer 多维评分系统')
    para(doc, '设计质量评分从电气、信号完整性、PDN、EMC、热、DFM 六个维度综合。采用平方根衰减函数处理惩罚项，避免线性无下限归零导致部分严重违规设计分数不可恢复：')
    code_block(doc, r'''
    score = 100 - 2.2 * sqrt(total_penalty)   # 平方根衰减，兑现原注释承诺
    # 每类违规按严重度加权，error>warning>info
''')
    para(doc, '评分系统是闭环验证"Δ 指标"与"评分守门"的基础（见 §2.4），也是团队成员绩效量化的客观依据。')

    h2(doc, '1.3 迭代收敛引擎（convergence.py，468 行）')
    para(doc, '闭环验证引擎需要判断 LLM 建议的修正过程是否真正收敛。为此实现策略驱动的状态机，定义 6 种终止状态，纯逻辑零 IO，与 verifier 分离：')
    bullet(doc, '终止策略链：BlockingIssues → Stagnation（指纹重复）→ Oscillation（周期2）→ Divergence（连续递增/超1.5×）→ MaxRounds')
    bullet(doc, 'RoundSnapshot 逐轮快照（指纹/问题签名/新增/解决/延迟），ConvergenceResult.to_dict() 供论文导出')
    bullet(doc, '配置：max_rounds=3, divergence_factor=1.5, streak=2')
    code_block(doc, r'''
class StagnationPolicy(TerminationPolicy):
    """LLM 修正与上一轮同指（无进展）→ STAGNATED。"""
    def evaluate(self, history):
        if len(history) < 2: return None
        cur, prev = history[-1], history[-2]
        if cur.fingerprint and cur.fingerprint == prev.fingerprint:
            return ConvergenceStatus.STAGNATED
        return None
''')

    h2(doc, '1.4 Agent 与工具系统（24 工具，Function Calling Agent Loop）')
    para(doc, '以 ToolRegistry 为唯一事实来源（SSOT），所有能力从同一份 TOOLS 列表派生：Controller 分发表、关键词匹配表、NLU 意图关键词、LLM prompt 操作表、帮助文本、Function Calling schema。支持多步复杂任务编排，Agent 自主决策调用工具、执行、回传、循环直至得出最终答复（上限 5 轮）。')

    h2(doc, '1.5 系统集成与部署')
    para(doc, '双前端架构（FastAPI + 立创 EDA 扩展）、Eel Web UI 替换 PyQt5、多实例/双窗口/伴生模式、全局热键与系统托盘、PyInstaller 打包配置、文件监听自动同步。')

    h1(doc, '二、关键技术实现（代码选段）')
    for t in ['元件语义分类（_classify_component）','容值解析（含 EIA 三位码）']:
        para(doc, t, bold=True)
    code_block(doc, r'''
def _parse_capacitance(val_str: str):
    """解析容值字符串（含 EIA 三位码），返回法拉。"""
    if not val_str: return None
    val_str = val_str.strip().upper().replace(" ", "")
    nv = ValueNormalizer.normalize(val_str)
    if nv.base_value: return nv.base_value
    if val_str.isdigit() and len(val_str) == 3:      # "104" = 10*10^4 pF
        return int(val_str[0:2]) * 10 ** int(val_str[2]) * 1e-12
    return None
''')

    h1(doc, '三、研究成果与量化指标')
    table(doc,
        ['成果', '量化指标', '达成情况'],
        [
            ['设计规则引擎', '71 条规则（申报书要求 15+）', '超额 4.7×'],
            ['元件语义分类', '分类准确率 99.24%（12 细类）', '达标'],
            ['工具系统', '24 个 Agent 工具（要求 20+）', '超标'],
            ['评分系统', '平方根衰减 + 六维度', '已实现'],
            ['收敛引擎', '6 终止状态 + 468 行', '已实现'],
            ['测试', '719 条测试全部通过', '达标'],
            ['去耦误报修复', '虚假违规 176→3，评分 71.5→93.5(A)', '核心优化'],
        ], widths=[1.6,2.8,2.0])

    h1(doc, '四、创新点与项目贡献')
    bullet(doc, '迭代收敛验证引擎：LLM→DRC→反馈→修正，与 B、C 协作完成 7 真实板 35 次闭环验证，守门拦截 4.8 分质量损失', bold_prefix='① ')
    bullet(doc, 'DRC 守门机制：SCORE_DROP_TOLERANCE=2.0，评分下降超阈值即拦截危险建议，保障设计不被"改坏"', bold_prefix='② ')
    bullet(doc, '元件语义分类三级策略，解决真实 BOM 关键词误判痛点', bold_prefix='③ ')

    h1(doc, '五、工作量说明')
    para(doc, '项目自启动以来按 12 个月（含寒暑假）× 3 人团队全力推进，实际投入超出常规预估。成员 A 以核心引擎与系统集成为主，除规则建模、评分系统与收敛引擎等核心研发外，还承担大量研究型与工程型任务：PCB 解析三路线选型对比、PyQt5→Eel 迁移论证、单/多 Agent 架构评审、24 工具系统多轮迭代、71 条规则的边界场景反复打磨与回归。考虑寒暑假全时投入、原型返工与文档沉淀成本，等效投入约 14.0 人月，占项目总工作量（约 36.5 人月）的 38%，为三人中占比最高，符合负责人定位。', bold=True)
    doc.save(os.path.join(OUT, '大创任务分工报告_成员A_核心引擎与规则系统.docx'))

# ============ 报告B ============
def report_b():
    doc = Document()
    cover(doc, '智绘PCB——AI 智能 PCB 设计助手', '大学生创新创业训练计划项目', '成员 B', 'AI 算法与知识库 · 机器学习 / 大模型')

    para(doc, '本报告为「智绘PCB——AI智能PCB设计助手」三人分工报告中成员 B 的分册，聚焦自研轻量机器学习模型、置信度校准与 PCB 领域知识库。成员 B 负责让系统"更懂 PCB 设计"，从云端 API 依赖走向完全离线、可解释、可部署的 AI 能力。')
    para(doc, '协作关系：B 的意图分类器供 NLU 引擎使用（本地优先→关键词回退→远程兜底），元件分类器供 A 的 DRC 规则引擎做语义识别，变更风险预测器供 C 的闭环实验做预检拦截。B 的模型是连接 A、C 的智能核心。')

    h1(doc, '一、主要研究内容')

    h2(doc, '1.1 三自研轻量 ML 模型（总参数 < 1M，全部离线、CPU 推理 < 2ms）')
    para(doc, '为替代云端 API 依赖，从零构建三个功能专一的字符级 TextCNN 模型，轻量、快速、可部署：')
    table(doc,
        ['模型', '参数', '用途', '准确率', '模型文件'],
        [
            ['意图分类器', '≈244K', '10 类自然语言意图识别', '99.09%', '960KB'],
            ['元件类型分类器', '≈600K', '12 细类→4 粗类映射', '99.24%', '2.3MB'],
            ['变更风险预测器', '≈100K', 'BOM 变更风险（21 维特征）', '0.671', '—'],
        ], widths=[1.4,1.0,2.0,1.1,1.0])
    para(doc, '意图分类器核心是字符级 TextCNN：输入文本 → 字符 Embedding → 多尺度 Conv1D → GlobalMaxPool → 分类头。三种不同卷积核尺度并行提取局部 n-gram 特征，再拼接得到全局表征。')
    code_block(doc, r'''
def forward(self, input_ids):
    # Embedding + 调整维度给 Conv1d
    x = self.embedding(input_ids).transpose(1, 2)
    conv_outputs = []
    for conv in self.convs:                     # 多尺度卷积
        y = conv(x); y = F.relu(y)
        y = F.max_pool1d(y, y.size(2))          # GlobalMaxPool
        conv_outputs.append(y.squeeze(2))
    x = torch.cat(conv_outputs, dim=1)          # 拼接多尺度特征
    x = self.dropout(x)
    x = F.relu(self.fc1(x))
    x = self.fc2(x)                             # (batch, num_classes)
    return x
''')

    h2(doc, '1.2 置信度校准（Temperature Scaling）')
    para(doc, '模型输出的置信度往往过于自信，直接用于拒识/预检不可靠。实现温度缩放校准，并引入 ECE（期望校准误差）/ MCE 评估 + 可靠性图数据，校准模型已部署到主推理路径：')
    bullet(doc, '意图分类器：ECE 0.0159 → 0.0098（T=0.896）')
    bullet(doc, '元件分类器：ECE 0.0090 → 0.0056（T=0.783）')
    code_block(doc, r'''
def predict(self, input_ids):
    self.eval()
    with torch.no_grad():
        logits = self.forward(input_ids) / self.temperature   # 应用校准温度
        probs = F.softmax(logits, dim=1)
        best_idx = probs.argmax(dim=1)
        intents = [IDX_TO_INTENT[i.item()] for i in best_idx]
        confidences = probs.max(dim=1).values.tolist()
    return intents, confidences
''')

    h2(doc, '1.3 违规知识挖掘（FP-Growth + 关联规则 + Fisher 检验）')
    para(doc, '从检查结果中挖掘"违规与违规/元件类型"的关联规则，为设计师提供经验性指导。采用 FP-Growth 频繁项集挖掘 + 关联规则提取 + Fisher 显著性检验过滤 + 电路类型模式命名。输出 violation_association_rules.md 规则报告。（注：当前 7 真实板 + 3 合成板，板级统计功效仍有限，需 20-30 块板方能出论文级显著结果。）')

    h2(doc, '1.4 RAG 知识库（11 文件 / 2041 行 / 8 大类）')
    para(doc, '构建 PCB 领域知识库，涵盖 IPC 标准、高速数字设计、信号完整性/PDN、EMC/EMI、先进材料、DFM 指南、热管理、混合信号/RF、BGA/先进封装、中国行业实践。每文件含公式/数据表/经验法则/常见陷阱/交叉引用。采用 chromadb + 本地 embedding，实现增量索引（manifest 基于 mtime）、过时条目自动清理、全链路集成（ToolRegistry→Controller→Eel→REST 端点）。')

    h2(doc, '1.5 多智能体审查与推理部署')
    para(doc, '5 Agent 并发评审，从不同角色维度交叉复核，输出共识汇总与雷达图。模型推理封装 < 2ms，三模型串联合计 < 1M 参数，可实现无云依赖的离线部署方案。')

    h1(doc, '二、研究成果与量化指标')
    table(doc,
        ['成果', '量化指标'],
        [
            ['意图分类器', '10 类 / 99.09% 准确率 / 960KB'],
            ['元件分类器', '12 细类 / 99.24% 准确率 / 2.3MB'],
            ['变更风险预测器', '21 维特征 / 风险排序正确'],
            ['置信度校准', 'ECE 0.0098 / 0.0056，模型已部署'],
            ['RAG 知识库', '8 大类 / 11 文件 / 2041 行'],
            ['创新叙事', '"From Detection to Prediction"'],
        ], widths=[2.6,4.0])

    h1(doc, '三、创新点与项目贡献')
    bullet(doc, '自研轻量 ML 模型，离线可部署，摆脱云端依赖', bold_prefix='① ')
    bullet(doc, '温度缩放置信度校准，提升预检/拒识可靠性', bold_prefix='② ')
    bullet(doc, 'FP-Growth 违规知识挖掘，从"检测"走向"预测"', bold_prefix='③ ')

    h1(doc, '四、工作量说明')
    para(doc, '成员 B 聚焦 AI 算法与知识库，任务具有强研究性：三自研模型需自行构建训练数据，完成训练脚本、超参搜索、消融实验与多轮调优；置信度校准需对比多种方案并验证部署；RAG 知识库需查阅大量 IPC 与行业标准并逐条整理成可用知识。考虑模型选型调研、跨学科知识学习与反复实验成本，等效投入约 12.0 人月，占项目总工作量（约 36.5 人月）的 33%。', bold=True)
    doc.save(os.path.join(OUT, '大创任务分工报告_成员B_AI算法与知识库.docx'))

# ============ 报告C ============
def report_c():
    doc = Document()
    cover(doc, '智绘PCB——AI 智能 PCB 设计助手', '大学生创新创业训练计划项目', '成员 C', '前端交互与实验验证 · 前端 / 可视化 / 测试')

    para(doc, '本报告为「智绘PCB——AI智能PCB设计助手」三人分工报告中成员 C 的分册，聚焦优秀产品级前端交互、可视化与负责项目成败的实验验证体系。成员 C 让系统的 AI 能力"看得见、可验证、可量化"，是成果展示与论文数据的直接责任人。')
    para(doc, '协作关系：C 消费 A 的 DRC/agent/REST 接口做可视化与交互，使用 B 的变更风险预测器做闭环预检。C 的四阶段实验框架产出论文所需全部数据（Δ 表、收敛率、多智能体评分、缺陷检出率），直接支撑申报书承诺指标的达成。')

    h1(doc, '一、主要研究内容')

    h2(doc, '1.1 Web UI 前端（Eel 三栏布局）')
    para(doc, '实现 Cherry Studio 风格三栏布局（助手/话题/内容区），支持多实例助手模型、Agent 模式开关、窗口模式开关、双向消息、SVG 功能图标、暗色主题、圆角无刚硬分割线。功能包含自然语言对话、Agent 多步推理、快捷键/托盘伴生模式、知识查询路由、快捷操作面板。')

    h2(doc, '1.2 AI Verification Map（可视化核心，550 行）')
    para(doc, '定位为"展示 AI 验证结果"而非"展示 BOM"：DRC 违规密度热力图（绿→橙→红）、AI 变更环（安全🟢/修正🟠/危险🔴/分析🔵 四色标记）、多智能体审查发现叠加、缩放/平移/点击详情面板（违规/AI变更/审查三标签）、按严重度/覆盖层/图层筛选。')
    para(doc, '创新点：立创 EDA 回答"板子长什么样"，本系统回答"问题在哪里、AI 发现了什么、AI 建议是否安全"——所有 EDA 工具尚无此能力。用于真实板（STM32F103，33 违规，35 元件热力图，5 AI 变更，MA 审查 69.7/100，4 缺陷注入）。')

    h2(doc, '1.3 四阶段实验框架（paper_experiments.py，约 1200 行）')
    para(doc, '构建自动化实验框架，覆盖 Phase A（DRC 基线）→ Phase B（闭环验证）→ Phase C（多智能体）→ Phase D（缺陷注入）。核心是闭环回放：LLM 文本建议 → 结构化 BOM 变更解析 → 应用到 BOM 副本 → DRC delta 对比 → 反馈 LLM 修正 → 循环（最多 3 轮）。')
    code_block(doc, r'''
for round_num in range(1, MAX_ROUNDS + 1):
    modified_bom = apply_bom_changes(original_bom, current_changes)
    modified_violations = DesignRuleChecker().check_all(modified_bom, ...)
    new_violations = [v for v in modified_violations if v.rule_name not in baseline_rules]
    score_drop = baseline_score - modified_score
    if not new_violations and score_drop <= SCORE_DROP_TOLERANCE:
        converged = True   # 无新规则类型 且 评分未显著下降（评分守门）
        break
''')

    h2(doc, '1.4 数据集构建与清洗')
    para(doc, '采集并清洗 7 块真实 PCB 设计（含 esp32 音频板、stm32 最小系统、无刷电调、DC-DC 电源、智能UV灯、EDA-RobotPro、多功能板），对齐 BOM + 坐标 + 网表 + 飞针测试四份数据，并注入 5 种缺陷类型构造基准集。')

    h2(doc, '1.5 测试体系与质量保障')
    para(doc, '维护 719 条测试（含 36 API、54 calculator、13 verifier、ML 模型测试、真实板回归、评分守门回归）。实现闭环 Δ 指标（baseline/final/proposed_score、risk_prevented、delta_score），保证"危险建议被拦截"数据语义正确、无误导性负 Δ。')

    h1(doc, '二、研究成果与量化指标')
    table(doc,
        ['成果', '量化指标'],
        [
            ['真实 PCB 数据集', '7 块真实设计（BOM+坐标+网表+飞针）'],
            ['四阶段实验', '35 次闭环验证 + 7 板多智能体'],
            ['缺陷检出率', '30/31 = 96.8%（Phase D）'],
            ['多智能体评分', '均分 93.5/A 级（esp32 95.2/A+）'],
            ['DRC 守门拦截', '避免质量损失 4.8 分'],
            ['可视化', 'AI Verification Map + 12 张论文图表'],
            ['测试', '719 条全部通过'],
        ], widths=[2.2,4.4])

    h1(doc, '三、创新点与项目贡献')
    bullet(doc, 'AI Verification Map：违规热力图 + AI 变更环 + 多智能体叠加，业界首创', bold_prefix='① ')
    bullet(doc, '四阶段闭环实验框架：Δ 指标、评分守门、结构化 BOM 回放', bold_prefix='② ')
    bullet(doc, '自动化实验体系支撑 7 真实板 + 719 测试的质量保障', bold_prefix='③ ')

    h1(doc, '四、工作量说明')
    para(doc, '成员 C 负责前端交互与实验验证，工作以产品打磨与数据产出为主：前端需多轮交互设计与可用性调试；四阶段实验框架需反复跑 7 真实板以确保数据可靠；AI Verification Map 为业界首创，需大量视觉与交互验证；719 条测试的维护与边界场景打磨费时较长。考虑视觉设计迭代、实验重跑与数据清洗成本，等效投入约 11.0 人月，占项目总工作量（约 36.5 人月）的 29%。', bold=True)
    doc.save(os.path.join(OUT, '大创任务分工报告_成员C_前端交互与实验验证.docx'))

if __name__ == '__main__':
    report_a(); report_b(); report_c()
    print('三份报告已生成到:', OUT)
    for f in os.listdir(OUT):
        if f.endswith('.docx'): print('  -', f)
