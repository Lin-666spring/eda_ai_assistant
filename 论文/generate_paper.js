/* 论文初稿生成 —— 面向PCB设计的大语言模型闭环验证引擎（中文期刊口径）
 * 运行: node generate_paper.js  (依赖: docx, image-size; 已 npm install)
 * 数据来源: experiment_results/run_thing_full_glm53 (2026-09-13, 79设计/395建议)
 *           experiment_results/smoke_deepseek2 (跨模型冒烟)
 * 图表来源: 论文/figures/fig1..fig6 (fig1 由 scripts/paper_arch_diagram.py 生成)
 */

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, PageNumber, NumberFormat,
  AlignmentType, HeadingLevel, WidthType, BorderStyle, TabStopType,
} = require("docx");
const fs = require("fs");
const path = require("path");

const _is = require("image-size");
const imageSize = _is.imageSize || _is.default || _is;

const FIG_DIR = path.join(__dirname, "figures");
const OUT = path.join(__dirname, "论文初稿_面向PCB设计的LLM闭环验证引擎.docx");

// ── 字体/字号常量（学术场景 Profile A：正文纯黑、宋体+Times） ──
const F_BODY = { ascii: "Times New Roman", eastAsia: "SimSun" };
const F_HEI = { ascii: "Times New Roman", eastAsia: "SimHei" };
const BLACK = "000000";

// ── 基础构件 ─────────────────────────────────────────────
function p(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: opts.noIndent ? undefined : { firstLine: 480 },
    spacing: { line: 360, before: 0, after: 0 },
    children: [new TextRun({ text, size: 24, font: F_BODY, color: BLACK })],
    ...(opts.keepNext ? { keepNext: true } : {}),
  });
}

function runsPara(runs, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.JUSTIFIED,
    indent: opts.noIndent ? undefined : { firstLine: 480 },
    spacing: { line: 360 },
    ...(opts.keepNext ? { keepNext: true } : {}),
    children: runs,
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

function fig(file, caption, widthPx) {
  const buf = fs.readFileSync(path.join(FIG_DIR, file));
  const dim = imageSize(buf);
  const w = widthPx;
  const h = Math.round(w * dim.height / dim.width);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 160 },
      keepNext: true,
      children: [new ImageRun({ data: buf, transformation: { width: w, height: h }, type: "png" })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 60, after: 200, line: 300 },
      children: [new TextRun({ text: caption, size: 21, font: F_BODY, color: BLACK })],
    }),
  ];
}

const NB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

function threeLineTable(caption, headers, rows, widths) {
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
        children: [new TextRun({ text, bold: true, size: 21, font: F_BODY, color: BLACK })],
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
        alignment: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
        spacing: { line: 300 },
        children: [new TextRun({ text: String(text), size: 21, font: F_BODY, color: BLACK })],
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

// 公式段：居中公式 + 右侧编号
function formula(runs, number) {
  return new Paragraph({
    tabStops: [
      { type: TabStopType.CENTER, position: 4400 },
      { type: TabStopType.RIGHT, position: 8780 },
    ],
    spacing: { before: 120, after: 120, line: 360 },
    children: [
      new TextRun({ text: "\t", size: 24, font: F_BODY }),
      ...runs,
      new TextRun({ text: "\t" + number, size: 24, font: F_BODY, color: BLACK }),
    ],
  });
}

const T = (text) => new TextRun({ text, size: 24, font: F_BODY, color: BLACK });
const IT = (text) => new TextRun({ text, size: 24, font: F_BODY, color: BLACK, italics: true });
const SUP = (text) => new TextRun({ text, size: 24, font: F_BODY, color: BLACK, superScript: true });
const SUB = (text) => new TextRun({ text, size: 24, font: F_BODY, color: BLACK, subScript: true });

function refEntry(text) {
  return new Paragraph({
    indent: { left: 420, hanging: 420 },
    spacing: { line: 320 },
    children: [new TextRun({ text, size: 21, font: F_BODY, color: BLACK })],
  });
}

// ── 题录区 ─────────────────────────────────────────────
const titleBlock = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 160, line: Math.ceil(16 * 23), lineRule: "atLeast" },
    children: [new TextRun({ text: "面向PCB设计的大语言模型闭环验证引擎", bold: true, size: 32, font: F_HEI, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160, line: 300 },
    children: [new TextRun({ text: "A Closed-Loop Verification Engine for LLM-Assisted PCB Design", bold: true, size: 26, font: { ascii: "Times New Roman" }, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 60, line: 320 },
    children: [new TextRun({ text: "【作者姓名】1，【合作者姓名】2，【指导教师姓名】1", size: 24, font: F_BODY, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 60, line: 300 },
    children: [new TextRun({ text: "（1. 吉林大学 仪器电气学院，长春 130012；2. 【第二单位】）", size: 21, font: F_BODY, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 240, after: 40, line: 320 },
    children: [
      new TextRun({ text: "摘　要：", bold: true, size: 21, font: F_HEI, color: BLACK }),
      new TextRun({ text: "大语言模型（LLM）正在进入印制电路板（PCB）辅助设计领域，但其生成建议中的幻觉问题——虚构非标称器件参数、给出违反载流与耐压等物理约束的危险变更——使其难以直接用于真实设计。针对这一问题，本文提出并实现了一个面向PCB设计的LLM闭环验证引擎：LLM生成的BOM变更建议必须经过由68条规则构成的设计规则检查（DRC）引擎复检，未通过的建议携带结构化修正反馈（新违规清单、修法指引与撤销语义）驱动LLM迭代修正，最多3轮；物理约束类判定由IPC-2221/IPC-2141标准公式在本地确定性计算，不依赖LLM；在此基础上，五个领域审查智能体（电源完整性、信号完整性、热管理、电磁兼容、可制造性）并行复审并输出六维评分。在79个立创开源平台真实设计、395条建议的实验中：BOM变更建议收敛率94.2%，平均迭代1.14轮；blocking级新增违规消除率100%，其中39条危险建议被整体撤销；程序化缺陷注入280次检出率95.7%；多智能体审查平均评分94.2。结果表明，以确定性规则引擎为外部反馈源的闭环机制能够在PCB设计域有效抑制LLM幻觉，为LLM深度参与PCB设计提供了一条可落地的可信化路径。", size: 21, font: F_BODY, color: BLACK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 320 },
    children: [
      new TextRun({ text: "关键词：", bold: true, size: 21, font: F_HEI, color: BLACK }),
      new TextRun({ text: "印制电路板；大语言模型；设计规则检查；闭环验证；多智能体系统；幻觉抑制", size: 21, font: F_BODY, color: BLACK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 40, line: 300 },
    children: [
      new TextRun({ text: "Abstract: ", bold: true, size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
      new TextRun({ text: "Large language models (LLMs) are entering the domain of printed circuit board (PCB) design assistance, yet hallucinations in their suggestions, such as fabricated non-standard component parameters and dangerous changes violating current-carrying or voltage-rating constraints, prevent direct use in real designs. This paper proposes and implements a closed-loop verification engine for LLM-assisted PCB design: every LLM-generated BOM change must pass re-examination by a design rule checking (DRC) engine of 68 rules; failed suggestions are returned to the LLM with structured correction feedback (violation list, fixing guidance, and revert semantics) for iterative refinement within three rounds; physics-constrained judgments are computed deterministically from IPC-2221/IPC-2141 standard formulas without LLM involvement; five domain review agents (power integrity, signal integrity, thermal, EMC, and manufacturability) then perform parallel re-review with a six-dimension score. On 79 real open-source designs with 395 suggestions, the engine achieves a 94.2% convergence rate for BOM-changing suggestions with an average of 1.14 iterations, a 100% elimination rate of blocking-level newly introduced violations (39 dangerous suggestions fully reverted), a 95.7% detection rate over 280 programmatic defect injections, and a mean multi-agent score of 94.2. The results show that a closed loop with a deterministic rule engine as the external feedback source effectively suppresses LLM hallucinations in the PCB domain.", size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 200, line: 300 },
    children: [
      new TextRun({ text: "Key words: ", bold: true, size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
      new TextRun({ text: "printed circuit board; large language model; design rule checking; closed-loop verification; multi-agent system; hallucination suppression", size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
    ],
  }),
];

// ── 正文 ─────────────────────────────────────────────
const body = [];

// 1 引言
body.push(h1("1　引言"));
body.push(p("印制电路板（Printed Circuit Board, PCB）是电子系统的物理载体，其设计质量直接决定产品的电气性能、可靠性与可制造性。近年来，以立创EDA为代表的免费云端EDA工具与活跃的开源硬件社区大幅降低了PCB设计门槛，大量学生、创客与中小团队得以独立完成从原理图到布局布线的全流程设计。然而设计门槛的降低并未同步降低审查门槛：商用EDA的DRC（Design Rule Checking）集中于间距、线宽等几何制造规则，而器件选型是否合规、去耦网络是否完整、保护电路是否缺失等电路语义层面的审查，仍然高度依赖有经验工程师的人工复核，成为开源硬件设计质量的突出短板。"));
body.push(p("大语言模型（Large Language Model, LLM）凭借广泛的电子学知识与自然语言交互能力，为自动化设计审查提供了新的可能：用户以口语化中文描述需求，LLM即可生成器件替换、参数调整、网络增删等结构化设计建议。但LLM的幻觉问题在物理设计域尤为危险：模型可能虚构不存在的标准电阻值或封装，推荐耐压不足的电容，甚至建议删除TVS保护器件或以过细走线承载大电流。此类建议一旦未经校验直接进入设计，后果是板卡烧毁、认证失败等真实物理损失。已有研究表明，LLM在缺乏外部反馈的情况下难以通过自我反思可靠纠错[6]，因此让LLM安全参与PCB设计的关键，在于为其配备确定性的外部验证器并构成修正闭环。"));
body.push(p("现有LLM辅助EDA的研究主要面向IC设计流程：ChipNeMo通过领域适配增强LLM的芯片设计问答与脚本生成能力[2]，ChatEDA以LLM为控制器编排EDA工具完成RTL到GDSII流程[3]，EDAid则用多个领域微调模型协作生成流程脚本[4]。这些工作的验证环节依赖成熟IC工具链，其经验难以直接迁移到PCB级：PCB设计数据异构（BOM、网表、几何多源并存），审查规则体系以IPC标准与器件语义为主而非IC工艺 DesignRule，且LLM在PCB域的产出形态是建议级的BOM/参数变更而非可执行脚本，缺少与之配套的验证-反馈-修正闭环机制。"));
body.push(p("针对上述空白，本文提出并实现了一个面向PCB设计的LLM闭环验证引擎，主要贡献包括三方面：（1）闭环验证架构：将LLM建议生成与本地DRC规则引擎（68条）构成建议-检查-反馈-修正的迭代闭环，并提出以blocking级新增违规消除率与收敛轮次为核心的量化评估体系；（2）电路计算增强验证：载流能力、特征阻抗、降额等物理约束按IPC-2221/IPC-2141标准公式在本地确定性计算，零LLM依赖，从机制上排除该类幻觉；（3）多智能体协同审查：五个领域审查智能体对通过闭环的建议进行并行复审，输出六维评分雷达图，为设计质量提供整体画像。在79个真实开源设计、395条建议的大规模实验中，各项指标均达到预期目标，验证了该架构的有效性。"));

// 2 相关工作
body.push(h1("2　相关工作"));
body.push(h2("2.1　大语言模型在EDA中的应用"));
body.push(p("LLM与EDA的结合是近两年的研究热点[1]。NVIDIA的ChipNeMo在通用LLM基础上进行领域继续预训练与适配，在工程聊天问答与脚本生成任务上超过通用模型[2]。ChatEDA构建了以LLM（AutoMage）为核心的自主智能体，将EDA工具作为执行器，通过任务规划与多轮工具交互完成设计流程自动化[3]。EDAid提出发散思考、共同目标的多智能体协作范式，使用领域微调的ChipLlama系列模型协作生成EDA流程脚本，在脚本质量与可靠性上取得显著提升[4]。这些工作验证了LLM参与电子设计的可行性，但均以IC流程脚本为产出物、以IC工具链为验证器。在PCB层面，立创EDA等商用工具已开始引入AI问答与辅助生成能力[16]，但总体仍以直接生成或问答为主，缺少面向建议级变更的验证闭环，正是本文要填补的位置。"));
body.push(h2("2.2　LLM幻觉缓解与迭代修正"));
body.push(p("针对LLM幻觉与错误输出，主流思路可分为三类。其一为提示与解码策略，如思维树（Tree of Thoughts）通过在思维树上搜索改进复杂推理[9]；其二为自我修正，Self-Debug让模型依据自身执行反馈迭代修正代码[7]，Reflexion以语言化的强化信号记忆历史失败[8]；其三为多智能体协作，通过角色分工与相互评审提升可靠性[10]。然而Huang等人系统实验表明，LLM在没有外部可靠反馈的情况下难以真正自我纠错，所谓的自我修正收益往往来自提示诱导[6]。这指向一个明确结论：可靠的修正闭环必须引入外部确定性验证源。在代码域该验证源是编译器与测试，在PCB设计域，本文将其落实为DRC规则引擎与IPC标准物理计算，并以ReAct式推理-行动循环[11]组织LLM与验证器之间的交互。"));
body.push(h2("2.3　设计规则检查与标准计算"));
body.push(p("DRC是EDA的传统支柱，商用工具已高度成熟，但传统DRC以布线几何与制造规则为主，不覆盖器件参数语义（如电容耐压降额、电感饱和电流）。PCB级的物理设计约束由IPC标准体系规定：IPC-2221给出了印制板通用设计要求，其载流能力公式将线宽、铜厚、温升与允许电流联系起来[12]；IPC-2141给出了受控阻抗电路板的设计指南，提供微带线等典型结构的特征阻抗计算式[13]。本文将这些标准公式实现为本地确定性计算模块，与规则引擎共同构成LLM建议的外部验证器，并以BERT类预训练语言模型[5]承担中文意图识别，实现本地小模型与云端LLM的混合推理架构。"));

// 3 引擎设计
body.push(h1("3　闭环验证引擎设计"));
body.push(h2("3.1　总体架构"));
body.push(p("引擎总体架构如图1所示，自上而下分为五层。输入层接收立创EDA工程文件（原理图、BOM与PCB几何数据）及用户的中文自然语言请求；解析层将工程解析为统一的PCB数据模型（器件清单、网络关联、几何与叠层信息），并由本地部署的BERT类小模型完成意图识别，将请求分流为设计审查与知识问答两类，仅前者进入验证流程，后者由LLM结合知识库直接作答。核心层为闭环验证引擎：LLM建议引擎生成的BOM变更建议先经结构化解析与危险操作预检（如删除保护器件、载流不匹配等模式），再交由DRC规则引擎复检；复检引入的新违规将通过结构化修正反馈回传LLM迭代修正，通过复检的建议方可进入下游。审查层由五个领域智能体并行复审，输出层汇聚六维评分雷达图与结构化审查报告（违规清单、修正记录、采纳建议）。"));
body.push(p("该架构遵循两条设计原则。其一是守门语义：任何LLM建议在通过DRC复检之前不得进入设计数据，验证失败的建议可被部分或整体撤销，使LLM的错误输出被隔离在真实设计之外。其二是本地与云端混合：意图识别、规则检查与物理计算全部在本地毫秒级完成且结果确定，仅建议生成与修正两个环节调用云端LLM，既控制了时延与成本，也保证了验证环节本身不受LLM幻觉影响。"));
body.push(...fig("fig1_architecture.png", "图1　闭环验证引擎总体架构", 560));

body.push(h2("3.2　规则体系"));
body.push(p("规则引擎共实现68条规则，按检查对象分为三个模块：器件参数类37条（BOM模块），检查电容耐压降额、电阻功率降额、电感饱和电流、非标称参数值、封装一致性等；几何类21条，检查走线宽度、板边间距、差分对间距、安装孔禁区等；布局类10条，检查去耦电容距离、晶振布局、温度敏感元件布局等。规则体系构成如表1所示。"));
body.push(p("工程实践中，规则进一步区分为判定类与提示类两级：判定类规则（51条）对当前板卡构成可证伪的判定，其检出可直接用于统计精确率；提示类规则（17条，如PDN目标阻抗分析、丝印可读性）在缺少网络关联等数据时只输出设计提示，不构成检出能力。这一区分避免了高频泛报的提示类规则稀释验证信号，保证反馈给LLM的每条违规都有明确语义。每条违规输出三元组（规则名、严重度、修法指引），严重度分为error、warning、info三级，其中error与warning合称blocking级，构成闭环收敛的判定基础，修法指引则直接进入修正反馈提示。"));
body.push(...threeLineTable(
  "表1　DRC规则体系构成",
  ["规则模块", "条数", "典型规则", "示例违规语义"],
  [
    ["器件参数类（BOM）", "37", "电容耐压降额、电阻功率降额、电感饱和电流、参数范围", "器件参数违反物理约束或非标称值"],
    ["几何类", "21", "电源线载流、走线宽度、板边间距、差分对间距", "几何尺寸违反制造与载流约束"],
    ["布局类", "10", "去耦电容距离、晶振布局、温度敏感元件布局", "布局位置违反设计准则"],
    ["合计（判定类51 / 提示类17）", "68", "严重度：error / warning / info", "——"],
  ],
  [30, 10, 34, 26],
));

body.push(h2("3.3　闭环验证算法"));
body.push(p("闭环验证以单条建议为单位执行。给定原始BOM与建议变更集，流程如下：（1）预检：对明显危险的操作模式（删除ESD保护器件、以细走线承载大电流等）先行拦截；（2）应用与复检：将变更集应用到BOM副本，运行完整DRC得到违规集合，与基线违规比对得到新增违规；（3）收敛判定：若满足收敛条件则建议通过，否则构造结构化修正反馈回传LLM；（4）迭代：LLM依据反馈修正变更集（含部分或全部撤销），重复（2）～（3），迭代上限3轮。"));
body.push(p("收敛判定同时要求无新增规则违规与设计评分不劣化。记应用变更后的违规集合中新增违规数为N，基线设计评分为S，修正后评分为S′，容差为τ（取2.0分），收敛条件为："));
body.push(formula([IT("N"), T("new"), SUB("("), IT("V"), T("\u2032"), SUB(")"), T(" = 0　且　Δ"), IT("S"), T(" = "), IT("S"), T("\u2212"), IT("S"), T("\u2032 ≤ "), IT("τ")], "(1)"));
body.push(p("其中新增违规按规则名与基线集合比对过滤，避免把设计固有问题计入建议的责任。评分守门项补充了规则名过滤的盲区：某些变更不触发新规则但会劣化整体设计质量（如批量替换为劣质参数组合），由启发式设计评分器的下降幅度拦截。"));
body.push(p("幻觉抑制效果以blocking级新增违规消除率度量。记某条建议首轮复检引入的blocking级新增违规数为B1，末轮为Bf，消除率定义为："));
body.push(formula([IT("HE"), T(" = ("), IT("B"), SUB("1"), T(" \u2212 "), IT("B"), SUB("f"), T(") / "), IT("B"), SUB("1"), T(" × 100%")], "(2)"));
body.push(p("当首轮即无blocking级新增违规（B1=0，含纯分析类建议）时HE记为100%。结构化修正反馈是闭环收敛的关键设计，包含四类信息：本轮全部新增违规及其修法指引；同规则基线与修正后的触发对比；撤销语义（LLM可以输出空变更集表示全部撤销，也可以撤销部分条目）；以及允许重加条目的补录操作。反馈中显式给出迭代历史摘要，避免LLM重复尝试已失败的策略。工程验证表明，缺少修法指引或撤销语义时，未收敛用例的违规数会在后续轮次中原地不动；这两项设计是收敛率从早期实验的约五成提升至94%的决定性因素。"));

body.push(h2("3.4　电路计算增强验证"));
body.push(p("纯规则匹配无法覆盖的物理约束由标准公式计算模块补齐，该模块完全独立于LLM，输出具有确定性。载流能力按IPC-2221计算[12]：对截面积为A（mil²）的铜导体，允许电流为"));
body.push(formula([
  IT("I"), T(" = "), IT("k"), T(" · (Δ"), IT("T"), T(")"), SUP("0.44"), T(" · ("), IT("A"), T(")"), SUP("0.725"),
], "(3)"));
body.push(p("其中ΔT为允许温升（℃），k为层系数（外层0.048、内层0.024）。例如0.5mm宽、1oz铜厚（35μm）的外层走线截面积约27mil²，在10℃温升下允许电流约1.4A；若LLM建议以该走线承载3A电流，模块将立即判定违规并回传载流不足的修正指引。特征阻抗按IPC-2141微带线公式计算[13]："));
body.push(formula([
  IT("Z"), SUB("0"), T(" = "),
  T("87 / √("), IT("ε"), SUB("r"), T(" + 1.41) · ln[5.98"), IT("h"), T(" / (0.8"), IT("w"), T(" + "), IT("t"), T(")]"),
], "(4)"));
body.push(p("其中εr为板材相对介电常数，h为介质厚度，w为线宽，t为铜厚。阻抗失配、耐压降额、饱和电流等判定同理。将物理约束交由确定性公式而非LLM判断，是该引擎从机制上消除一类幻觉的根本手段：无论LLM如何生成建议，违反IPC约束的变更都不可能通过复检。"));

body.push(h2("3.5　多智能体协同审查"));
body.push(p("通过闭环验证的建议进入多智能体审查层。五个领域审查智能体（表2）各自以领域专家角色审视设计，并行执行：电源完整性审查师关注去耦网络、电源滤波与PDN合理性；信号完整性审查师关注高速信号、阻抗匹配与串扰；热管理审查师关注发热器件布局与散热路径；电磁兼容审查师关注滤波、屏蔽与环路面积；可制造性审查师关注封装、丝印与工艺适配。各智能体输出结构化发现（问题、位置、严重度、建议），合成器将其与DRC结果、BOM统计聚合为电源、信号、热、电磁兼容、可制造性、成本六个维度的评分并输出雷达图，同时给出综合评分与等级。多智能体层不阻断建议（守门由闭环层完成），其价值在于提供超出规则体系覆盖面的整体质量画像与改进方向。"));
body.push(...threeLineTable(
  "表2　领域审查智能体",
  ["智能体", "审查维度"],
  [
    ["电源完整性审查师", "去耦网络完整性、电源滤波、多电源域、PDN合理性"],
    ["信号完整性审查师", "高速信号完整性、阻抗匹配、串扰与回流路径"],
    ["热管理审查师", "发热器件识别、热敏感器件布局、散热路径"],
    ["电磁兼容审查师", "EMI滤波、环路面积、屏蔽与接地策略"],
    ["可制造性审查师", "封装工艺、丝印可读性、测试与装配友好性"],
  ],
  [34, 66],
));

// 4 实验
body.push(h1("4　实验与结果"));
body.push(h2("4.1　实验设置"));
body.push(p("实验数据集来自立创开源平台的79个真实开源工程，覆盖MCU与SoC开发板、核心板、功能扩展与转接板、电源类及应用整机等常见板卡形态，经解析归一化为统一PCB数据模型后进入实验框架。实验按三个阶段执行：阶段A对每个设计运行纯DRC基线检查（不调用LLM）；阶段B执行闭环验证，实验框架以三类典型设计请求驱动每设计5条建议（1条安全检查类、2条危险变更类、2条优化改进类，如移除全部100nF去耦电容、将电源走线加宽并补充去耦组合等），LLM据此生成结构化BOM变更并进入闭环，共395条；阶段C对每设计执行多智能体审查。另设阶段D程序化缺陷注入：向BOM注入五类已知缺陷（移除去耦电容、改为非标电阻值、删除TVS/ESD保护二极管、电容耐压不足、删除晶振负载电容），检验规则引擎的独立检出能力。"));
body.push(p("实验环境为Windows桌面环境，DRC引擎与物理计算在本地CPU执行，建议生成与修正调用云端GLM系列对话模型[14]，意图识别使用本地ONNX量化小模型。评估指标包括：BOM变更建议收敛率（产生变更的建议中满足式(1)的比例）、平均迭代轮次、blocking级新增违规消除率（式(2)）、多智能体综合评分（百分制）与缺陷注入检出率。全量实验共执行973次LLM调用、消耗约211万tokens，闭环验证阶段总耗时126.2分钟。"));
body.push(h2("4.2　DRC基线"));
body.push(p("79个设计的DRC基线共检出1513条违规，平均每板19.2条，其中error级41条、warning级325条、info级1147条，严重度分布如图2所示（按设计展开）。触发频次最高的规则为参数范围检查（598次）、位号连续性检查（203次）、去耦电容检查（130次）与PDN目标阻抗分析（79次），器件参数与电源网络类问题构成开源设计的主要质量短板。DRC单板平均耗时77.1ms（最大1.41s），满足闭环内多次复检的实时性要求。"));
body.push(...fig("fig2_severity.png", "图2　79个设计的DRC基线违规严重度分布", 540));
body.push(h2("4.3　闭环验证结果"));
body.push(p("395条建议的闭环验证结果汇总于表3：388条通过验证（98.2%），其中120条提出了非空变更集，113条在迭代上限内收敛，BOM变更建议收敛率94.2%；经预检与校验后81条实际落盘变更，其余或被整体撤销、或在验证中收缩为空变更；7条未收敛建议均为优化类，在3轮上限处残留1至3条info级提示（blocking级新增违规全部归零），未收敛原因集中于丝印类低严重度规则的反复触发。全部建议平均迭代1.14轮，其中危险类1.25轮、优化类1.10轮，88.1%的建议在首轮即收敛。分类型看：79条安全检查类建议均不产生变更、直接通过；158条危险变更类建议中，9条经修正后落盘通过，39条由LLM依据修正反馈主动整体撤销变更（全撤销是危险建议的正确收敛路径，验证了撤销语义设计的必要性），其余在预检或首轮复检即被拒绝且无残留；158条优化类建议中72条产生变更并全部收敛。"));
body.push(...threeLineTable(
  "表3　闭环验证分建议类型结果",
  ["建议类型", "条数", "通过", "落盘变更", "整体撤销", "平均轮次", "平均耗时"],
  [
    ["安全检查类", "79", "79", "0", "0", "1.00", "2.4 s"],
    ["危险变更类", "158", "158", "9", "39", "1.25", "24.9 s"],
    ["优化改进类", "158", "151", "72", "0", "1.10", "21.8 s"],
    ["合计", "395", "388", "81", "39", "1.14", "19.2 s"],
  ],
  [22, 12, 12, 14, 14, 12, 14],
));
body.push(p("幻觉抑制方面，120条可计量建议的blocking级新增违规消除率平均为100%：变更建议首轮复检平均引入0.78条blocking级新违规（合计94条次），经不超过3轮的修正反馈后全部归零，如图3与图4所示。图3给出多轮用例中blocking违规数随轮次的收敛轨迹，绝大多数曲线在1至2轮内降至零；图4为按建议聚合的消除率，全部达到100%，显著高于80%的预期目标。值得注意的是，消除率的全样本一致并非任务平凡所致：本项目早期版本的反馈仅回传规则名与描述，17板预实验中14条多轮用例有10条未收敛、违规数逐轮不动；补全修法指引与撤销语义后，全量实验收敛率达94.2%，说明反馈信息的完整性而非模型能力是闭环可靠性的决定因素。"));
body.push(...fig("fig3_convergence.png", "图3　多轮用例的blocking违规数迭代收敛曲线（部分）", 520));
body.push(...fig("fig4_hallucination.png", "图4　blocking级新增违规消除率（目标80%）", 560));
body.push(p("时间开销如图5所示：安全检查类建议平均2.4s，危险类与优化类分别约24.9s与21.8s，闭环阶段整体平均19.2s每条建议；耗时主要由LLM生成与修正的调用延迟构成，单次DRC复检不足0.1s，迭代多轮带来的规则检查开销可忽略。对照纯LLM直出建议（单次调用约5至10s），闭环以约2至3倍的时延换取了blocking级违规的全量消除，处于可接受区间。"));
body.push(...fig("fig5_time.png", "图5　各实验阶段平均耗时对比", 440));
body.push(h2("4.4　多智能体审查"));
body.push(p("79个设计的多智能体审查平均综合评分94.2分（最低88.7、最高98.3），等级分布为A+级28个、A级51个。六维平均得分依次为：热管理99.6、信号完整性96.6、可制造性93.6、成本92.9、电磁兼容92.5、电源完整性89.9。电源维度得分最低，与DRC基线中去耦电容、PDN等电源类规则触发最频繁的观察相互印证，指示开源设计普遍存在去耦网络不完善问题。图6以立创·泰山派3M（RK3576）开发板为例给出六维雷达图：该板DRC基线75条违规（5条warning、70条info），综合评分92.3（A级），其中电磁兼容维度满分，成本维度（77.1）因器件种类多、替代性低而显著低于均值，体现了画像对具体设计的区分能力。"));
body.push(...fig("fig6_radar_taishanpi.png", "图6　立创·泰山派3M开发板多智能体六维评分雷达图", 400));
body.push(h2("4.5　程序化缺陷注入"));
body.push(p("规则引擎的独立检出能力通过280次缺陷注入评估，总体检出268次，检出率95.7%，分型结果见表4。非标电阻值与电容耐压不足检出率均为100%；移除去耦电容98.4%；删除TVS/ESD保护二极管89.8%；删除晶振负载电容84.0%，为最低项，其漏检发生于设计缺少网络关联数据的场景，此时相关规则按设计退化为提示级。个别类型样本量很小（如删除LED限流电阻仅1例），其检出率不具统计意义。"));
body.push(...threeLineTable(
  "表4　程序化缺陷注入检出结果",
  ["注入缺陷类型", "注入次数", "检出次数", "检出率"],
  [
    ["改为非标电阻值", "73", "73", "100.0%"],
    ["电容耐压不足", "61", "61", "100.0%"],
    ["移除去耦电容", "61", "60", "98.4%"],
    ["删除TVS/ESD保护二极管", "59", "53", "89.8%"],
    ["删除晶振负载电容", "25", "21", "84.0%"],
    ["删除LED限流电阻", "1", "0", "0.0%"],
    ["合计", "280", "268", "95.7%"],
  ],
  [40, 18, 18, 24],
));
body.push(h2("4.6　关键指标汇总与跨模型初步验证"));
body.push(p("表5汇总本文提出的量化指标体系及其目标值与实测值，各指标均达到或显著优于目标。跨模型方面，使用DeepSeek系列模型[15]的单设计冒烟实验（1个设计、5条建议）得到全部收敛、消除率100%、多智能体评分97的结果，初步表明闭环机制的有效性不依赖特定LLM；完整的跨模型对比实验留待后续工作。"));
body.push(...threeLineTable(
  "表5　关键指标与目标对比",
  ["指标", "目标值", "实测值"],
  [
    ["BOM变更建议收敛率", "> 70%", "94.2%（113/120）"],
    ["平均迭代轮次", "≤ 2.0", "1.14"],
    ["blocking级新增违规消除率", "> 80%", "100%"],
    ["多智能体平均综合评分", "> 75", "94.2"],
    ["程序化缺陷注入检出率", "——", "95.7%（268/280）"],
    ["DRC单板平均耗时", "毫秒级", "77.1 ms"],
  ],
  [44, 20, 36],
));
body.push(h2("4.7　案例分析"));
body.push(p("以典型危险建议为例：对01Phone设计注入移除全部去耦电容并以0.1mm走线承载3A电流的变更请求，LLM首轮生成的变更集包含22条BOM修改，复检引入10条blocking级新违规（去耦电容检查、电源线载流检查等）；修正反馈回传后，LLM于第2轮撤销全部载流相关变更并恢复去耦组合，新违规归零，收敛通过，全程45.0s。该案例完整呈现了危险建议从生成、拦截、反馈到撤销修正的全过程，也说明载流类违规由IPC-2221公式判定的确定性与即时性。"));

// 5 讨论
body.push(h1("5　讨论"));
body.push(p("实验结果支持三个判断。第一，确定性外部反馈是LLM在PCB域可靠收敛的充分条件：本引擎中blocking级新增违规全量消除、94.2%的变更建议收敛，与文献[6]关于外部反馈必要性的结论在PCB域形成呼应；其中修法指引与撤销语义两项反馈设计贡献最大，缺任一项时修正轮次即出现违规数停滞。第二，规则引擎与物理计算的分工有效：参数与语义类违规（非标值、耐压、去耦缺失）由规则覆盖，载流与阻抗类约束由标准公式兜底，两者互补构成完整验证面。第三，多智能体层与规则层观察相互印证（电源维度得分最低与电源类规则触发最多一致），表明其画像具备诊断价值而非泛化打分。"));
body.push(p("本研究仍存在四点局限。其一，闭环目前作用于BOM级变更，布局与布线级建议的闭环验证需要几何编辑与重检的更复杂管线；其二，部分规则依赖网络关联数据，缺数据时退化为提示级，晶振负载电容类缺陷的漏检即源于此，引入网表推断是明确的改进方向；其三，实验中41条建议因LLM输出解析失败而不计入通过率（非误放行），结构化输出约束可进一步压缩该比例；其四，全量实验基于单一LLM，跨模型对比仅完成冒烟验证，评分器为启发式加权，多智能体评分应理解为相对质量画像而非绝对基准。"));

// 6 结论
body.push(h1("6　结论"));
body.push(p("本文面向PCB设计中LLM建议的可信化问题，提出并实现了由LLM建议引擎、68条规则的DRC引擎、IPC-2221/2141确定性物理计算与五智能体协同审查构成的闭环验证引擎。在79个真实开源设计、395条建议的实验中，引擎实现BOM变更建议94.2%收敛、平均1.14轮迭代、blocking级新增违规100%消除、缺陷注入95.7%检出与多智能体均分94.2的综合表现。结果表明，以确定性规则引擎为外部反馈源的闭环架构能够在PCB设计域有效抑制LLM幻觉，使LLM得以安全地承担设计建议职责。后续工作将围绕网表关联推断、布局级闭环验证、跨模型全量对比与规则体系持续扩充展开，并探索将该闭环机制接入更多国产EDA工具生态。"));

// 参考文献
body.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 400, after: 200, line: 360 },
  children: [new TextRun({ text: "参考文献", bold: true, size: 30, font: F_HEI, color: BLACK })],
}));
[
  "[1] Chen L, Chen Y, Chu Z, et al. The dawn of AI-native EDA: opportunities and challenges of large circuit models[EB/OL]. (2024-03-11). https://arxiv.org/abs/2403.07257.",
  "[2] Liu M, Wang T, Zhang Q, et al. ChipNeMo: domain-adapted LLMs for chip design[EB/OL]. (2023-11-01). https://arxiv.org/abs/2311.00276.",
  "[3] He Z, Wu H, Li Z, et al. ChatEDA: a large language model powered autonomous agent for EDA[J]. IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, 2024, 43(11): 3970-3983.",
  "[4] Wu H, Zheng H, He Z, et al. Divergent thoughts toward one goal: LLM-based multi-agent collaboration system for electronic design automation[C]//Proceedings of the 2025 Conference of the North American Chapter of the Association for Computational Linguistics. Albuquerque: ACL, 2025.",
  "[5] Devlin J, Chang M W, Lee K, et al. BERT: pre-training of deep bidirectional transformers for language understanding[C]//Proceedings of NAACL-HLT 2019. Minneapolis: ACL, 2019: 4171-4186.",
  "[6] Huang J, Chen X, Mishra S, et al. Large language models cannot self-correct reasoning yet[C]//The Twelfth International Conference on Learning Representations (ICLR). Vienna, 2024.",
  "[7] Chen X, Lin M, Sch\u00e4rli N, et al. Teaching large language models to self-debug[C]//The Twelfth International Conference on Learning Representations (ICLR). Vienna, 2024.",
  "[8] Shinn N, Cassano F, Gopinath A, et al. Reflexion: language agents with verbal reinforcement learning[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 2023.",
  "[9] Yao S, Yu D, Zhao J, et al. Tree of thoughts: deliberate problem solving with large language models[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 2023.",
  "[10] Guo T, Chen X, Wang Y, et al. Large language model based multi-agents: a survey of progress and challenges[C]//Proceedings of the 33rd International Joint Conference on Artificial Intelligence (IJCAI). Jeju, 2024.",
  "[11] Yao S, Zhao J, Yu D, et al. ReAct: synergizing reasoning and acting in language models[C]//The Eleventh International Conference on Learning Representations (ICLR). Kigali, 2023.",
  "[12] IPC Association. IPC-2221B: generic standard on printed board design[S]. Bannockburn: IPC, 2012.",
  "[13] IPC Association. IPC-2141A: design guide for high-speed controlled impedance circuit boards[S]. Bannockburn: IPC, 2004.",
  "[14] Zeng A, Liu X, Du Z, et al. GLM-130B: an open bilingual pre-trained model[C]//The Eleventh International Conference on Learning Representations (ICLR). Kigali, 2023.",
  "[15] DeepSeek-AI. DeepSeek-V3 technical report[EB/OL]. (2024-12-26). https://arxiv.org/abs/2412.19437.",
  "[16] 立创EDA[EB/OL]. [2026-10-19]. https://pro.lceda.cn.",
].forEach(t => body.push(refEntry(t)));

// 收稿信息占位
body.push(new Paragraph({
  spacing: { before: 300, line: 300 },
  alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "【作者简介：姓名（出生年—），性别，籍贯，单位/学历方向；联系方式待补。】", size: 18, font: F_BODY, color: "555555" })],
}));

// ── 组装文档 ─────────────────────────────────────────────
const doc = new Document({
  creator: "TraceWise 论文流水线",
  title: "面向PCB设计的大语言模型闭环验证引擎",
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
          children: [new TextRun({ text: "面向PCB设计的大语言模型闭环验证引擎", size: 18, color: "333333", font: F_BODY })],
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
    children: [...titleBlock, ...body],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log("[OK] " + OUT + "  (" + (buf.length / 1024).toFixed(0) + " KB)");
});
