/* 大创中期检查组会 PPT 生成脚本 —— 智绘PCB（TraceWise）
 * 结构：封面 / 提纲 / 01执行情况×2 / 02成果×5 / 03问题 / 04计划 / 05经费 / 结论
 * 设计：学术结构化口径（白底、藏青主色、行动句标题、一页一论点）
 */
const pptxgen = require("pptxgenjs");

const C = {
  bg: "FFFFFF",
  primary: "1F4E79",
  accent: "2E75B6",
  body: "2D2D2D",
  muted: "777777",
  tint: "EBF3FA",
  tint2: "F2F7FC",
  rule: "CCCCCC",
  highlight: "FFF2CC",
  amber: "7A5200",
  grayBar: "BFBFBF",
  onDark: "A9C6E8",
  onDark2: "CADCFC",
};
const F = "Microsoft YaHei";
const W = 13.33, H = 7.5, M = 0.5;
const CW = W - 2 * M; // 12.33

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "智绘PCB项目组";
pres.title = "智绘PCB——AI智能PCB设计助手 中期检查汇报";

let pageNum = 0;
function newSlide(dark) {
  const s = pres.addSlide();
  s.background = { color: dark ? C.primary : C.bg };
  return s;
}
function crumb(s, text) {
  s.addText(text, { x: M, y: 0.22, w: 8, h: 0.3, fontSize: 12, fontFace: F, color: C.accent, bold: true, charSpacing: 2, margin: 0 });
}
function title(s, text, opts = {}) {
  s.addText(text, { x: M, y: 0.5, w: CW, h: 0.75, fontSize: opts.size || 24, fontFace: F, color: C.primary, bold: true, valign: "top", margin: 0 });
}
function footer(s, source) {
  pageNum += 1;
  if (source) s.addText(source, { x: M, y: 7.08, w: 10.5, h: 0.3, fontSize: 10.5, fontFace: F, color: C.muted, margin: 0 });
  s.addText(String(pageNum), { x: 12.5, y: 7.08, w: 0.5, h: 0.3, fontSize: 10.5, fontFace: F, color: C.muted, align: "right", margin: 0 });
}
const bu = () => ({ code: "25B8", indent: 12, color: C.accent });

/* ============ S1 封面 ============ */
{
  const s = newSlide(true);
  s.addText("大学生创新创业训练计划项目 · 中期检查汇报", { x: 0.9, y: 1.35, w: 11.5, h: 0.4, fontSize: 16, fontFace: F, color: C.onDark, charSpacing: 2, margin: 0 });
  s.addText("智绘PCB——AI智能PCB设计助手", { x: 0.9, y: 1.9, w: 11.5, h: 0.95, fontSize: 40, fontFace: F, color: "FFFFFF", bold: true, margin: 0 });
  s.addText("面向 PCB 设计的闭环验证式智能设计助手", { x: 0.9, y: 2.95, w: 11.5, h: 0.5, fontSize: 18, fontFace: F, color: C.onDark2, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.9, y: 4.35, w: 2.0, h: 0.045, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText([
    { text: "汇报人：李泓达（项目负责人）　　团队成员：林昊晞 · 刘澈", options: { breakLine: true } },
    { text: "指导教师：丁文晴", options: {} },
  ], { x: 0.9, y: 4.6, w: 11.5, h: 0.85, fontSize: 15, fontFace: F, color: C.onDark2, paraSpaceAfter: 6, margin: 0 });
  s.addText("吉林大学 · 仪器科学与电气工程学院 · 测控技术与仪器专业", { x: 0.9, y: 5.5, w: 11.5, h: 0.4, fontSize: 14, fontFace: F, color: C.onDark, margin: 0 });
  s.addText("2026 年 10 月", { x: 0.9, y: 6.55, w: 5, h: 0.35, fontSize: 14, fontFace: F, color: C.onDark, margin: 0 });
  s.addNotes("开场：一句话定位——我们在做一个让 AI 给出的每一条 PCB 设计建议都经过规则验证的系统。本次中期检查按学校要求的五个方面汇报。");
}

/* ============ S2 汇报提纲 ============ */
{
  const s = newSlide(false);
  title(s, "汇报提纲");
  const items = [
    ["01", "项目执行情况", "是否按立项计划进行"],
    ["02", "阶段性成果", "系统建成 · 闭环实验 · 数据工程 · 本地智能 · 产出物"],
    ["03", "主要问题及解决方式", "五个问题的定位、解法与验证效果"],
    ["04", "下阶段工作计划", "两条主线与核心问题工作方案"],
    ["05", "经费使用情况", "支出科目与执行特点"],
  ];
  let y = 1.5;
  for (const [no, t, sub] of items) {
    s.addText(no, { x: M, y, w: 0.85, h: 0.75, fontSize: 26, fontFace: F, color: C.accent, bold: true, margin: 0 });
    s.addText([
      { text: t, options: { fontSize: 18, bold: true, color: C.body, breakLine: true } },
      { text: sub, options: { fontSize: 12.5, color: C.muted } },
    ], { x: 1.5, y, w: 6.1, h: 0.8, fontFace: F, valign: "top", margin: 0 });
    y += 1.02;
  }
  // 右侧项目速览
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.15, y: 1.5, w: 4.68, h: 4.9, fill: { color: C.tint }, line: { color: C.tint }, rectRadius: 0.08 });
  s.addText("项目速览（截至 2026-10）", { x: 8.45, y: 1.75, w: 4.1, h: 0.35, fontSize: 15, fontFace: F, color: C.primary, bold: true, margin: 0 });
  const facts = [
    ["技术核心", "LLM 闭环验证引擎（建议 → 规则复检 → 修正收敛）"],
    ["系统版本", "v0.8.0（运行时品牌 TraceWise）"],
    ["真实设计数据集", "155 个（立创开源平台）"],
    ["自动化测试", "1289 项全部通过"],
    ["设计规则 / 工具", "71 条 DRC 规则 / 24 项工具"],
    ["开源", "GitHub · MIT 协议 · 101 次提交"],
  ];
  const fa = facts.map(([k, v], i) => [
    { text: k, options: { fontSize: 12.5, bold: true, color: C.accent, breakLine: true } },
    { text: v, options: { fontSize: 13, color: C.body, breakLine: i < facts.length - 1 } },
  ]).flat();
  s.addText(fa, { x: 8.45, y: 2.2, w: 4.1, h: 4.0, fontFace: F, paraSpaceAfter: 8, valign: "top", margin: 0 });
  footer(s);
}

/* ============ S3 立项目标 ============ */
{
  const s = newSlide(false);
  crumb(s, "01 · 项目执行情况");
  title(s, "立项目标：以规则引擎闭环验证，破解大模型在 PCB 设计中的幻觉难题", { size: 23 });
  s.addText("为什么做这个项目", { x: M, y: 1.55, w: 5.9, h: 0.35, fontSize: 16, fontFace: F, color: C.accent, bold: true, margin: 0 });
  s.addText([
    { text: "通用大模型直接给硬件设计建议会产生「幻觉」——看似合理实则危险，例如把全部 100nF 电容改值时误删 MCU 复位电路电容", options: { bullet: bu(), breakLine: true } },
    { text: "人工逐项核对设计规则低效易漏，中小团队与高校学生缺乏专业检查手段", options: { bullet: bu(), breakLine: true } },
    { text: "现有 EDA 的 AI 插件多为单一大模型问答：无规则验证、无闭环修正，结果不可信", options: { bullet: bu() } },
  ], { x: M, y: 1.95, w: 5.9, h: 3.6, fontSize: 15.5, fontFace: F, color: C.body, paraSpaceAfter: 14, valign: "top", margin: 0 });

  s.addText("技术答案：闭环验证引擎", { x: 6.85, y: 1.55, w: 6, h: 0.35, fontSize: 16, fontFace: F, color: C.accent, bold: true, margin: 0 });
  const steps = [
    "① LLM 生成 BOM 变更建议",
    "② DRC 规则引擎对设计副本复检",
    "③ 新增违规 → 结构化修正反馈（违规清单 + 修法指引 + 撤销语义）",
    "④ 迭代直至收敛（六状态收敛状态机，危险建议整体撤销）",
  ];
  let sy = 1.98;
  for (let i = 0; i < steps.length; i++) {
    const last = i === steps.length - 1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 6.85, y: sy, w: 6.0, h: 0.72, rectRadius: 0.06,
      fill: { color: last ? C.primary : C.tint }, line: { color: last ? C.primary : "C9DCEF" },
    });
    s.addText(steps[i], { x: 7.05, y: sy, w: 5.7, h: 0.72, fontSize: 13.5, fontFace: F, color: last ? "FFFFFF" : C.body, valign: "middle", margin: 0 });
    if (!last) s.addText("↓", { x: 9.6, y: sy + 0.68, w: 0.5, h: 0.3, fontSize: 14, fontFace: F, color: C.accent, align: "center", margin: 0 });
    sy += 0.98;
  }
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 6.15, w: CW, h: 0.7, fill: { color: C.tint2 }, line: { color: "C9DCEF" }, rectRadius: 0.06 });
  s.addText([
    { text: "立项产出目标：", options: { bold: true, color: C.primary } },
    { text: "EI 论文投稿 ｜ 软件著作权申请 ｜ 真实数据集 20+ 块 ｜ 软件打包发布", options: { color: C.body } },
  ], { x: 0.8, y: 6.15, w: 11.7, h: 0.7, fontSize: 14.5, fontFace: F, valign: "middle", margin: 0 });
  footer(s, "立项目标来源：《智绘PCB——AI智能PCB设计助手项目计划书》（2026-08）");
  s.addNotes("先立靶子：项目要解决的不是“AI 能不能写代码”，而是“AI 的硬件建议可不可信”。闭环验证引擎是全项目的技术主轴，后面所有成果都围绕它展开。");
}

/* ============ S4 执行情况总览 ============ */
{
  const s = newSlide(false);
  crumb(s, "01 · 项目执行情况");
  title(s, "总体按立项计划推进：五项节点中四项达成，一项滞后已补齐", { size: 23 });
  const hdr = { fill: { color: C.primary }, color: "FFFFFF", bold: true, fontSize: 13, valign: "middle" };
  const rows = [
    [{ text: "立项计划事项", options: hdr }, { text: "计划节点", options: hdr }, { text: "当前进展（2026-10）", options: hdr }, { text: "判定", options: { ...hdr, align: "center" } }],
    ["闭环验证引擎与规则体系", "2026-08", "71 条规则引擎建成，并通过全量真实实验（79 设计 × 395 条建议）", "✔ 达成"],
    ["真实数据集扩充至 20+ 块", "2026 下半年", "155 个真实设计（79 thing_designs + 76 个 .epro2 工程），约为目标 7.8 倍", "✔ 超前"],
    ["EI / 期刊论文投稿", "2026-09", "18 页中文期刊口径初稿完成（10-19），待导师审阅后投稿", "◐ 滞后已补齐"],
    ["软件著作权申请", "2026-08", "材料完备：用户手册 19 页、源程序文档 685 页，具备提交条件", "✔ 达成"],
    ["软件打包发布", "2027 上半年", "Windows 安装包 v0.8.0 已产出，安装 / 卸载全流程验证完毕", "✔ 提前"],
  ].map((r, i) => i === 0 ? r : r.map((c, j) => ({
    text: c,
    options: {
      fontSize: 12.5, color: j === 3 ? (r[3].startsWith("◐") ? C.amber : C.primary) : C.body,
      bold: j === 3, align: j === 3 ? "center" : "left", valign: "middle",
      fill: { color: i % 2 === 1 ? "FFFFFF" : "F5F8FC" },
    },
  })));
  s.addTable(rows, {
    x: M, y: 1.45, w: CW, colW: [3.15, 1.55, 6.03, 1.6],
    border: { pt: 0.75, color: "D9E2EC" }, rowH: [0.5, 0.78, 0.78, 0.78, 0.78, 0.78], fontFace: F, margin: 0.08,
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 6.25, w: CW, h: 0.62, fill: { color: C.highlight }, line: { color: "E6C800", pt: 0.75 }, rectRadius: 0.06 });
  s.addText([
    { text: "总体判断：", options: { bold: true, color: C.amber } },
    { text: "技术路线未偏离立项计划，结项所需核心节点均已就绪；唯一滞后的论文节点已于 10 月补齐初稿。", options: { color: C.body } },
  ], { x: 0.8, y: 6.25, w: 11.7, h: 0.62, fontSize: 14, fontFace: F, valign: "middle", margin: 0 });
  footer(s);
  s.addNotes("主动说明论文滞后约一个月的原因：9 月先把实验数据做实（覆盖率与指标口径），10 月集中产出初稿——先数据后写作，避免返工。");
}

/* ============ S5 成果一 系统全景 ============ */
{
  const s = newSlide(false);
  crumb(s, "02 · 阶段性成果");
  title(s, "成果一：建成完整可用的闭环验证式智能设计助手系统（v0.8）");
  const layers = [
    ["交互层", "Eel Web 界面 · 对话优先工作区 · 系统托盘 / 伴生模式"],
    ["智能层", "本地 BERT 意图识别 · 10 家 LLM 智能路由 · Function Calling Agent"],
    ["业务层", "BOM 管理 · 71 条 DRC 规则 · 5 类审查 Agent · 电路计算引擎 · RAG 知识库"],
    ["验证层", "闭环验证引擎 · 六状态迭代收敛状态机 · DRC 守门"],
    ["数据层", "SQLite 会话库 · ChromaDB 本地知识库 · 155 个真实设计数据集"],
  ];
  let ly = 1.5;
  for (const [name, items] of layers) {
    s.addShape(pres.shapes.RECTANGLE, { x: M, y: ly, w: 1.25, h: 0.82, fill: { color: C.primary }, line: { color: C.primary } });
    s.addText(name, { x: M, y: ly, w: 1.25, h: 0.82, fontSize: 14.5, fontFace: F, color: "FFFFFF", bold: true, align: "center", valign: "middle", margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: 1.75, y: ly, w: 5.35, h: 0.82, fill: { color: C.tint2 }, line: { color: "C9DCEF" } });
    s.addText(items, { x: 1.9, y: ly, w: 5.1, h: 0.82, fontSize: 12.5, fontFace: F, color: C.body, valign: "middle", margin: 0 });
    ly += 0.94;
  }
  // 右侧真实截图
  s.addImage({ path: "../软著材料/_build/shots/05_review.png", x: 7.45, y: 1.5, w: 5.38, h: 3.6 });
  s.addText("多智能体审查真实界面：六维雷达图 + 综合评分 A / 94.6", { x: 7.45, y: 5.18, w: 5.38, h: 0.32, fontSize: 12, fontFace: F, color: C.muted, align: "center", margin: 0 });
  s.addText([
    { text: "规模：", options: { bold: true, color: C.primary } },
    { text: "24 项工具 · 12 套电路模板 · 10 家 AI 厂商 · 11 类中文 PCB 知识库", options: { color: C.body } },
  ], { x: 7.45, y: 5.62, w: 5.38, h: 0.75, fontSize: 13, fontFace: F, valign: "top", margin: 0 });
  footer(s, "截图：智绘PCB v0.8 运行界面（软件著作权《用户操作手册》配图）");
  s.addNotes("强调“可用”：不是演示原型，是有 1289 项测试、可打包安装、按工作区管理会话的完整软件。右图为软著手册同款真实截图。");
}

/* ============ S6 成果二 闭环实验（核心） ============ */
{
  const s = newSlide(false);
  crumb(s, "02 · 阶段性成果");
  title(s, "成果二：闭环验证全量实验五项指标全部超越立项目标");
  const kpis = [
    ["94.2%", "BOM 变更收敛率", "立项目标 > 70%"],
    ["1.14 轮", "平均修正轮次", "立项目标 ≤ 2.0"],
    ["100%", "危险建议消除率", "目标 > 80%（blocking 级）"],
    ["95.7%", "缺陷注入检出率", "280 次注入检出 268"],
    ["94.2", "多智能体审查均分", "立项目标 > 75"],
  ];
  const cw = 2.37, gap = 0.12;
  kpis.forEach(([num, label, target], i) => {
    const x = M + i * (cw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.55, w: cw, h: 2.25, fill: { color: C.tint }, line: { color: "C9DCEF" }, rectRadius: 0.08 });
    s.addText(num, { x, y: 1.75, w: cw, h: 0.75, fontSize: 33, fontFace: F, color: C.primary, bold: true, align: "center", margin: 0 });
    s.addText(label, { x: x + 0.1, y: 2.6, w: cw - 0.2, h: 0.55, fontSize: 13.5, fontFace: F, color: C.body, bold: true, align: "center", valign: "top", margin: 0 });
    s.addText(target, { x: x + 0.1, y: 3.28, w: cw - 0.2, h: 0.45, fontSize: 11, fontFace: F, color: C.muted, align: "center", valign: "top", margin: 0 });
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 4.1, w: CW, h: 0.62, fill: { color: C.highlight }, line: { color: "E6C800", pt: 0.75 }, rectRadius: 0.06 });
  s.addText([
    { text: "实验规模：", options: { bold: true, color: C.amber } },
    { text: "79 个立创开源真实设计 × 5 类建议 = 395 条建议全量验证；对照立项时小样本实验（收敛 65% / 消除 76.5%），全量真实数据下全面提升。", options: { color: C.body } },
  ], { x: 0.8, y: 4.1, w: 11.7, h: 0.62, fontSize: 13.5, fontFace: F, valign: "middle", margin: 0 });
  s.addText([
    { text: "39 条危险建议被 LLM 识别后整体撤销——「AI 只会让设计变好，不会变差」由守门机制从机制上保证", options: { bullet: bu(), breakLine: true } },
    { text: "全部 395 条建议零错误执行；闭环收敛由指纹重复、周期振荡、连续发散等六种终止状态判定", options: { bullet: bu() } },
  ], { x: M, y: 4.95, w: CW, h: 1.6, fontSize: 14.5, fontFace: F, color: C.body, paraSpaceAfter: 10, valign: "top", margin: 0 });
  footer(s, "数据来源：experiment_results/run_thing_full_glm53（GLM-5.3，973 次调用 / 210.6 万 tokens），指标口径与论文初稿一致");
  s.addNotes("这是全项目最核心的一页。每个数字都能在实验目录下复现；答辩追问时口径：收敛率按 BOM 变更类建议计，100% 指 blocking 级新增违规消除。");
}

/* ============ S7 成果三 数据工程 ============ */
{
  const s = newSlide(false);
  crumb(s, "02 · 阶段性成果");
  title(s, "成果三：自研 .epro2 解析器打通真实数据，规则覆盖率提升至 100%", { size: 23 });
  s.addChart(pres.charts.BAR, [
    { name: "期初（旧数据口径）", labels: ["可判定覆盖率（口径A）", "有输出覆盖率（口径B）"], values: [70.4, 54.9] },
    { name: "现在（.epro2 全量）", labels: ["可判定覆盖率（口径A）", "有输出覆盖率（口径B）"], values: [100, 85.9] },
  ], {
    x: M, y: 1.6, w: 5.9, h: 4.5, barDir: "col", barGapWidthPct: 60,
    chartColors: [C.grayBar, C.accent],
    chartArea: { fill: { color: "FFFFFF" } },
    catAxisLabelColor: C.body, catAxisLabelFontSize: 12, catAxisLabelFontFace: F,
    valAxisLabelColor: C.muted, valAxisLabelFontSize: 11, valAxisLabelFontFace: F,
    valAxisMaxVal: 110, valAxisMinVal: 0, valAxisMajorUnit: 25,
    valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.primary, dataLabelFontSize: 11.5, dataLabelFontFace: F,
    showLegend: true, legendPos: "b", legendFontSize: 12, legendFontFace: F, legendColor: C.body,
    showTitle: false,
  });
  s.addText([
    { text: "立创 .epro2 为未公开格式：自研解析器 78/78 工程解析成功，与官方导出交叉验证 100% 一致", options: { bullet: bu(), breakLine: true } },
    { text: "元件 947/947 · 网络 667/667 · BOM 位号 885=885，坐标中位误差 0.0003 mm", options: { bullet: bu(), breakLine: true } },
    { text: "以真实铜箔数据重标定走线阈值：全量误报 8394 → 4000（−52%），检出覆盖口径不变", options: { bullet: bu(), breakLine: true } },
    { text: "激活长期失效的锐角 / 直角规则：110231 个真实拐角中检出锐角 862 处、直角 2146 处", options: { bullet: bu() } },
  ], { x: 6.75, y: 1.75, w: 6.08, h: 4.3, fontSize: 14.5, fontFace: F, color: C.body, paraSpaceAfter: 13, valign: "top", margin: 0 });
  footer(s, "复现：python scripts/epro2_rule_coverage.py（零 LLM、零网络，45 秒）；数据集合计 155 个真实设计");
  s.addNotes("口径要讲清：A=规则真的执行了判断，B=实际报出违规。71 条规则全部可判定；两条口径都能一键复现，不是数字灌水。");
}

/* ============ S8 成果四 本地智能与工程质量 ============ */
{
  const s = newSlide(false);
  crumb(s, "02 · 阶段性成果");
  title(s, "成果四：意图识别升级为本地 BERT（95.2%），DRC 稳态 12.6 毫秒", { size: 23 });
  const cards = [
    ["本地智能 · 离线可用", "95.2%", "引擎意图识别准确率", [
      "自研 TextCNN 升级为 rbt3 BERT（ONNX fp16），裸模型 96.4%",
      "59 项路由语义探针全部通过",
      "本地 CPU 推理，摆脱云端 API 依赖",
    ]],
    ["性能优化", "12.6 ms", "稳态 DRC 全量检查（原 520 ms，41×）", [
      "根因剖析：耗时来自重复 ML 前向，而非算法复杂度",
      "双检锁预热 + BootStep 常驻缓存",
    ]],
    ["工程质量", "1289 项", "pytest 自动化测试全部通过", [
      "UI 冒烟 57 项全过（含深色 / 伴生模式）",
      "金样快照锁定 2048 项断言，指标口径防漂移",
      "规则抽查常态化（9-18 / 10-06 两轮报告）",
    ]],
  ];
  const cw2 = 4.01, gap2 = 0.15;
  cards.forEach(([head, num, sub, bullets], i) => {
    const x = M + i * (cw2 + gap2);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.55, w: cw2, h: 5.0, fill: { color: C.tint2 }, line: { color: "C9DCEF" }, rectRadius: 0.08 });
    s.addText(head, { x: x + 0.25, y: 1.8, w: cw2 - 0.5, h: 0.35, fontSize: 15.5, fontFace: F, color: C.accent, bold: true, margin: 0 });
    s.addText(num, { x: x + 0.25, y: 2.25, w: cw2 - 0.5, h: 0.75, fontSize: 34, fontFace: F, color: C.primary, bold: true, margin: 0 });
    s.addText(sub, { x: x + 0.25, y: 3.05, w: cw2 - 0.5, h: 0.6, fontSize: 12.5, fontFace: F, color: C.body, valign: "top", margin: 0 });
    s.addText(bullets.map((b, j) => ({ text: b, options: { bullet: bu(), breakLine: j < bullets.length - 1 } })),
      { x: x + 0.25, y: 3.75, w: cw2 - 0.5, h: 2.6, fontSize: 12.5, fontFace: F, color: C.body, paraSpaceAfter: 9, valign: "top", margin: 0 });
  });
  footer(s, "口径：测试规模为 2026-10-14 提交（3121bdd）时点；意图识别为 data/nlu_eval.json 评估集");
  s.addNotes("三个数字对应三类同学的工作：成员B的模型线、性能专项、以及全员的质量底线。BERT 升级同时保留了关键词与云端兜底，短命令由模板覆盖。");
}

/* ============ S9 成果五 产出物 ============ */
{
  const s = newSlide(false);
  crumb(s, "02 · 阶段性成果");
  title(s, "成果五：论文初稿、软著材料、安装包、开源仓库四类产出全部落地");
  const cards = [
    ["01 学术论文", "《面向 PCB 设计的 LLM 闭环验证引擎》初稿 18 页（2026-10-19）：中文期刊口径，6 图 5 表 4 公式 16 篇文献；指标全部取自全量实测，逐页排版校验通过"],
    ["02 软件著作权", "《智绘PCB—AI智能PCB设计助手软件 V1.0》：用户操作手册 19 页（嵌 5 图）、源程序文档 34138 行 / 685 页、36 条静态目录——申请材料完备，待提交"],
    ["03 软件交付", "Inno Setup 安装包 + onedir 发行版 v0.8.0；运行时品牌定名 TraceWise；安装、卸载、升级全流程在真机验证"],
    ["04 开源与过程资产", "GitHub 开源（MIT 协议）· 101 次提交全程留痕；实验数据、脚本与报告全部可复现，分工报告 / 代码示例文档齐备"],
  ];
  const cw3 = 6.06, ch = 2.32;
  cards.forEach(([head, body], i) => {
    const x = M + (i % 2) * (cw3 + 0.2);
    const y = 1.5 + Math.floor(i / 2) * (ch + 0.22);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw3, h: ch, fill: { color: i === 0 ? C.tint : C.tint2 }, line: { color: "C9DCEF" }, rectRadius: 0.08 });
    s.addText(head, { x: x + 0.28, y: y + 0.22, w: cw3 - 0.56, h: 0.38, fontSize: 16, fontFace: F, color: C.primary, bold: true, margin: 0 });
    s.addText(body, { x: x + 0.28, y: y + 0.68, w: cw3 - 0.56, h: ch - 0.9, fontSize: 12.5, fontFace: F, color: C.body, valign: "top", paraSpaceAfter: 6, margin: 0 });
  });
  footer(s, "论文与软著材料位于仓库 论文/ 与 软著材料/ 目录，可现场查验");
  s.addNotes("论文今天刚出初稿、尚未提交 git；软著按学校流程走完提交即可。若评委问论文进度：已进入导师审阅阶段。");
}

/* ============ S10 问题与解决 ============ */
{
  const s = newSlide(false);
  crumb(s, "03 · 主要问题及解决方式");
  title(s, "五个主要问题均已定位并解决，解法全部经真实数据验证", { size: 23 });
  const hdr = { fill: { color: C.primary }, color: "FFFFFF", bold: true, fontSize: 13, valign: "middle" };
  const rows = [
    [{ text: "遇到的问题", options: hdr }, { text: "解决方式", options: hdr }, { text: "验证效果", options: hdr }],
    ["LLM 幻觉：危险建议看似合理实则致命", "闭环验证：DRC 复检 + 结构化修正反馈 + 撤销语义 + 守门", "blocking 级新增违规消除率 100%，39 条危险建议被整体撤销"],
    ["立创 .epro2 格式无公开文档，真实数据进不来", "自研解析器，并与官方导出做交叉验证", "78/78 解析成功；元件 / 网络 / BOM 100% 一致"],
    ["规则误报多，个别规则「静默失效」（死代码、漏 import）", "真实铜箔数据重标定阈值；专项审计暴露隐藏缺陷", "误报 −52%；修复 5 处隐藏缺陷，锐角规则重新激活"],
    ["早期指标区分度不足（消除率恒为 100%）", "评审误报族判据修正，指标口径重新定义并冻结", "误报 1761 → 1691；金样快照锁定，结果可复现"],
    ["依赖云端 API，离线场景不可用", "自研轻量模型本地化，并升级为 BERT", "意图识别本地推理，准确率 95.2%，无需联网"],
  ].map((r, i) => i === 0 ? r : r.map((c, j) => ({
    text: c,
    options: { fontSize: 12.5, color: C.body, bold: j === 0, valign: "middle", fill: { color: i % 2 === 1 ? "FFFFFF" : "F5F8FC" } },
  })));
  s.addTable(rows, {
    x: M, y: 1.45, w: CW, colW: [3.9, 4.3, 4.13],
    border: { pt: 0.75, color: "D9E2EC" }, rowH: [0.42, 0.82, 0.82, 0.82, 0.82, 0.82], fontFace: F, margin: 0.08,
  });
  s.addText([
    { text: "遗留事项：", options: { bold: true, color: C.amber } },
    { text: "安装包未做代码签名（未签名 exe 会被杀软拦截）→ 已列入下阶段，申请代码签名证书解决。", options: { color: C.body } },
  ], { x: M, y: 6.4, w: CW, h: 0.45, fontSize: 13, fontFace: F, valign: "middle", margin: 0 });
  footer(s);
  s.addNotes("讲问题的原则：每个问题都给出“定位—解法—验证”三段式，避免只列问题不给方案。指标区分度一条最能体现科研严谨性，可展开讲。");
}

/* ============ S11 下阶段计划 ============ */
{
  const s = newSlide(false);
  crumb(s, "04 · 下阶段工作计划");
  title(s, "下阶段两条主线：论文投稿与软著提交，核心问题均有明确工作方案", { size: 23 });
  const phases = [
    ["10 月下旬", "论文定稿投稿", "导师审阅 → 期刊模板套排 → 投稿"],
    ["11 月", "软著提交", "申请表 + 材料报送，跟进审查进度"],
    ["12 月", "技术收尾", "需求电流等剩余规则 · 锐角分级校准 · KiCad 接入预研"],
    ["2027 上半年", "结题冲刺", "跨模型对比补充实验 · 结题材料 · 企业试用对接"],
  ];
  const pw = 2.85, gapT = 0.31;
  phases.forEach(([time, head, body], i) => {
    const x = M + i * (pw + gapT);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 1.5, w: pw, h: 1.75, rectRadius: 0.08,
      fill: { color: i < 2 ? C.primary : C.accent }, line: { color: i < 2 ? C.primary : C.accent },
    });
    s.addText([
      { text: time, options: { fontSize: 12.5, color: C.onDark2, breakLine: true } },
      { text: head, options: { fontSize: 16, bold: true, color: "FFFFFF", breakLine: true } },
      { text: body, options: { fontSize: 11, color: "E8F0FA" } },
    ], { x: x + 0.22, y: 1.66, w: pw - 0.44, h: 1.48, fontFace: F, valign: "top", paraSpaceAfter: 5, margin: 0 });
    if (i < phases.length - 1) {
      s.addText("→", { x: x + pw, y: 2.12, w: gapT, h: 0.5, fontSize: 18, fontFace: F, color: C.accent, bold: true, align: "center", valign: "middle", margin: 0 });
    }
  });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 3.6, w: CW, h: 2.9, fill: { color: C.tint }, line: { color: "C9DCEF" }, rectRadius: 0.08 });
  s.addText("核心问题工作方案", { x: 0.8, y: 3.82, w: 6, h: 0.38, fontSize: 16, fontFace: F, color: C.primary, bold: true, margin: 0 });
  s.addText([
    { text: "论文线：补齐作者 / 单位信息 → 按目标期刊模板套排 → 导师审定后投稿；同步确定备选期刊，规避单一期刊审稿周期风险", options: { bullet: bu(), breakLine: true } },
    { text: "结论普适性：跨模型全量对比（DeepSeek 已冒烟通过，GLM-5.3 全量已完成）按时间余量推进", options: { bullet: bu(), breakLine: true } },
    { text: "分发风险：申请代码签名证书，解决未签名 exe 被杀软拦截的分发问题", options: { bullet: bu(), breakLine: true } },
    { text: "结题对齐：按立项「发展规划」推进 KiCad 生态与企业试用对接，2027 上半年形成结题材料", options: { bullet: bu() } },
  ], { x: 0.8, y: 4.3, w: 11.6, h: 2.05, fontSize: 14, fontFace: F, color: C.body, paraSpaceAfter: 11, valign: "top", margin: 0 });
  footer(s);
  s.addNotes("两条主线都有明确责任人与时间点：论文由李泓达牵头、软著由林昊晞牵头、实验收尾由刘澈牵头。");
}

/* ============ S12 经费使用情况 ============ */
{
  const s = newSlide(false);
  crumb(s, "05 · 经费使用情况");
  title(s, "经费使用规范、执行进度正常，开支以资料与云服务为主", { size: 23 });
  const hdr = { fill: { color: C.primary }, color: "FFFFFF", bold: true, fontSize: 13, valign: "middle" };
  const rows = [
    [{ text: "支出科目", options: hdr }, { text: "已使用", options: { ...hdr, align: "center" } }, { text: "用途说明", options: hdr }],
    ["大模型 API / 云服务", "≈ ¥3", "闭环全量实验 210.6 万 tokens 实测约 ¥2.9；多模态截图分析走已有订阅"],
    ["图书资料与打印装订", "待对账", "立项 / 中期材料、论文与用户手册打印装订"],
    ["知识产权事务费", "¥0", "软件著作权登记费自 2017 年起国家免收，未发生代理费"],
    ["差旅与会议", "¥0", "本期以本地开发与线上调研为主，未发生差旅"],
    ["设备购置", "¥0", "纯软件研发：使用团队自有电脑与开源软件栈，无大额采购"],
  ].map((r, i) => i === 0 ? r : r.map((c, j) => ({
    text: c,
    options: { fontSize: 12.5, color: C.body, bold: j === 1, align: j === 1 ? "center" : "left", valign: "middle", fill: { color: i % 2 === 1 ? "FFFFFF" : "F5F8FC" } },
  })));
  s.addTable(rows, {
    x: M, y: 1.5, w: 7.45, colW: [2.05, 1.15, 4.25],
    border: { pt: 0.75, color: "D9E2EC" }, rowH: [0.45, 0.85, 0.85, 0.85, 0.85, 0.85], fontFace: F, margin: 0.08,
  });
  s.addText("执行特点", { x: 8.35, y: 1.5, w: 4.4, h: 0.35, fontSize: 16, fontFace: F, color: C.accent, bold: true, margin: 0 });
  s.addText([
    { text: "成本结构健康：无大额设备采购，最大单项为小额 API 充值", options: { bullet: bu(), breakLine: true } },
    { text: "控费机制：本地模型优先 + 多云路由 + 零 LLM 可复现脚本，把实验成本压至两位数以内", options: { bullet: bu(), breakLine: true } },
    { text: "合规：无超支、无科目调剂；决算将随结题材料一并报送", options: { bullet: bu() } },
  ], { x: 8.35, y: 1.95, w: 4.45, h: 3.4, fontSize: 13.5, fontFace: F, color: C.body, paraSpaceAfter: 12, valign: "top", margin: 0 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 6.3, w: CW, h: 0.55, fill: { color: C.highlight }, line: { color: "E6C800", pt: 0.75 }, rectRadius: 0.06 });
  s.addText("注：立项预算额度以项目申报书为准；表内金额为项目组台账口径，提交前将与财务报销凭证逐项核对更新。", { x: 0.8, y: 6.3, w: 11.7, h: 0.55, fontSize: 12.5, fontFace: F, color: C.amber, valign: "middle", margin: 0 });
  footer(s);
  s.addNotes("★提交前必做：把申报书预算额度与实际报销数填进左表（当前为台账口径）。“待对账”一格按财务系统数字替换。项目本质是软件研发，经费执行率低是正常情况，重点讲控费机制。");
}

/* ============ S13 中期结论 ============ */
{
  const s = newSlide(true);
  s.addText("中期检查结论", { x: M, y: 0.55, w: 6, h: 0.45, fontSize: 20, fontFace: F, color: C.onDark, margin: 0 });
  s.addShape(pres.shapes.RECTANGLE, { x: M, y: 1.08, w: 9.0, h: 0.045, fill: { color: C.accent }, line: { color: C.accent } });
  const points = [
    ["1. 执行情况：", "总体按立项计划推进，技术路线未偏离；唯一滞后的论文节点已于 10 月补齐 18 页初稿"],
    ["2. 阶段性成果：", "系统 v0.8 建成可用；闭环实验收敛率 94.2%、危险建议消除率 100%、缺陷检出 95.7%，五项指标全面超越立项目标"],
    ["3. 问题与解决：", "幻觉、数据、误报、指标口径、离线化五大问题全部闭环，解法均经 155 个真实设计数据验证"],
    ["4. 下阶段：", "论文投稿与软著提交两条主线，配套明确工作方案，2027 上半年具备结题条件"],
  ];
  const runs = points.flatMap(([b, rest], i) => [
    { text: b, options: { bold: true, color: "FFFFFF" } },
    { text: rest, options: { color: C.onDark2, breakLine: i < points.length - 1 } },
  ]);
  s.addText(runs, { x: M, y: 1.45, w: CW, h: 4.2, fontSize: 16.5, fontFace: F, paraSpaceAfter: 20, valign: "top", margin: 0 });
  s.addText("开源仓库：github.com/Lin-666spring/eda_ai_assistant　·　智绘PCB 项目组（李泓达 · 林昊晞 · 刘澈）　·　2026-10", { x: M, y: 6.35, w: CW, h: 0.4, fontSize: 13, fontFace: F, color: C.onDark, margin: 0 });
  s.addNotes("结论页停留 during Q&A。预期问题：①覆盖率口径（A/B 两口径）②为什么自研解析器（官方导出交叉验证）③论文投稿目标期刊。");
}

pres.writeFile({ fileName: "智绘PCB_大创中期检查汇报_2026-10-19.pptx" }).then(() => console.log("OK pptx written"));
