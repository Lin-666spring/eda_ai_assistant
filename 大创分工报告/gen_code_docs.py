# -*- coding: utf-8 -*-
"""⚠️ 本文件内嵌的代码片段是 2026 年早期的规则引擎副本，与现行实现（src/rules/）
已发生漂移，仅作大创汇报的 historical 展示用途 —— 不要以此为参考改代码（2026-10-10 声明）。
Original docstring: 生成三名成员各自的代码库示例文档。运行: python gen_code_docs.py"""
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

def para(doc, text, size=10.5, bold=False, align=None, name='宋体', space_after=6, color=None):
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(space_after); p.paragraph_format.line_spacing = 1.35
    if align: p.alignment = align
    r = p.add_run(text); set_run(r, name=name, size=size, bold=bold, color=color); return p

def title(doc, text, size=24, color=(0x0B,0x39,0x6E)):
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
    return t

def cover(doc, t, m, r):
    title(doc, t)
    subtitle(doc, '代码库示例 · 功能实现与代码说明')
    for x in (m, r, '大学生创新创业训练计划项目', '2026年9月'):
        q=doc.add_paragraph(); q.alignment=WD_ALIGN_PARAGRAPH.CENTER; q.paragraph_format.space_after=Pt(4)
        rr=q.add_run(x); set_run(rr,size=13,color=(0x33,0x33,0x33))
    doc.add_page_break()

def func(doc, name, desc, code, points):
    h2(doc, name)
    para(doc, desc)
    code_block(doc, code)
    for p in points:
        bullet(doc, p[1], bold_prefix=p[0] if len(p)>1 and p[0] else None)

# ============ 成员A ============
def doc_a():
    doc=Document()
    cover(doc,'核心引擎与规则系统', '成员 A（负责人）', '后端 / 设计规则 / Agent')
    para(doc,'本文档为成员 A 方向的代码库示例，聚焦项目的底层引擎：设计规则检查、元件语义分类、多维评分、迭代收敛状态机与智能体工具。以下每个功能均附真实实现代码与逐段说明。')

    h1(doc,'一、功能代码示例')
    func(doc,
        '① DRC 去耦电容检查（真实电路导向）',
        'DRC 是项目核心。去耦检查不再是"全 BOM 有一个 100nF 就满足/一个没有就全报错"的简单判断，而是基于元件语义分类 + 供需关系（可用电容总量 vs 需去耦 IC 数）。',
        r'''def _check_decoupling_caps(self, bom_items, positions, netlist):
    """去耦电容检查：每个 IC 应有匹配的去耦电容，基于 Z-F 分析。"""
    violations = []
    ics, caps = [], []
    for item in bom_items:
        cls = _classify_component(item)      # 语义分类，非关键词匹配
        if cls == "cap":
            caps.append(item)
        elif cls == "ic":
            ics.append(item)
    # ── 统计可用去耦电容总量（含数量）──
    ...  # 按"可用 100nF/10µF 总量 vs IC 数"供需判断''',
        [('设计定位：','真实立创 BOM 描述常只是值/型号（"100nF"），旧逻辑会把电容/二极管误判为 IC，产生大量虚假违规。'),
         ('分类依据：','位号前缀 + 描述关键词，而非仅描述关键词，保证元件识别准确。'),
         ('供需判断：','全缺→逐 IC ERROR；缺口→汇总 WARNING，粒度贴合实际使用。')])

    func(doc,
        '② 元件语义三级分类（ML 优先 + 安全网 + 规则回退）',
        '将 BOM 元件分为 ic/cap/passive/other 四粗类。优先用自研 ML 元件分类器，但"非 IC 前缀绝不接受 ic 分类"，防止 ML 看到描述里 "USB/IC" 字眼误判。',
        r'''def _classify_component(item) -> str:
    from src.ml.component_classifier import FINE_TO_COARSE
    fine_type, confidence = _classify_component_fine(item)   # ① ML 优先
    if fine_type:
        coarse = FINE_TO_COARSE.get(fine_type, "other")
        prefix = reference_prefix(item)                       # 取位号字母前缀
        _non_ic_prefixes = (
            "C","R","RN","RNC","L","FB","D","LED","Q","T",  # 元件
            "X","Y","XTAL","OSC",                            # 晶振
            "J","CN","CON","HDR","P","FPC","TP",             # 连接器
            "SW","K","S","BUTTON","BUZZ","BZ","F","FU",      # 开关/蜂鸣器/保险丝
            "RL","RELAY",                                    # 继电器
        )
        if coarse == "ic" and prefix in _non_ic_prefixes:     # ② 安全网
            return _classify_component_rule(item)             # ③ 规则回退
        return coarse
    return _classify_component_rule(item)''',
        [('三级策略：','ML 模型 → 前缀安全网 → 规则回退，兼顾准确率与可控性。'),
         ('安全网价值：','修复 D-ESD、X-连接器被误判为 IC 的问题，消除大量去耦虚报。'),
         ('修复效果：','四块板去耦违规 176→3，评分 71.5(B)→93.5(A)。')])

    func(doc,
        '③ 容值解析（含 EIA 三位码）',
        '真实 BOM 常以 3 位码表示容值（如 "104" = 100nF）。解析函数先走 ValueNormalizer，失败再回退到 EIA 三位码规则。',
        r'''def _parse_capacitance(val_str: str):
    """解析容值字符串（含 EIA 三位码），返回法拉。"""
    if not val_str: return None
    val_str = val_str.strip().upper().replace(" ", "")
    nv = ValueNormalizer.normalize(val_str)
    if nv.base_value: return nv.base_value
    if val_str.isdigit() and len(val_str) == 3:
        return int(val_str[0:2]) * 10 ** int(val_str[2]) * 1e-12  # "104"=100nF
    return None''',
        [('容错：','处理空格/大小写，提高真实数据解析率。'),
         ('EIA 码：','"104"→10×10^4 pF = 100nF，覆盖立创常见值表示。')])

    func(doc,
        '④ 六维设计评分系统（平方根衰减 + 等级映射）',
        '将违规按维度分组（电气/SI/PDN/EMC/热/DFM），每维度独立评分，最终映射为 A+/A/B+... 等级。采用平方根衰减避免惩罚线性无下限。',
        r'''# Step 1: 将违规按维度分组
for v in violations:
    for kw, (dim, weight) in RULE_DIMENSION_MAP.items():
        if kw in v.rule_name:
            v._weight = weight            # 附加权重到违规对象
            dim_violations[dim].append(v)
            break

def _assign_grade(score: float) -> str:
    if score >= 95: return "A+"
    elif score >= 88: return "A"
    elif score >= 80: return "B+"
    elif score >= 70: return "B"
    elif score >= 60: return "C"
    elif score >= 45: return "D"
    else: return "F"''',
        [('分组映射：','RULE_DIMENSION_MAP 把规则名→(维度,权重)，决定每个违规影响哪个维度。'),
         ('等级制：','评分→等级，多智能体/闭环实验都以等级作为最终口径。'),
         ('闭环用途：','评分差分是"Δ 指标"与"评分守门"的基础。')])

    func(doc,
        '⑤ 迭代收敛状态机（终止策略链）',
        '闭环引擎需判断 LLM 修正是否真正收敛。实现策略驱动状态机：依次评估阻断→停滞→振荡→发散→最大轮次，决定终止状态。',
        r'''class StagnationPolicy(TerminationPolicy):
    """LLM 修正与上一轮建议同指（无进展）→ STAGNATED。"""
    def evaluate(self, history):
        if len(history) < 2: return None
        cur, prev = history[-1], history[-2]
        if cur.fingerprint and cur.fingerprint == prev.fingerprint:
            return ConvergenceStatus.STAGNATED
        return None''',
        [('策略链：','BlockingIssues→Stagnation→Oscillation→Divergence→MaxRounds，优先级递减。'),
         ('指纹比较：','相邻两轮"问题指纹"相同即停滞，避免与振荡（周期2）语义打架。'),
         ('工程价值：','纯逻辑零 IO，与 verifier 分离，6 种终止状态，供论文导出。')])

    h1(doc,'二、文件清单')
    para(doc,'成员 A 负责仓位的核心文件（主要改动）：')
    table(doc,['文件','职责'],
        [['src/rules/checker.py','71 条 DRC 规则 + 元件语义分类'],
         ['src/core/design_scorer.py','六维评分系统、等级映射'],
         ['src/core/convergence.py','迭代收敛状态机（6 终止状态）'],
         ['src/agent/tools.py','24 工具注册（SSOT）'],
         ['src/core/controller.py','UI 无关的调度大脑'],
         ['src/constants.py','魔法数字/常量（规则、IPC 参数）']], widths=[2.6,4.0])
    doc.save(os.path.join(OUT,'代码库示例_成员A_核心引擎与规则系统.docx'))

# ============ 成员B ============
def doc_b():
    doc=Document()
    cover(doc,'AI 算法与知识库', '成员 B', '机器学习 / 大模型 / 知识库')
    para(doc,'本文档为成员 B 方向的代码库示例，聚焦自研轻量模型、置信度校准、变更风险预测与元件识别。全部模型离线、CPU 推理 <2ms，摆脱云端 API 依赖。')

    h1(doc,'一、功能代码示例')
    func(doc,
        '① 字符级 TextCNN 意图分类器（多尺度卷积）',
        '将用户自然语言指令分类到 10 类意图。输入文本→字符 Embedding→多尺度 Conv1D→GlobalMaxPool→拼接→分类头，用不同卷积核提取局部 n-gram 特征。',
        r'''def forward(self, input_ids):
    # Embedding + 调整维度给 Conv1d
    x = self.embedding(input_ids).transpose(1, 2)
    conv_outputs = []
    for conv in self.convs:              # 多尺度卷积
        y = conv(x); y = F.relu(y)
        y = F.max_pool1d(y, y.size(2))   # GlobalMaxPool
        conv_outputs.append(y.squeeze(2))
    x = torch.cat(conv_outputs, dim=1)   # 拼接多尺度特征
    x = self.dropout(x)
    x = F.relu(self.fc1(x))
    x = self.fc2(x)                      # (batch, num_classes)
    return x''',
        [('多尺度：','不同 kernel 尺寸并行，抓取不同长度的字符 n-gram。'),
         ('全局池化：','GlobalMaxPool 将每通道压成标量，表征该通道最显著的局部特征。'),
         ('轻量：','≈244K 参数、960KB、CPU <1ms，可离线部署。')])

    func(doc,
        '② 元件类型分类器（12 细类 → 4 粗类 + 超参设计）',
        '元件细分为 12 类（ic_mcu/ic_power/cap_mlcc/resistor/connector 等），再映射到粗类。超参比意图分类器高约 2.5×，以适应更细的分类粒度。',
        r'''FINE_TO_COARSE = {
    "ic_mcu": "ic", "ic_power": "ic", "ic_analog": "ic", "ic_other": "ic",
    "cap_mlcc": "cap", "cap_elec": "cap",
    "resistor": "passive", "inductor": "passive",
    "diode_led": "passive", "transistor": "passive",
    "crystal": "other", "connector": "other",
}
DEFAULT_COMPONENT_CONFIG = {
    "embed_dim": 128,          # ↑ 96→128
    "kernel_sizes": [2,3,4,5,6],  # ↑ 4→5 尺度
    "num_filters": 128,        # ↑ 64→128
    "dropout": 0.35,           # ↑ 正则化
    "hidden_dim": 128, "max_len": 128,
    "num_classes": NUM_COMPONENT_CLASSES,
}''',
        [('分层：','细类用于精确识别，粗类供 DRC 规则引擎消费，两端解耦。'),
         ('超参调优：','随参数量增大同步提升正则化，防止过拟合。')])

    func(doc,
        '③ 置信度校准（Temperature Scaling + ECE）',
        '模型置信度往往过于自信。用温度缩放 T 对 logits 缩放，并计算 ECE/MCE 评估校准效果。校准模型已部署到主推理路径。',
        r'''def predict(self, input_ids):
    self.eval()
    with torch.no_grad():
        logits = self.forward(input_ids) / self.temperature  # 应用校准温度
        probs = F.softmax(logits, dim=1)
        best_idx = probs.argmax(dim=1)
        confidences = probs.max(dim=1).values.tolist()
    return intents, confidences''',
        [('温度缩放：','除以 T 后 softmax，T>1 压低过度自信，T<1 拉平。'),
         ('部署集成：','校准温度随模型权重一起保存，推理时自动应用。'),
         ('效果：','Intent ECE 0.0159→0.0098(T=0.896)、Component ECE 0.0090→0.0056(T=0.783)。')])

    func(doc,
        '④ BOM 变更风险预测器（21 维特征 + 启发式）',
        '闭环实验在应用 LLM 建议的 BOM 变更前，预测每条变更的风险，高风险建议提前标记拦截。特征含元件类型 one-hot、字段类型、参数幅度变化、设计健康度、违规邻近度。',
        r'''class ChangeFeatures:
    def to_vector(self) -> np.ndarray:
        ...  # 21 维特征向量

class ChangeFeatureExtractor:
    def extract(self, change, bom_items) -> ChangeFeatures:
        ...  # 元件类型 one-hot + 字段类型 + 参数变化幅度 + 健康度

class ChangeRiskPredictor:
    def predict(self, feats: ChangeFeatures) -> float:
        # 逻辑回归权重 + 启发式兜底
        score = np.dot(self._heuristic_weights(), feats.to_vector())
        return float(sigmoid(score))''',
        [('特征工程：','把"改电容 10 倍"与"微调电阻"编码成可区分向量。'),
         ('风险排序：','晶振改频(0.97) > 电容10倍(0.96) > IC封装(0.77) > 电阻微调(0.73)。'),
         ('预检闭环：','与闭环实验联动，preflight_flagged 提前拦截危险建议。')])

    h1(doc,'二、文件清单')
    para(doc,'成员 B 负责的算法模块：')
    table(doc,['文件','功能'],
        [['src/ml/intent_classifier.py','意图分类 TextCNN（10 类）'],
         ['src/ml/component_classifier.py','元件分类 TextCNN（12 细类）'],
         ['src/ml/change_predictor.py','BOM 变更风险预测（21 维）'],
         ['src/ml/calibrate.py','Temperature Scaling 校准 + ECE'],
         ['src/ml/violation_mining.py','FP-Growth 违规知识挖掘'],
         ['src/rag/*','RAG 知识库（8 大类 / 2041 行）']], widths=[2.8,3.8])
    doc.save(os.path.join(OUT,'代码库示例_成员B_AI算法与知识库.docx'))

# ============ 成员C ============
def doc_c():
    doc=Document()
    cover(doc,'前端交互与实验验证', '成员 C', '前端 / 可视化 / 测试')
    para(doc,'本文档为成员 C 方向的代码库示例，聚焦产品级交互、AI 可视化与四阶段实验验证体系。核心是让 AI 能力"看得见、可验证、可量化"。')

    h1(doc,'一、功能代码示例')
    func(doc,
        '① 结构化 BOM 变更解析（三级回退）',
        'LLM 建议需转成结构化 JSON BOM 变更才能被校验和应用。解析器按"整段 JSON → ```json 代码块 → 首个 { } 块"三级回退，提高容错。',
        r'''def parse_llm_bom_changes(llm_response: str) -> ParseResult:
    text = llm_response.strip()
    parsed = None
    # 策略 1：直接 json.loads 整个响应
    try: parsed = json.loads(text)
    except json.JSONDecodeError: pass
    # 策略 2：提取 ```json ... ``` 代码块
    if parsed is None:
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if fence_match:
            try: parsed = json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError: pass
    # 策略 3：提取第一个 { ... } 块
    ...''',
        [('容错：','LLM 回复格式不稳定，三级回退最大限度提取有效变更。'),
         ('工程价值：','是闭环回放"LLM 建议→可执行变更"的关键桥梁。')])

    func(doc,
        '② 结构化 BOM 应用（不可变副本）',
        '把变更应用到 BOM 副本，不污染原始数据。用 dataclasses.replace() 创建新对象，并用位号→索引映射处理"多位号同行"的真实 BOM。',
        r'''def apply_bom_changes(bom_items, changes):
    from dataclasses import replace
    result = [replace(item) for item in bom_items]            # 不可变副本
    ref_to_indices = {}
    for idx, item in enumerate(result):
        for ref in item.reference_list:                        # 支持 "R1,R2,R3"
            ref_to_indices.setdefault(ref.upper(), []).append(idx)
    for change in changes:
        if change.action == "remove":
            ...  # 按位号删/改，dataclasses.replace() 安全应用
    return result''',
        [('不可变：','replace() 生成新对象，保证原始 BOM 与基线可回溯对比。'),
         ('多位号：','reference_list 覆盖逗号分隔位号，贴合真实数据。')])

    func(doc,
        '③ 闭环回放主循环（LLM→DRC→反馈→修正）',
        '核心创新点。每轮应用变更→DRC→计算新违规与评分下降→满足收敛条件则停止，否则反馈 LLM 修正（最多 3 轮）。',
        r'''for round_num in range(1, MAX_ROUNDS + 1):
    modified_bom = apply_bom_changes(original_bom, current_changes)
    modified_violations = DesignRuleChecker().check_all(modified_bom, ...)
    new_violations = [v for v in modified_violations if v.rule_name not in baseline_rules]
    score_drop = baseline_score - modified_score
    if not new_violations and score_drop <= SCORE_DROP_TOLERANCE:
        converged = True    # 无新规则 且 评分未显著下降（评分守门）
        break''',
        [('评分守门：','SCORE_DROP_TOLERANCE=2.0，评分下降超阈值即拦截危险建议。'),
         ('Δ 指标：','baseline/final/proposed_score + risk_prevented，保障"拦截坏建议"语义正确。')])

    func(doc,
        '④ AI Verification Map 可视化生成',
        '业界首创的"展示 AI 验证结果"可视化：DRC 违规密度热力图 + AI 变更四色环（安全🟢/修正🟠/危险🔴/分析🔵）+ 多智能体叠加，可点击查看详情。',
        r'''class VerificationMapGenerator:
    def generate(self, bom_items, violations, ai_changes, ma_results):
        html = self._render_template(...)      # 交互式 HTML 模板
        overlay = self._prepare_overlay_data(...) # 热力图 + 变更环 + 叠加层
        return html

def _classify_safety(vr: dict) -> str:
    """按风险打四色标记：safe/correct/dangerous/analysis"""
    ...''',
        [('定位：','回答"问题在哪里、AI 发现了什么、建议是否安全"，区别于立创 3D 的"板子长什么样"。'),
         ('交互：','缩放/平移/点击详情面板（违规/AI变更/审查三标签）、按严重度/覆盖层筛选。')])

    # 闭环实验成果表
    h1(doc,'二、实验验证成果（数据支撑）')
    table(doc,['阶段','成果'],
        [['Phase A 基线','7 真实板 DRC 基线（board_schematic 47 违规等）'],
         ['Phase B 闭环','35 次闭环验证，守门拦截 4.8 分质量损失'],
         ['Phase C 多智能体','均分 93.5/A 级（esp32 95.2/A+）'],
         ['Phase D 缺陷注入','检出率 30/31 = 96.8%'],
         ['图表','12 张论文级图表生成']], widths=[2.0,4.6])
    h1(doc,'三、文件清单')
    para(doc,'成员 C 负责的代码与数据：')
    table(doc,['文件','职责'],
        [['src/html_bom/verification_map.py','AI Verification Map 生成器'],
         ['tests/paper_experiments.py','四阶段实验框架（约 1200 行）'],
         ['tests/bom_suggestion.py','结构化 BOM 解析/应用'],
         ['tests/paper_charts.py','论文图表（8 类）'],
         ['tests/real_pcb_experiment.py','真实板实验入口'],
         ['test_data/pcb_designs/','7 块真实 PCB 数据集']], widths=[2.9,3.7])
    doc.save(os.path.join(OUT,'代码库示例_成员C_前端交互与实验验证.docx'))

if __name__=='__main__':
    doc_a(); doc_b(); doc_c()
    print('三份代码库示例文档已生成到:', OUT)
    for f in os.listdir(OUT):
        if f.endswith('.docx') and '代码库' in f: print('  -', f)
