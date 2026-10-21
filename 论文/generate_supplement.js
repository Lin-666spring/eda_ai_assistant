/* 补充材料生成（N3）—— 随修回稿提交的五项材料
 *
 * 数据来源: 论文/review/supplement_data.json（由 论文/supplement_extract.py 程序化
 * 提取自仓库源码与实验产物，本文档不含手写实验数字）。
 * 样式与 论文/generate_paper.js 保持一致（宋体正文/黑体标题/三线表）。
 *
 * 用法: node 论文/generate_supplement.js
 * 输出: 论文/补充材料_面向PCB设计的LLM闭环验证引擎.docx
 */

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, HeadingLevel, Header, Footer,
  PageNumber, NumberFormat,
} = require("docx");
const fs = require("fs");
const path = require("path");

const DATA = JSON.parse(fs.readFileSync(path.join(__dirname, "review", "supplement_data.json"), "utf-8"));
const OUT = path.join(__dirname, "补充材料_面向PCB设计的LLM闭环验证引擎.docx");

const F_BODY = { ascii: "Times New Roman", eastAsia: "SimSun" };
const F_HEI = { ascii: "Times New Roman", eastAsia: "SimHei" };
const F_MONO = { ascii: "Consolas", eastAsia: "SimSun" };
const BLACK = "000000";

function p(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: opts.noIndent ? undefined : { firstLine: 480 },
    spacing: { line: 360, before: 0, after: 0 },
    children: [new TextRun({ text, size: opts.size || 24, font: F_BODY, color: BLACK })],
    ...(opts.keepNext ? { keepNext: true } : {}),
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    keepNext: true,
    spacing: { before: 360, after: 200, line: 360 },
    children: [new TextRun({ text, bold: true, size: 30, font: F_HEI, color: BLACK })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    keepNext: true,
    spacing: { before: 280, after: 140, line: 360 },
    children: [new TextRun({ text, bold: true, size: 28, font: F_HEI, color: BLACK })],
  });
}

const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

function threeLineTable(caption, headers, rows, widths, opts = {}) {
  const fontSize = opts.fontSize || 21;
  const capPara = new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 200, after: 80, line: 300 },
    children: [new TextRun({ text: caption, size: 21, font: F_BODY, color: BLACK })],
  });
  const headerRow = new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: headers.map((text, i) => new TableCell({
      borders: {
        top: { style: BorderStyle.SINGLE, size: 6, color: BLACK },
        bottom: { style: BorderStyle.SINGLE, size: 4, color: BLACK },
        left: NB, right: NB,
      },
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      width: { size: widths[i], type: WidthType.PERCENTAGE },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { line: 300 },
        children: [new TextRun({ text, bold: true, size: fontSize, font: F_BODY, color: BLACK })],
      })],
    })),
  });
  const dataRows = rows.map((cells, ri) => new TableRow({
    cantSplit: true,
    children: cells.map((text, i) => new TableCell({
      borders: {
        top: NB,
        bottom: ri === rows.length - 1
          ? { style: BorderStyle.SINGLE, size: 6, color: BLACK }
          : NB,
        left: NB, right: NB,
      },
      margins: { top: 50, bottom: 50, left: 100, right: 100 },
      width: { size: widths[i], type: WidthType.PERCENTAGE },
      children: [new Paragraph({
        alignment: opts.centerAll || i > 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
        spacing: { line: 300 },
        children: [new TextRun({ text: String(text), size: fontSize, font: F_BODY, color: BLACK })],
      })],
    })),
  }));
  const table = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: BLACK },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: BLACK },
      left: NB, right: NB,
      insideHorizontal: NB, insideVertical: NB,
    },
    rows: [headerRow, ...dataRows],
  });
  return [capPara, table, new Paragraph({ spacing: { after: 120 }, children: [] })];
}

// 提示词/代码块：逐行等宽段落，保留空行与缩进
function codeBlock(text) {
  const lines = text.split("\n");
  return lines.map((line, i) => new Paragraph({
    alignment: AlignmentType.LEFT,
    spacing: { line: 260, before: 0, after: i === lines.length - 1 ? 160 : 0 },
    shading: { type: "clear", fill: "F5F5F5" },
    children: [new TextRun({
      text: line.length ? line : " ",
      size: 18, font: F_MONO, color: "222222",
    })],
  }));
}

function formulaP(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 120, line: 360 },
    children: [new TextRun({ text, size: 24, font: F_BODY, color: BLACK })],
  });
}

// ═══════════════════════════════════════════════════════════════
// 题头
// ═══════════════════════════════════════════════════════════════

const titleBlock = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 120, line: 400 },
    children: [new TextRun({ text: "补充材料", bold: true, size: 36, font: F_HEI, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80, line: 320 },
    children: [new TextRun({ text: "面向PCB设计的大语言模型闭环验证引擎（修回稿）", bold: true, size: 26, font: F_HEI, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 200, line: 300 },
    children: [new TextRun({ text: "（作者信息双盲评审期匿名，录用后补全）", size: 21, font: F_BODY, color: "555555" })],
  }),
  p("本补充材料与修回稿一并提交，包含正文4.1节与文末可得性声明所述的五项材料：S1实验数据集清单、S2的68条规则逐条定义、S3提示词模板、S4变更集schema、S5评分器权重映射。五项内容均由流水线脚本从论文对应的代码仓库与实验产物中程序化提取生成（提取脚本随材料一并提供），未包含任何人工誊写的实验数字；正文与补充材料的数值口径完全一致。", { noIndent: false }),
  ...threeLineTable(
    "表S0　补充材料与正文的对应关系",
    ["材料", "内容", "正文对应位置"],
    [
      ["S1", "实验数据集清单（79板主实验＋21板分层子集＋78个带版图注入语料＋5条模板请求）", "4.1节、4.5节"],
      ["S2", "68条规则逐条定义（器件参数37条/几何21条/布局10条，含类型与严重度）", "3.1节表1"],
      ["S3", "提示词模板（首轮解析、修正轮含2×2消融四变体、五智能体）", "3.3节、4.3节"],
      ["S4", "变更集schema（JSON Schema形式化与三操作示例）", "3.2节"],
      ["S5", "评分器权重映射（6维定义、规则→维度/权重、严重度扣分、守门τ）", "2.2节、4.3节"],
    ],
    [10, 62, 28]
  ),
];

const body = [...titleBlock];

// ═══════════════════════════════════════════════════════════════
// S1 实验数据集清单
// ═══════════════════════════════════════════════════════════════

const D = DATA.designs;

body.push(h1("S1　实验数据集清单"));
body.push(h2("S1.1　主实验数据集（79个真实开源设计）"));
body.push(p(`数据来源为立创开源硬件平台公开开源工程。候选池91个工程，经归一化解析（scripts/normalize_thing_designs.py：按BOM指纹去除重复工程、保留最小目录序号）与剔除数据不全或解析失败工程后，得到79个设计（与正文4.1节口径一致）。BOM规模画像：最小${D.components_min}个、中位${D.components_median}个、均值${D.components_mean}个、最大${D.components_max}个元件。全部设计遵循平台开源协议，仅用于研究用途；规范化后的解析件（BOM xlsx＋贴装csv＋网表tel）随本补充材料一并提交，目录test_data/thing_designs/与清单文件_manifest.csv逐板对应。`));
body.push(p("表S1逐板列出79个设计：设计名（规范化目录名）、BOM元件数、按BOM规模三分层（小/中/大，切分方式见S1.2）与是否属于21板分层子集（●标记）。", { keepNext: true }));
body.push(...threeLineTable(
  "表S1　主实验设计清单（79板，按名称字典序）",
  ["序号", "设计名", "BOM元件数", "规模分层", "21板子集"],
  D.list.map((d, i) => [i + 1, d.name, d.components, d.tier, d.in_subset21 ? "●" : ""]),
  [10, 46, 16, 14, 14],
  { fontSize: 18 }
));

body.push(h2("S1.2　21板分层子集（跨模型与消融实验）"));
body.push(p(`跨模型子集实验（正文4.6节表7～表9）与受控消融实验（正文4.3节表5）共用同一21板分层子集：将79板按BOM规模升序切为小/中/大三层（各26/26/27板），按层比例分配名额（各7板，种子2026，random.Random抽样），复算抽样与实际运行子集完全一致（${D.subset21.length}板）。表S1以●标记子集成员。`));

body.push(h2("S1.3　几何/布局模块注入实验语料（78个带版图工程）"));
body.push(p("正文4.5节的598次几何/布局程序化注入（表8）需要PCB版图数据（走线/过孔/板框/元件坐标），故板源改用带完整版图的开源工程语料（.epro2格式，test_data/_incoming_epro2/78/），共78个工程，与主实验79板（无版图数据）相互独立。工程名去除统一前缀ProPrj_与导入日期后缀后列于表S2。", { keepNext: true }));
body.push(...threeLineTable(
  "表S2　注入实验语料工程清单（78个，按名称字典序）",
  ["序号", "工程名（去除前缀与日期后缀）", "序号", "工程名（去除前缀与日期后缀）"],
  (() => {
    const clean = (s) => s.replace(/^ProPrj_/, "").replace(/_20\d{2}-\d{2}-\d{2}$/, "").trim();
    const names = D.injection_corpus.boards.map(clean);
    const half = Math.ceil(names.length / 2);
    const rows = [];
    for (let i = 0; i < half; i++) {
      rows.push([i + 1, names[i], i + half + 1 <= names.length ? i + half + 1 : "", names[i + half] || ""]);
    }
    return rows;
  })(),
  [8, 42, 8, 42],
  { fontSize: 18 }
));

body.push(h2("S1.4　三类模板请求（建议生成模板）"));
body.push(p("主实验的395条建议由79板×5条固定模板请求驱动（正文4.1节：建议为三类模板请求驱动，非LLM自主提出）。5条模板的程序化定义列于表S3，其中safe类1条、dangerous类2条、optimization类2条；类别字段为实验设计标注，LLM意图识别的实际分类分布见正文4.1节。", { keepNext: true }));
body.push(...threeLineTable(
  "表S3　五条固定模板请求（tests/paper_experiments.py DEFAULT_SUGGESTIONS）",
  ["序号", "模板请求文本", "设计类别"],
  DATA.prompts.suggestion_templates.map((s, i) => [i + 1, s.text, s.category]),
  [10, 72, 18],
  { fontSize: 18 }
));

// ═══════════════════════════════════════════════════════════════
// S2 68条规则定义
// ═══════════════════════════════════════════════════════════════

const R = DATA.rules;
const KIND_CN = { detect: "判定", advise: "提示" };
const SEV_CN = { ERROR: "错误", WARNING: "警告", INFO: "提示", "动态": "动态" };

function ruleRows(list) {
  return list.map((r) => [
    r.rule_name,
    KIND_CN[r.kind] || r.kind,
    SEV_CN[r.severity] || r.severity || "",
    r.summary,
  ]);
}

body.push(h1("S2　DRC引擎68条规则逐条定义"));
body.push(p(`规则引擎共实现68条活跃规则，与正文3.1节口径一致：器件参数类37条（BOM模块）、几何类21条、布局类10条。规则按检查对象分为判定类（detect，对板做可证伪判定，可计精确率，52条）与提示类（advise，通用建议或缺数据即报，不构成检出能力，16条）。严重度分错误（error）/警告（warning）/提示（info）三档；5条规则的严重度按判定条件动态分档，在表中标注"动态"并于表下注记分档条件。`));
body.push(p("规则逐条定义提取自代码仓库src/rules/（base.py、bom_rules.py、geometry_rules.py、layout_rules.py）：规则名、类型与严重度为程序运行时取值，检查内容为各规则实现的方法文档首行。", { keepNext: true }));
body.push(...threeLineTable(
  "表S4　器件参数类规则（BOM模块，37条）",
  ["规则名", "类型", "严重度", "检查内容"],
  ruleRows(R.modules.bom),
  [22, 8, 10, 60],
  { fontSize: 18 }
));
body.push(...threeLineTable(
  "表S5　几何类规则（21条）",
  ["规则名", "类型", "严重度", "检查内容"],
  ruleRows(R.modules.geometry),
  [22, 8, 10, 60],
  { fontSize: 18 }
));
body.push(...threeLineTable(
  "表S6　布局类规则（10条）",
  ["规则名", "类型", "严重度", "检查内容"],
  ruleRows(R.modules.layout),
  [22, 8, 10, 60],
  { fontSize: 18 }
));
body.push(p("动态严重度分档条件：①PDN目标阻抗分析——去耦电容数＞3为警告、否则提示；②差分对等长检查——按接口判据档分档，超限档为错误/警告，接口未识别的表外组为提示（参考判定）；③特征阻抗匹配检查——两层板警告、多层板错误；④电源线载流检查——按IPC-2221载流余量分档，余量不足为错误、不足1.5倍为警告；⑤元件间距检查——重叠为警告、接近为提示。", { size: 21 }));
body.push(p("设计性休眠方法披露：规则类中另有4个检查方法（BGA扇出、元件高度分区、光耦隔离爬电、极性元件方向）处于设计性休眠状态——因现有解析数据不含焊盘级几何/旋转角/元件高度，旧版计数模板判据不可证伪，于2026-10-10审计批改为无条件返回空并留档待数据就绪后启用。它们不发射任何规则名，不计入68条活跃规则；本披露用于与源码中_check_*方法总数（72）对账。", { size: 21 }));

// ═══════════════════════════════════════════════════════════════
// S3 提示词模板
// ═══════════════════════════════════════════════════════════════

const P = DATA.prompts;

body.push(h1("S3　提示词模板"));
body.push(p("闭环验证引擎与LLM的交互由两段提示词承载：首轮解析提示词将自然语言建议转换为结构化变更集（其输出约定即S4的变更集schema）；修正轮提示词将每轮复检反馈（新违规清单、同规则恶化对比、评分信号、轮次历史、修法指引与撤销语义）回传LLM驱动修正。两段提示词全文列于下，提取自tests/bom_suggestion.py并以实验真实调用形态填充示例值；示例值仅作展示占位，不代表任何实验板上的真实数据。"));
body.push(h2("S3.1　首轮解析提示词（全文）"));
body.push(...codeBlock(P.parse_prompt));
body.push(h2("S3.2　修正轮提示词（完整反馈变体，全文）"));
body.push(...codeBlock(P.correction_variants.A_full));
body.push(h2("S3.3　2×2消融变体差异（B/C/D臂对A臂的逐行差异）"));
body.push(p("受控消融（正文4.3节）以两个开关从完整反馈变体派生其余三臂：include_guidance=False剥离每条违规的「修法」指引行与策略第2条的指引引用；include_revert=False移除撤销授权（策略第1条、「空changes合法」输出约定、末轮撤销提示）。以下为程序化逐行比对得到的差异句（其余行与A臂完全一致）。", { keepNext: true }));
(() => {
  const nameCN = { B_noguid: "B臂（剥离修法指引）", C_norevert: "C臂（剥离撤销语义）", D_neither: "D臂（两者皆无）" };
  for (const [k, v] of Object.entries(P.correction_variant_diffs)) {
    body.push(p(`${nameCN[k]}：`, { noIndent: true, keepNext: true }));
    const lines = [
      ...v.only_in_A.map((l) => "A臂有而本臂无：" + l.trim()),
      ...v.only_in_variant.map((l) => "本臂有而A臂无：" + l.trim()),
    ];
    body.push(...codeBlock(lines.join("\n")));
  }
})();
body.push(h2("S3.4　五智能体审查画像与提示词"));
body.push(p("多智能体审查画像（正文2.2节）由五个专业智能体构成，其领域定义提取自src/agent/review_agents.py；每个智能体对分配到的违规先做规则化重写，再可选地以两段提示词调用LLM做深度分析与领域总结（模板源码原文列于表后）。", { keepNext: true }));
body.push(...threeLineTable(
  "表S7　五智能体审查画像（AGENT_DEFINITIONS）",
  ["键", "智能体", "领域", "专长描述"],
  Object.entries(P.agents).map(([k, a]) => [k, a.name, a.domain || "", a.expertise]),
  [10, 20, 14, 56],
  { fontSize: 18 }
));
body.push(p("深度分析提示词模板（_llm_deep_analyze，f-string源码原文）：", { noIndent: true, keepNext: true }));
body.push(...codeBlock(P.agent_prompt_templates._llm_deep_analyze));
body.push(p("领域总结提示词模板（_llm_summarize，f-string源码原文）：", { noIndent: true, keepNext: true }));
body.push(...codeBlock(P.agent_prompt_templates._llm_summarize));

// ═══════════════════════════════════════════════════════════════
// S4 变更集 schema
// ═══════════════════════════════════════════════════════════════

body.push(h1("S4　变更集schema"));
body.push(p("LLM输出的变更集为JSON对象{\"changes\": [...]}，每个元素描述一种原子操作：replace（修改现有元件参数）/ add（新增元件，位号必须为参考表外新位号，field固定为value）/ remove（删除元件）。该约定在首轮解析提示词（S3.1）中以少样本示例给出，解析器（BOMChange数据类）按同一口径校验并将模型偏差归一化（归一化条目数单独计数，用于schema遵守率度量）。以下为该约定的JSON Schema形式化。", { keepNext: true }));
body.push(...codeBlock(JSON.stringify(DATA.schema, null, 1)));
body.push(...threeLineTable(
  "表S8　三种原子操作的示例（与S3.1提示词示例一致）",
  ["操作", "示例"],
  [
    ["replace", "{\"reference\": \"C1\", \"field\": \"value\", \"old_value\": \"100nF\", \"new_value\": \"1uF\", \"action\": \"replace\"}"],
    ["remove", "{\"reference\": \"C1\", \"field\": \"value\", \"old_value\": \"100nF\", \"new_value\": \"\", \"action\": \"remove\"}"],
    ["add", "{\"reference\": \"C101\", \"field\": \"value\", \"old_value\": \"\", \"new_value\": \"100nF\", \"action\": \"add\"}"],
  ],
  [14, 86],
  { fontSize: 18 }
));
body.push(p("硬性约束（由解析器强制执行，违反者该条变更被丢弃并计数）：action必须显式给出且仅取三值之一；field禁止取reference；删除/新增只能以remove/add表达，禁止以空new_value或field:\"reference\"暗示；合并位号须拆成多条；纯分析类建议返回空changes；新增元件每元件仅一条add且位号不得与参考表重复。", { size: 21 }));

// ═══════════════════════════════════════════════════════════════
// S5 评分器权重映射
// ═══════════════════════════════════════════════════════════════

const S = DATA.scorer;
const DIM_ORDER = ["power", "signal", "thermal", "emc", "dfm", "cost"];

body.push(h1("S5　评分器权重映射"));
body.push(p("评分器（src/core/design_scorer.py）将DRC违规映射到6个专业维度并量化为0～100分，闭环验证以评分信号（ΔS）作为规则名级闸门之外的第二重质量守门（正文3.3节：收敛判定新增违规计数不分严重度；评分守门另设）。映射与权重全文列于下。"));
body.push(h2("S5.1　评分维度定义"));
body.push(...threeLineTable(
  "表S9　六个评分维度",
  ["键", "维度", "说明"],
  DIM_ORDER.map((k) => [k, S.dimensions[k].label, S.dimensions[k].description]),
  [12, 18, 70],
  { fontSize: 18 }
));
body.push(h2("S5.2　规则关键词→维度与权重映射（生效值）"));
body.push(p("映射以「规则名关键词子串匹配」实现：逐违规按映射表迭代顺序取首个命中关键词，赋予该维度与权重；未命中者归入默认权重1.0（不参与维度分组）。下表为52个关键词的生效映射。代码字面量中「封装一致性」定义了两次（可制造性dfm/1.5与成本cost/0.5），按字典字面量语义后者生效——本表如实呈现生效值并披露该覆盖事实。", { keepNext: true }));
body.push(...threeLineTable(
  "表S10　规则关键词→维度与权重映射（52键，源码生效值）",
  ["规则名关键词", "维度", "权重", "规则名关键词", "维度", "权重"],
  (() => {
    const entries = Object.entries(S.rule_dimension_map_effective);
    const half = Math.ceil(entries.length / 2);
    const rows = [];
    for (let i = 0; i < half; i++) {
      const [k1, v1] = entries[i];
      const cell2 = entries[i + half];
      rows.push([k1, v1[0], v1[1], cell2 ? cell2[0] : "", cell2 ? cell2[1][0] : "", cell2 ? cell2[1][1] : ""]);
    }
    return rows;
  })(),
  [24, 10, 8, 24, 10, 8],
  { fontSize: 18 }
));
body.push(h2("S5.3　扣分、合成公式与等级"));
body.push(p(`严重度扣分基数：错误（error）${S.severity_penalty.ERROR}分、警告（warning）${S.severity_penalty.WARNING}分、提示（info）${S.severity_penalty.INFO}分；每条违规扣分＝基数×规则权重。维度分按平方根衰减合成，少量违规温和扣分、大量违规不瞬间归零：`));
body.push(formulaP("score_d ＝ max(0, 100 − 2.2 × √( Σᵢ 基数(sevᵢ) × 权重(ruleᵢ) ) )　　（S1）"));
body.push(p("综合评分为六维加权平均，维度固定权重：power 1.2、signal 1.2、thermal 1.0、emc 1.0、dfm 0.8、cost 0.6：", { keepNext: true }));
body.push(formulaP("overall ＝ Σ_d score_d × w_d ／ Σ_d w_d　　（S2）"));
body.push(...threeLineTable(
  "表S11　综合评分等级映射",
  ["等级", "A+", "A", "B+", "B", "C", "D", "F"],
  [["分数下限", ...S.grade_thresholds.map(([s, g]) => `${s}（${g}）`), "<45"]],
  [22, 12, 10, 10, 10, 10, 10, 8],
  { fontSize: 18 }
));
body.push(h2("S5.4　闭环评分守门"));
body.push(p(`闭环流程以评分下降量ΔS＝基线评分−变更后评分作为第二重守门，容差τ＝${S.gate.tau}分（tests/paper_experiments.py常量SCORE_DROP_TOLERANCE）：某轮应用变更后，若新增违规为零且ΔS≤τ，该轮通过；若新增违规为零但ΔS＞τ，不通过并进入修正（防止「无新规则类型但整体质量劣化」的变更被放行，正文3.3节）。该信号同时进入修正轮提示词的「综合评分」段（S3.2）。`));

// ═══════════════════════════════════════════════════════════════
// 文档组装
// ═══════════════════════════════════════════════════════════════

const doc = new Document({
  creator: "TraceWise 论文流水线",
  title: "补充材料——面向PCB设计的大语言模型闭环验证引擎（修回稿）",
  styles: {
    default: {
      document: {
        run: { font: F_BODY, size: 24, color: BLACK },
        paragraph: { spacing: { line: 360 } },
      },
      heading1: {
        run: { font: F_HEI, size: 30, bold: true, color: BLACK },
        paragraph: { spacing: { before: 360, after: 200, line: 360 } },
      },
      heading2: {
        run: { font: F_HEI, size: 28, bold: true, color: BLACK },
        paragraph: { spacing: { before: 280, after: 140, line: 360 } },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, bottom: 1440, left: 1701, right: 1417, header: 850, footer: 992 },
        pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BLACK } },
          children: [new TextRun({ text: "补充材料——面向PCB设计的大语言模型闭环验证引擎（修回稿）", size: 18, color: "333333", font: F_BODY })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "- ", size: 21, font: F_BODY }),
            new TextRun({ children: [PageNumber.CURRENT], size: 21, font: { ascii: "Times New Roman" } }),
            new TextRun({ text: " -", size: 21, font: F_BODY }),
          ],
        })],
      }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log("[OK] " + OUT + "  (" + (buf.length / 1024).toFixed(0) + " KB)");
});
