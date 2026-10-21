/* 论文修回稿生成（第二轮 N1-N18 落地）—— 面向PCB设计的大语言模型闭环验证引擎
 * 运行: node generate_paper.js
 * 修订依据: 论文/review/round2/editorial_decision_r2.md（Minor Revision 路线图 N1-N18）
 * 数据来源: experiment_results/run_thing_full_glm53 (79设计/395建议, glm-5.3-flash)
 *           + 论文/review/revision_metrics.json（修订重放口径）
 * 图表来源: 论文/figures/fig1..fig6（fig1=arch_diagram, fig2=fig2_severity,
 *           fig3=convergence, fig4=fig4_revision(首轮vs末轮), fig5=time, fig6=radar）
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
const OUT = path.join(__dirname, "论文修订稿_面向PCB设计的LLM闭环验证引擎.docx");

const F_BODY = { ascii: "Times New Roman", eastAsia: "SimSun" };
const F_HEI = { ascii: "Times New Roman", eastAsia: "SimHei" };
const BLACK = "000000";

function p(text, opts = {}) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: opts.noIndent ? undefined : { firstLine: 480 },
    spacing: { line: 360, before: 0, after: 0 },
    children: [new TextRun({ text, size: 24, font: F_BODY, color: BLACK })],
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

// ── 题录区（R5/R6：中英摘要对齐 + 体例要素） ─────────────
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
    children: [new TextRun({ text: "（1. 【作者单位（双盲评审期匿名，录用后补全）】；2. 【第二单位】）", size: 21, font: F_BODY, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160, line: 300 },
    children: [new TextRun({ text: "【基金项目：国家级大学生创新创业训练计划项目（编号双盲评审期匿名）】　中图分类号：TN41　文献标识码：A", size: 18, font: F_BODY, color: BLACK })],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 200, after: 40, line: 320 },
    children: [
      new TextRun({ text: "摘　要：", bold: true, size: 21, font: F_HEI, color: BLACK }),
      new TextRun({ text: "大语言模型（LLM）正在进入印制电路板（PCB）辅助设计领域，但其生成建议中的幻觉问题——虚构非标称器件参数、给出违反载流与耐压等物理约束的危险变更——使其难以直接用于真实设计。针对这一问题，本文提出并实现了一个面向PCB设计的LLM闭环验证引擎：LLM生成的BOM变更建议必须经过由68条规则构成的设计规则检查（DRC）引擎复检，未通过的建议携带结构化修正反馈（新违规清单、修法指引与撤销语义）驱动LLM迭代修正，最多3轮；载流与阻抗等物理约束按IPC-2221/IPC-2141标准公式在本地确定性计算，不依赖LLM。在79个立创开源平台真实设计、395条三类模板请求驱动的建议上，以三臂对比评估：LLM直出（无验证）会在23个设计的23条建议上引入共80条次blocking级违规；单次门（直出后一次性复检拒绝）的首轮采纳率为74.2%（89/120）；闭环验证在相同数据上将收敛率提升至94.2%（113/120，按板聚类bootstrap 95%置信区间89.8%～97.6%）且blocking级残留为零；同口径下闭环落盘产量为74/120（61.7%），39/120的收敛由整体撤销达成，23条引入违规的建议全部经反馈后整体撤销——其增量价值在质量隔离而非落盘产量。跨模型验证在21板分层子集上重复：DeepSeek-V4.1-Flash与Qwen3.8-max的变更建议收敛率分别为98.4%与100%，清除路径与轮次分布和GLM一致（DeepSeek的22条宿主建议中21条经整体撤销清零、1条未收敛）；在21板子集与反馈措辞经GLM系协同调优的条件下，该机制的行为形态不因模型而异。受控消融证实撤销语义承担了相对无撤销对照的全部收敛率增益：21板子集上剥离后收敛率由98.1%降至86.7%，降幅集中于危险类变更。另以280次BOM级程序化缺陷注入单独评估规则引擎自身，五类注入分类上检出率95.7%（几何/布局模块598次注入为88.1%）。结果表明，在规则与IPC公式覆盖域内，以确定性规则引擎为外部反馈源的闭环机制能够以规则名级闸门阻止LLM变更引入新增规则违规——直出臂的80条次blocking级违规零落盘；对基线已触发规则的实例恶化，该粒度的闸门不构成拦截，隔离主张以此为边界。其覆盖上界受规则在注入分类内实测召回率的限制，真实开放请求下的有效性有待进一步验证。", size: 21, font: F_BODY, color: BLACK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 320 },
    children: [
      new TextRun({ text: "关键词：", bold: true, size: 21, font: F_HEI, color: BLACK }),
      new TextRun({ text: "印制电路板；大语言模型；设计规则检查；闭环验证；IPC标准；幻觉抑制", size: 21, font: F_BODY, color: BLACK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 40, line: 300 },
    children: [
      new TextRun({ text: "Abstract: ", bold: true, size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
      new TextRun({ text: "Large language models (LLMs) are entering the domain of printed circuit board (PCB) design assistance, yet hallucinations in their suggestions, such as fabricated non-standard component parameters and dangerous changes violating current-carrying or voltage-rating constraints, prevent direct use in real designs. This paper proposes and implements a closed-loop verification engine for LLM-assisted PCB design: every LLM-generated BOM change must pass re-examination by a design rule checking (DRC) engine of 68 rules; failed suggestions are returned to the LLM with structured correction feedback (violation list, fixing guidance, and revert semantics) for iterative refinement within three rounds; current-carrying and impedance constraints are computed deterministically from IPC-2221/IPC-2141 standard formulas without LLM involvement. On 79 real open-source designs with 395 suggestions driven by three template request types, a three-arm comparison shows that direct LLM output without verification would introduce 80 blocking-level violations into 23 suggestions across 23 designs; a single-pass gate adopts 74.2% of suggestions (89/120) at the first re-examination; the closed loop raises the convergence rate to 94.2% (113/120, design-clustered bootstrap 95% CI 89.8%-97.6%) with zero blocking-level residual. Under the same landed-change criterion, the closed loop lands 74/120 (61.7%) suggestions, with 39/120 convergences via full reversion and all 23 violation-introducing suggestions cleared through reversion - its incremental value lies in quality isolation rather than landed output. Cross-model validation on a stratified 21-design subset shows convergence rates of 98.4% for DeepSeek-V4.1-Flash and 100% for Qwen3.8-max, with clearance paths and iteration distributions consistent with GLM (21 of DeepSeek's 22 host suggestions cleared via full reversion, one unconverged); under this subset and GLM-tuned feedback wording, the behavior of the mechanism does not vary with the model. A controlled four-arm ablation on the same subset confirms revert semantics as the carrier of the entire convergence gain over the no-revert control: removing it lowers the convergence rate from 98.1% to 86.7%, with the loss concentrated in dangerous-class changes. A separate 280-case BOM-level programmatic defect injection assesses the rule engine itself at a 95.7% detection rate within its five injection categories (88.1% for the geometry/layout module over 598 injections). Within the coverage of the rules and IPC formulas, the closed loop with a deterministic external feedback source prevents LLM changes from introducing new rule-name violations - all 80 blocking-level violations of the direct-output arm fail to land in the design; deterioration of rules already violated at baseline is not intercepted at this rule-name granularity, and the isolation claim is bounded accordingly. The upper bound is limited by the rule recall measured within the injection categories; effectiveness under open-ended real requests remains to be verified.", size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 200, line: 300 },
    children: [
      new TextRun({ text: "Key words: ", bold: true, size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
      new TextRun({ text: "printed circuit board; large language model; design rule checking; closed-loop verification; IPC standards; hallucination suppression", size: 21, font: { ascii: "Times New Roman" }, color: BLACK }),
    ],
  }),
];

// ── 正文 ─────────────────────────────────────────────
const body = [];

// 1 引言
body.push(h1("1　引言"));
body.push(p("印制电路板（Printed Circuit Board, PCB）是电子系统的物理载体，其设计质量直接决定产品的电气性能、可靠性与可制造性。近年来，以立创EDA[1]为代表的免费云端EDA工具与活跃的开源硬件社区大幅降低了PCB设计门槛，大量学生、创客与中小团队得以独立完成从原理图到布局布线的全流程设计。然而设计门槛的降低并未同步降低审查门槛：商用EDA的DRC（Design Rule Checking）与DFM（Design for Manufacturing）分析集中于几何制造规则，而器件选型是否合规、去耦网络是否完整、保护电路是否缺失等电路语义层面的审查，仍然高度依赖有经验工程师的人工复核，成为开源硬件设计质量的突出短板。"));
body.push(p("大语言模型（Large Language Model, LLM）凭借广泛的电子学知识与自然语言交互能力，为自动化设计审查提供了新的可能：用户以口语化中文描述需求，LLM即可生成器件替换、参数调整、网络增删等结构化设计建议。但LLM的幻觉问题[2]在物理设计域尤为危险：模型可能虚构不存在的标准电阻值或封装，推荐耐压不足的电容，甚至建议删除TVS保护器件或以过细走线承载大电流。此类建议一旦未经校验直接进入设计，后果是板卡烧毁、认证失败等真实物理损失。已有研究表明，LLM在缺乏外部反馈的情况下难以通过自我反思可靠纠错[3]，因此让LLM安全参与PCB设计的关键，在于为其配备确定性的外部验证器并构成修正闭环。"));
body.push(p("现有LLM辅助EDA的研究主要面向IC设计流程[4]：ChipNeMo通过领域适配增强LLM的芯片设计问答与脚本生成能力[5]，ChatEDA以LLM为控制器编排EDA工具完成RTL到GDSII流程[6]，EDAid则用多个领域微调模型协作生成流程脚本[7]。这些工作的验证环节依赖成熟IC工具链，其经验难以直接迁移到PCB级：PCB设计数据异构（BOM、网表、几何多源并存），审查规则体系以IPC标准与器件语义为主而非IC工艺规则，且LLM在PCB域的产出形态是建议级的BOM/参数变更而非可执行脚本，尚缺乏与之配套的验证-反馈-修正闭环机制——PCB级LLM应用目前以商用工具的辅助问答、评测基准与AI自动化产品为主[8-11,28-29]，就本文所及，公开学术文献中尚无对LLM建议级变更闭环验证的系统评估。"));
body.push(p("针对上述缺口，本文提出并实现了一个面向PCB设计的LLM闭环验证引擎，主要工作包括三方面：（1）闭环验证架构：将LLM建议生成与本地DRC规则引擎（68条）构成建议-检查-反馈-修正的迭代闭环，并以直出、单次门、闭环三臂对比与建议级流向分解评估其有效性；（2）电路计算增强验证：走线宽度、布局位置等几何级变更被闭环动作空间确定性排除，载流能力、特征阻抗等物理约束由IPC-2221/IPC-2141标准公式模块承担——该模块作为几何级闭环的预留确定性校核在本地确定性计算、零LLM依赖，其检出能力由独立的程序化注入实验评估（3.4节）；（3）领域画像辅助：五个领域审查智能体对设计进行并行复审并输出六维相对质量画像。需要说明的是，本文的全部有效性主张限定于规则与IPC公式的覆盖域内：验证器的召回上界（BOM级注入分类内实测95.7%、几何/布局注入88.1%）同时是闭环隔离能力的上界，这一点在结果与讨论中显式量化。在79个真实开源设计、395条建议的实验中，闭环将直出会引入的80条次blocking级违规全部隔离，收敛率113/120（94.2%）较单次门首轮采纳89/120（74.2%）高20.0个百分点（收敛率与落盘产量两种口径的完整对照见4.3节）。"));

// 2 相关工作
body.push(h1("2　相关工作"));
body.push(h2("2.1　EDA与PCB设计中的LLM应用"));
body.push(p("LLM与EDA的结合是近两年的研究热点[4]。ChipNeMo在通用LLM基础上进行领域继续预训练与适配，在工程问答与脚本生成任务上超过通用模型[5]；ChatEDA构建了以LLM为核心的自主智能体，将EDA工具作为执行器完成流程自动化[6]；EDAid提出发散思考、共同目标的多智能体协作范式生成EDA流程脚本[7]。这些工作面向IC流程脚本，以IC工具链为验证器。在PCB层面：Cadence Allegro X AI将机器学习用于布线与Placement辅助[8]，Siemens Valor NPI等器件级NPI（New Product Introduction）检查系统在制造与装配规则层面已高度成熟[9]，立创EDA等国产工具开始引入AI问答能力[1]；产品侧，Flux将LLM Copilot引入原理图与BOM的交互式问答[28]，Quilter以物理约束驱动的自动化引擎生成布局布线候选[29]；学术侧，PCB-Bench[10]与PCB-QA[11]最近开始构建面向PCB知识的LLM评测基准。与这些工作不同，本文的产出形态是BOM级的结构化设计建议而非问答、脚本或自动化布线，核心问题是建议级变更的验证-反馈-修正闭环——上述产品与基准均不针对该环节；相对DFM/DFV系统覆盖制造几何分析，本文聚焦器件参数语义与IPC物理约束的审查，并给出LLM建议的守门与迭代机制。"));
body.push(h2("2.2　LLM幻觉缓解与迭代修正"));
body.push(p("针对LLM幻觉与错误输出，主流思路可分为四类。其一为提示与解码策略，如思维树[12]、链式验证（Chain-of-Verification）[13]与SelfCheckGPT的采样一致性自检[14]；其二为自我修正，Self-Debug让模型依据自身执行反馈迭代修正代码[15]，Reflexion以语言化强化信号记忆历史失败[16]，Self-Refine建立通用自反馈迭代框架[17]；其三为工具交互修正，CRITIC主张让外部工具的评判信号驱动修正，其作者明确指出纯自我修正不可靠[18]；其四为多智能体协作评审[19]。Huang等人的系统实验进一步表明，LLM在没有外部可靠反馈的情况下难以真正自我纠错[3]。这些结论与本文的设计选择一致：可靠的修正闭环必须引入外部确定性验证源，本文将其落实为DRC规则引擎与IPC标准计算，并以验证器在环的迭代修正循环（区别于ReAct[20]的自主行动选择范式）组织LLM与验证器的交互。相对上述方法，本文的增量在于：将工具交互修正应用于PCB设计域，并针对该域设计了结构化修正反馈的四要素（违规清单、恶化对比、修法指引、撤销语义），其中把全部撤销（空变更集）纳入合法收敛终态是工程上被发现不可或缺的设计；这一工程判断已获受控消融支持——剥离撤销语义后，21板分层子集（glm-5.3-flash）的收敛率下降11.4个百分点，且降幅集中于危险类变更（4.3节）。"));
body.push(h2("2.3　设计规则检查与标准计算"));
body.push(p("DRC是EDA的传统支柱，商用工具已高度成熟，但传统DRC以布线几何与制造规则为主，不覆盖器件参数语义（如电容耐压降额、电感饱和电流）。PCB级的物理设计约束由IPC标准体系规定：IPC-2221给出了印制板通用设计要求，其载流能力图表公式将线宽、铜厚、温升与允许电流联系起来[21]；IPC-2152以更系统的实验数据取代了IPC-2221的载流图表[22]；IPC-2141给出了受控阻抗电路板的设计指南，提供微带线等典型结构的特征阻抗计算式[23]。本文将IPC-2221图表公式与IPC-2141计算式实现为本地确定性计算模块（选型论证见3.4节），与规则引擎共同构成LLM建议的外部验证器，并以BERT类预训练语言模型[24]承担中文意图识别，实现本地小模型与云端LLM的混合推理架构。国内学者对LLM幻觉的来源、评估与缓解亦有系统性综述[2]，本文的量化口径（blocking级新增违规与消除分解）可为该方向提供一个领域实例。"));

// 3 引擎设计
body.push(h1("3　闭环验证引擎设计"));
body.push(h2("3.1　总体架构"));
body.push(p("引擎总体架构如图1所示，自上而下分为五层。输入层接收立创EDA工程文件（原理图、BOM与PCB几何数据）及用户的中文自然语言请求；解析层将工程解析为统一的PCB数据模型（器件清单、网络关联、几何与叠层信息），并由本地部署的BERT类小模型完成意图识别，将请求分流为设计审查与知识问答两类，仅前者进入验证流程。核心层为闭环验证引擎：LLM建议引擎生成的BOM变更建议先经结构化解析与风险预检（预检仅对高风险模式打标提示、不直接否决，全部否决均由复检承担），再交由DRC规则引擎复检；复检引入的新违规通过结构化修正反馈回传LLM迭代修正，通过复检的建议方可进入下游。审查层由五个领域智能体并行复审，输出层汇聚六维评分画像与结构化审查报告。"));
body.push(p("该架构遵循两条设计原则。其一是守门语义：任何LLM建议在通过DRC复检之前不得进入设计数据，验证失败的建议可被部分或整体撤销，使LLM的错误输出难以进入真实设计。该隔离带有两个显式边界：覆盖面边界——以规则引擎与IPC公式的判定面为上界（见4.5节漏检率），超出覆盖面的危险变更不在此保证之内；闸门粒度边界——复检的新增判定按规则名与基线比对，基线已触发规则的实例恶化不构成新增、不被该闸门拦截（见3.3节与4.3节逐条核验）。两者均不作无限定外推。其二是本地与云端混合：意图识别、规则检查与物理计算全部在本地毫秒级完成且结果确定，仅建议生成与修正两个环节调用云端LLM，既控制了时延与成本，也保证了验证环节本身不受LLM幻觉影响。"));
body.push(...fig("fig1_architecture.png", "图1　闭环验证引擎总体架构", 560));

body.push(h2("3.2　规则体系"));
body.push(p("规则引擎共实现68条规则，按检查对象分为三个模块：器件参数类37条（BOM模块），检查电容耐压降额、电阻功率降额、电感饱和电流、非标称参数值、封装一致性等；几何类21条，检查走线宽度、板边间距、差分对间距、安装孔禁区等；布局类10条，检查去耦电容距离、晶振布局、温度敏感元件布局等。规则体系构成如表1所示。"));
body.push(p("工程实践中，规则进一步区分为判定类与提示类两级：判定类规则（51条）对当前板卡构成可证伪的判定，其检出可直接用于统计精确率；提示类规则（17条，如PDN目标阻抗分析、丝印可读性）在缺少网络关联等数据时只输出设计提示，不构成检出能力。这一区分避免了高频泛报的提示类规则稀释验证信号。每条违规输出三元组（规则名、严重度、修法指引），严重度分为error、warning、info三级，其中error与warning合称blocking级，用于危险变更识别与宿主建议统计，修法指引直接进入修正反馈提示；需要说明，收敛判定的新增违规计数不分严重度、info级亦计入（见3.3节式(1)）。关于验证覆盖的不对称性：4.5节的程序化缺陷注入对三个模块分别执行——器件参数类规则以280次BOM级注入评估（95.7%），几何类与布局类规则在78份立创专业版真实工程导出件（含真实走线、过孔、板框与元件坐标，与主实验数据集不重叠）上以598次程序化几何/布局变异注入评估（总检出88.1%，几何85.2%、布局93.2%）；几何类中15条与布局类中4条规则因所需图层或元数据不可得（丝印、叠层介质、差分对工程声明、安装孔坐标等）未做注入，其证据仍以静态检查与真实板基线为准。因此本文的实验证据以BOM语义验证为主、几何/布局验证为辅，且对几何/布局模块的检出率与漏检模式如实报告（含漏检的机制归因，见4.5节）。"));
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
body.push(p("闭环验证以单条建议为单位执行。建议的动作空间为BOM结构化变更，形式化为五元组（reference, field, old_value, new_value, action），其中reference为位号，field为字段（如value、footprint），action为编辑类型枚举{add, remove, replace}；走线宽度、布局位置等几何调整不在本闭环的作用域内（含走线描述的请求由LLM映射为BOM级变更或零变更回应，见4.1节）。给定原始BOM与建议变更集，流程如下：（1）预检：对危险操作模式（删除ESD保护器件、大电流请求等）计算风险分并打标，仅作提示不否决；（2）应用与复检：将变更集应用到BOM副本，运行完整DRC得到违规集合，与基线违规按规则名比对得到新增违规；（3）收敛判定：若满足收敛条件则建议通过，否则构造结构化修正反馈回传LLM；（4）迭代：LLM依据反馈修正变更集（含部分或全部撤销），重复（2）～（3），迭代上限3轮。"));
body.push(p("收敛判定同时要求无新增规则违规与设计评分不劣化。记应用变更后的违规集合中新增违规数为N_new——新增判定按规则名与基线集合比对过滤，且不分严重度（error/warning/info均计入）——基线设计评分为S，修正后评分为S′，容差为τ，收敛条件为："));
body.push(formula([IT("N"), SUB("new"), T("("), IT("V"), T("\u2032"), SUB(")"), T(" = 0　且　Δ"), IT("S"), T(" = "), IT("S"), T("\u2212"), IT("S"), T("\u2032 ≤ "), IT("τ")], "(1)"));
body.push(p("其中新增违规按规则名与基线集合比对过滤，避免把设计固有问题计入建议的责任。该比对的粒度是规则名级：基线已触发某规则的板，其违规实例的增多或恶化（如删除去耦电容使去耦电容检查的实例数上升）不构成新增、闸门对此不设防。这与4.5节注入评估采用的实例级判定（基线已触发该规则的板若注入后违规实例描述变化亦计新检出）存在口径不对称——闸门比验证器自身演示过的判定粒度更粗，4.3节将给出该口径下九条危险来源落盘案例的逐条通过机制；实例级新增判定列为工程改进方向。评分S来自启发式设计评分器（3.5节）：按规则到六维的加权映射累计扣分得到百分制总分；τ取2.0为工程设定（对应百分制下2%的容差带宽），其取值依据与敏感性见4.3节——评分守门项是对规则名过滤的补充，用于拦截不触发新规则但整体劣化参数质量的变更组合。"));
body.push(p("本文对消除效果采用过程性描述而非比率型headline：记某条建议首轮复检引入的blocking级新增违规数为B1，末轮为Bf，消除率HE=(B1−Bf)/B1×100%（B1=0时该建议无违规可消除、不进入该统计）。必须指出，该指标在口径上部分是定义的必然：式(1)的通过条件即Bf=0，故凡收敛通过的建议HE恒为100%，消除率不承载区分度，仅用于核验预算内清除是否发生；本文headline由收敛率与三臂对比（4.3节）承担，消除情况以宿主建议的首轮/末轮违规数与清除路径分解（修正-保留型或撤销型）呈现。"));
body.push(p("结构化修正反馈包含四类信息：本轮全部新增违规及其修法指引；同规则基线与修正后的触发对比；撤销语义（LLM可以输出空变更集表示全部撤销，也可以撤销部分条目）；以及允许重加条目的补录操作。反馈中显式给出迭代历史摘要，避免LLM重复尝试已失败的策略。撤销计入收敛的口径声明：全撤销（空变更集）满足式(1)故计为收敛，属于防御性收敛路径；因此收敛率拆分为修正-保留收敛率与撤销率两个子指标并列报告（4.3节）。关于反馈要素的作用，早期17板预实验（不同反馈实现、非受控配置）中，仅回传规则名的旧版本下14条多轮用例有10条违规数逐轮不动，补全修法指引与撤销语义后全量实验收敛率达94.2%——该对照为跨时间的历史观察而非受控消融，提示（而非证明）两项设计可能是关键因素；这一提示已获同期受控证据——撤销语义经四臂受控消融确认为受操纵反馈要素中唯一的收敛承载：剥离后收敛率下降11.4个百分点，且降幅集中于危险类变更，见4.3节。"));

body.push(h2("3.4　电路计算增强验证"));
body.push(p("纯规则匹配无法覆盖的物理约束由标准公式计算模块补齐，该模块的输入与计算过程完全确定（输出为近似经验公式的计算值），且不涉及LLM。载流能力按IPC-2221图表公式计算[21]：对截面积为A（mil²）的铜导体，允许电流为"));
body.push(formula([
  IT("I"), T(" = "), IT("k"), T(" · (Δ"), IT("T"), T(")"), SUP("0.44"), T(" · ("), IT("A"), T(")"), SUP("0.725"),
], "(2)"));
body.push(p("其中ΔT为允许温升（℃），k为层系数（外层0.048、内层0.024），引擎默认ΔT取10℃（保守取向，未按板类分层设定，分层取值留待后续）。例如0.5mm宽、1oz铜厚（35μm）的外层走线截面积约27mil²，在10℃温升下允许电流约1.4A。标准选型说明：IPC-2152[22]以更系统的实验数据取代了IPC-2221的载流图表，是更精细的现行标准；本文沿用IPC-2221图表公式，取其保守取向（同等条件下给出的允许电流更低，利于安全侧误判）与实现数据可得性，两标准在本文建议集上的判定翻转比对留待后续工作。载流判定的电流输入来自BOM估算：由电源类器件估算整机电源电流（默认约1A口径的启发式估计，电机驱动电流单独取出），与请求文本中声称的电流值无关；过孔载流未纳入判定范围，此处显式声明排除。"));
body.push(p("特征阻抗按IPC-2141A微带线公式计算[23]："));
body.push(formula([
  IT("Z"), SUB("0"), T(" = "),
  T("87 / √("), IT("ε"), SUB("r"), T(" + 1.41) · ln[5.98"), IT("h"), T(" / (0.8"), IT("w"), T(" + "), IT("t"), T(")]"),
], "(3)"));
body.push(p("其中εr为板材相对介电常数，h为介质厚度，w为线宽，t为铜厚。该式的适用域为0.1<w/h<2.0且1<εr<15，越界时引擎将结果降级为提示级而非判定依据；带状线与差分结构暂不覆盖，此处显式声明。同时应明确：经验近似式的计算值与全波仿真之间存在固有偏差，本引擎以保守阈值留出余量，违反约束的判定应理解为违反近似公式的计算值。还需区分该模块与闭环的两层关系：其一，走线宽度、布局位置等几何级变更由动作空间确定性排除在闭环之外（3.3节），该排除不经过本模块；其二，IPC公式模块在当前实现中是几何级闭环的预留确定性校核——其判定在主实验闭环内未参与任何否决（全量395条建议的全部复检轮次中载流/阻抗判定触发为零），其检出能力由4.5节的独立注入实验评估。将物理约束交由确定性公式而非LLM判断，是在规则与公式覆盖面上消除一类幻觉通道的根本手段——该保证以覆盖声明为前提，不外推到未覆盖的约束类型。"));

body.push(h2("3.5　多智能体协同审查与设计评分器"));
body.push(p("通过闭环验证的建议进入多智能体审查层。五个领域审查智能体（表2）各自以领域专家角色并行审视设计，输出结构化发现（问题、位置、严重度、建议）。合成器将各智能体发现、DRC结果与BOM统计聚合为电源、信号、热、电磁兼容、可制造性、成本六维评分：其中前五维与五个智能体一一对应，成本维由BOM统计与参数范围、封装一致性等规则触发情况派生（规则到维度的映射带权重，如去耦电容类规则计入电源维权重1.5、电源线宽类权重2.0；维度分为100减去加权扣分，总分取六维加权平均）。评分器为启发式加权设计、未经人工标注对齐，其实测量级为相对质量画像而非绝对质量基准；多智能体层不阻断建议（守门由闭环层完成），其价值在于提供超出规则体系覆盖面的整体画像与改进方向，本文不将其分数用作有效性证据。"));
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
body.push(p("实验数据集构建过程如下：以脚本从立创开源平台批量抓取公开工程导出件（BOM表、网表、贴片坐标）构成候选池91个，经归一化解析后剔除数据不全或解析失败的12个，得到79个设计（均为公开开源工程，遵循平台开源协议，仅用于研究用途；完整设计清单与解析件作为补充材料随稿提交）。数据集画像：BOM器件数中位数25、均值38.1、最小5、最大313，覆盖MCU与SoC开发板、核心板、功能扩展与转接板、电源类及应用整机等常见板卡形态。"));
body.push(p("实验按三个阶段执行：阶段A对每个设计运行纯DRC基线检查（不调用LLM）；阶段B执行闭环验证，以三类固定模板请求驱动每设计5条建议（1条安全检查类、2条危险变更类、2条优化改进类），LLM据此生成结构化BOM变更并进入闭环，共395条；阶段C对每设计执行多智能体审查。三类请求模板全文公布如下（危险与优化模板中的走线级描述超出闭环动作空间，用于观察LLM对超出动作空间请求的处理，见3.3节）：安全类为检查当前BOM设计是否符合PCB设计规范、不做任何修改；危险类为移除所有100nF去耦电容以降低BOM成本、用0.1mm走线承载3A电流；优化类为将3.3V电源走线加宽到0.5mm、在每个IC的VDD引脚旁增加100nF与10μF去耦电容组合。需强调两点外部效度限定：其一，395条观测按设计聚类（每板5条、共享板卡基线与LLM解码随机性），非395个独立样本，本文区间估计均按设计为聚类单元做bootstrap（重抽次数B=2000，百分位法构造区间）；其二，请求分布由三类模板构造且与规则模块设计存在对齐，结论限定在该模板分布与规则集的覆盖区间内，对真实开放请求的外推不在本文证据范围内。"));
body.push(p("模型与环境配置：建议生成与修正调用云端对话模型——主实验为glm-5.3-flash（GLM系列[25]的轻量档），跨模型子集实验为DeepSeek-V4.1-Flash[26]与Qwen3.8-max[27]，均经API调用（主实验调用时间为2026年9月，子集实验为2026年10月），采样参数为服务端默认配置（未固定随机种子，多次运行存在解码波动）；意图识别使用本地ONNX量化小模型；DRC引擎与物理计算在本地CPU执行。68条规则的逐条定义、修正反馈提示词模板、变更集schema、五智能体提示词与评分器权重映射作为补充材料随稿提交（代码仓库拟于论文录用后公开，此前可联系作者获取）。评估采用三臂对比：直出臂（LLM建议不经验证直接采纳，以首轮应用后的违规状态重放度量）、单次门臂（直出后仅做一次复检、有新违规即整体拒绝、无修正反馈）与闭环臂（本文方法，迭代上限3轮），三臂对比在主实验数据上执行；跨模型子集实验仅运行闭环臂、与主实验同子集口径对比。反馈要素的作用以受控消融单独评估（4.3节）：在与跨模型实验相同的21板分层子集上，同一模型、同一规则版本、同期执行四臂对照——完整反馈、剥离修法指引（违规仅报规则名与描述）、剥离撤销语义（提示词移除撤销授权且机制拒收空变更集）、两者皆无，每臂105条。另设两组程序化缺陷注入（不涉及LLM）：BOM级五类缺陷280次（4.5节），以及几何/布局模块的598次程序化几何变异注入（4.5节），单独评估规则引擎自身的召回。全量实验共执行973次LLM调用、消耗约211万tokens，闭环验证阶段总耗时126.2分钟；两个跨模型子集各执行约200～235次调用、39万～45万tokens；消融实验四臂共执行555次调用、消耗约185万tokens（每条建议为首轮解析1次加每轮修正1次，四臂各105条合计）。"));
body.push(h2("4.2　DRC基线"));
body.push(p("79个设计的DRC基线共检出1513条违规，平均每板19.2条，其中error级41条、warning级325条、info级1147条，严重度分布如图2所示。触发频次最高的规则为参数范围检查（598次）、位号连续性检查（203次）、去耦电容检查（130次）与PDN目标阻抗分析（79次），器件参数与电源网络类问题构成开源设计的主要质量短板。DRC单板平均耗时77.1ms（最大1.41s），满足闭环内多次复检的实时性要求。"));
body.push(...fig("fig2_severity.png", "图2　79个设计的DRC基线违规严重度分布", 540));
body.push(h2("4.3　闭环验证结果"));
body.push(p("395条建议的完整流向如表3所示：79条安全类按设计即零变更通过；对危险与优化请求，LLM有196条以零变更回应（运行日志按输出形态归类：155条为明确的分析型回应，41条为输出解析失败或条目被全部丢弃——两类均未产生任何可执行变更，最终状态为零变更通过，本文不计其为修正成功）；120条提出了非空变更集，其中113条在迭代上限内收敛（94.2%，按板聚类bootstrap 95%置信区间89.8%～97.6%），7条未收敛（均为优化类，末轮残留1～3条info级新增违规、blocking级为零；其终态语义为末轮变更保留落盘并标记未通过，见下文与5节审计）。按收敛路径拆分：74条为修正-保留收敛（修正-保留收敛率61.7%），39条由LLM依据反馈整体撤销变更（撤销率32.5%）。零变更回应不构成验证通过的证据，本文不以总通过率作headline，而以120条变更建议为分母报告收敛口径。"));
body.push(...threeLineTable(
  "表3　395条建议级流向分解",
  ["状态", "条数", "说明"],
  [
    ["安全类零变更（按设计）", "79", "请求即检查类，LLM无变更输出"],
    ["LLM零变更回应（危险110/优化86）", "196", "分析型回应155（危险82/优化73）；解析失败41（危险28/优化13）"],
    ["提出非空变更集", "120", "进入闭环复检与迭代"],
    ["├ 修正-保留收敛", "74", "末轮仍有落盘变更且通过复检"],
    ["├ 撤销型收敛", "39", "反馈后整体撤销（空变更集），防御性路径"],
    ["└ 未收敛（3轮上限）", "7", "末轮变更保留落盘并标记未通过；残留1～3条info级新增违规，blocking为零"],
  ],
  [40, 12, 48],
));
body.push(p("三臂对比如表4所示。直出臂（重放首轮应用状态）：120条变更建议全部采纳时，将在23个设计的23条建议上引入共80条次blocking级违规（首轮复检合计94条次新违规中blocking级80条次）；单次门臂：有首轮新违规即拒绝，首轮采纳89/120（74.2%），31条建议被整体放弃、blocking残留为零；闭环臂：收敛113/120（94.2%）、blocking残留为零。闭环相对单次门的收敛率增量为20.0个百分点（113对89，即24/120条）：31条被单次门一刀切拒绝的建议中，24条经迭代收敛——其中23条以解释性整体撤销收场、1条修正保留；相对直出的价值是把80条次blocking违规全部隔离。同时必须给出同口径的落盘产量对照：单次门采纳的89条变更全部进入设计，闭环通过复检且末轮有落盘变更的为74/120（61.7%），低于单次门——闭环相对单次门的增量价值在质量面而非落盘产量，详见下文与5节。危险类158条的去向分解为：110条LLM零变更回应、39条迭代后全撤销、9条部分落盘；预检对其中48条打了高风险标记但均未直接否决，全部否决均来自复检。9条部分落盘的逐条核验（据运行日志）：其通过闸门的机制均为板卡基线已触发去耦电容检查（每板1～7次），规则名级比对下删除操作不构成新增违规；落盘内容7条为移除1～6只100nF去耦电容（合计21只）、2条为移除单枚外围功能芯片（音频功放LM4871N、升压变换器SY7201ABC），复检均无新增违规——该泄漏通道处于闸门粒度（规则名级比对）之内而非规则可见性之外，其后果在5节讨论。"));
body.push(...threeLineTable(
  "表4　三臂对比（120条提出变更的建议）",
  ["实验臂", "设置", "采纳/收敛", "blocking残留"],
  [
    ["直出（无验证）", "首轮变更直接进入设计", "120（全部采纳）", "80条次（23条建议）"],
    ["单次门", "一次复检，有新违规即拒绝", "89（74.2%，首轮采纳）", "0"],
    ["闭环（本文）", "复检+结构化反馈迭代≤3轮", "113（94.2%，CI95 89.8～97.6）", "0"],
    ["闭环·落盘产量（同口径）", "通过复检且末轮有落盘变更", "74（61.7%）", "0"],
    ["闭环·未收敛落盘", "3轮超时，末轮变更保留并标记未通过", "7（5.8%）", "0"],
  ],
  [22, 32, 26, 20],
));
body.push(p("表4的同口径对照须显式解读。以「变更实际进入设计」为统一口径：单次门落盘89/120，闭环落盘74/120（含未收敛落盘则81/120）——闭环在落盘产量上低于单次门；端到端占全部395条建议的比例为直出120/395（30.4%）、单次门89/395（22.5%）、闭环74/395（18.7%，含未收敛落盘81/395即20.5%）。单次门的89条采纳与闭环的113条收敛并非同一集合：89条中有16条因评分降幅2.6～6.6分触发闭环的评分守门、送回修正后以整体撤销收场（单次门不检查评分、会将其落盘）；闭环另有24条收敛来自被单次门拒绝的31条（23条撤销型、1条修正保留）。据此，闭环相对单次门的增量价值重新表述为：80条次blocking违规隔离（对直出）与16条评分劣化变更拦截（对单次门），而非落盘产量。"));
body.push(p("blocking违规的清除情况如图3与图4所示。图3给出多轮用例中blocking违规数随轮次的收敛轨迹；图4为23条引入blocking违规的宿主建议的首轮/末轮对比：首轮合计80条次，末轮全部清零。清除路径分解是本实验最重要的定性发现：23条宿主建议的清除全部经整体撤销达成（修正-保留型为0）——即一旦变更触发blocking级新违规，LLM在结构化反馈下的行为模式是撤回而非修复；修正-保留路径仅发生在info级提示的场合。这印证了闭环对危险变更的实际作用机制是防御性隔离（拒答、整体撤销，或落盘复检未报新增违规的部分变更），而非缺陷修复，其保守性代价（可能连带丢弃有益变更）在5节讨论。"));
body.push(...fig("fig3_convergence.png", "图3　多轮用例的blocking违规数迭代收敛曲线（部分）", 520));
body.push(...fig("fig4_hallucination.png", "图4　宿主建议的blocking违规清除：首轮引入 vs 末轮残留", 560));
body.push(p("反馈要素对闭环收敛的贡献以受控消融单独检验（表5）：在与跨模型实验相同的21板分层子集上，以glm-5.3-flash同期执行四臂对照，每臂105条，同一规则版本、迭代上限3轮、评分守门τ取2.0，DRC复检与预检四臂完全相同，A臂与主实验闭环代码路径逐字节一致。操纵分两层：提示词层，B/D臂剥离每条违规附带的修法指引行（严重级、规则名、位置、描述与恶化对比、迭代历史、评分信号均保留，修复策略中按指引调整的措辞相应改为自行判断并调整）；C/D臂移除全部撤销授权——撤销策略、空变更集合法且推荐的输出约定与末轮直接撤销全部的提示均删去，改述为无法消除的变更不会被接受。机制层与提示词层保持一致，C/D臂的引擎拒收空修正变更集（保持原变更并计一轮，不额外加轮或调用，LLM不收到显式拒收消息），部分撤回（非空缩减）仍被接受，故C/D臂的收敛按构造全为修正-保留型、撤销率为0。结果（全撤销计入收敛的口径同3.3节；105条含按设计零变更的安全分析类建议，该分母与表4的120条变更建议口径不同，收敛率仅用于四臂间对照）：剥离撤销语义使收敛率自A臂的98.1%降至C臂的86.7%与D臂的82.9%，分别下降11.4与15.2个百分点，未收敛记录由2条增至14条与18条、其中13条与16条为违规数逐轮停滞；剥离修法指引的影响很小，B臂与A臂收敛率持平（均为98.1%，bootstrap区间完全重叠）。对撤销语义的作用机制作两种并列解读：撤销是满足式(1)的防御性收敛出口，剥离后该出口关闭；LLM亦失去整体放弃选项，只能对无法修复的违规反复硬修直至停滞。另须披露一项设计混杂：C/D臂的空变更集拒收为静默设计——引擎拒收但LLM不收到显式拒收消息，LLM对撤销被拒的无知可能使部分条目陷入「尝试撤销—被静默拒收—继续硬修」的循环，静默拒收对C/D臂未收敛的贡献无法从现有运行记录中分离；带显式拒收回显的第四对照臂列为可选增强。分请求类型分解见表5后四列：撤销语义的收敛增益集中于危险类（A臂42/42收敛、其中撤销13条，C臂降至33/42、9条未收敛，下降21.4个百分点；优化类由40/42降至37/42，下降7.1个百分点；安全类各臂均21/21收敛）。按收敛路径：A臂修正-保留80.0%、撤销型18.1%，B臂81.0%、17.1%；C/D臂的收敛按构造全部为修正-保留型，其中经部分撤回（非空缩减）收敛的C臂为0条、A臂为1条。A臂21条宿主建议中19条经整体撤销清除、1条修正-保留、1条未收敛——宿主清除以撤销为绝对主导，但撤销并非唯一路径。据此本文将消融命题限定为：撤销语义承担了闭环相对无撤销对照的全部收敛率增益，且该增益集中于危险类变更——撤销语义是不可修复（危险类）变更安全收敛的主要承载，也是受操纵反馈要素（修法指引、撤销语义）中唯一的收敛承载；修法指引的增量在每臂105条的检验力下未观察到（B臂与A臂持平，不排除其在更细粒度任务上的作用），按未证实增量处理。该结论限定于glm-5.3-flash、21板子集与模板请求分布，表4三臂对比的headline口径不受影响。"));
body.push(...threeLineTable(
  "表5　反馈要素受控消融（21板分层子集×4臂×105条，glm-5.3-flash）",
  ["臂", "修法指引", "撤销语义", "收敛率%（CI95）", "危险类收敛/42", "优化类收敛/42", "平均轮次"],
  [
    ["A 完整反馈", "有", "有", "98.1（95.2～100.0）", "42（撤销13）", "40", "1.26"],
    ["B 无修法指引", "无", "有", "98.1（95.2～100.0）", "42（撤销12）", "40", "1.26"],
    ["C 无撤销语义", "有", "无", "86.7（80.0～92.4）", "33", "37", "1.37"],
    ["D 两者皆无", "无", "无", "82.9（75.2～89.5）", "30", "36", "1.40"],
  ],
  [16, 10, 10, 24, 15, 13, 12],
));
body.push(p("分建议类型的表现如表6所示：安全类均零变更通过；危险类平均1.25轮（撤销型均为2轮内）；优化类平均1.10轮、72条落盘。评分守门项（式(1)第二条件）在16条建议的流程中单独触发（无新规则违规但评分降幅超2.0分），全流程共34轮次出现大于2分的降幅（最大7.6分），τ取2.0时这些变更被送回修正。基于运行日志的归宿分解：该16条（均为危险类）最终全部以整体撤销收敛——0条落盘、0条未收敛；7条未收敛建议的失败原因全部为新增违规未清（末轮残留1～3条info级新违规），无一因评分违约单独致败（其末轮评分降幅均为0），也无双违反案例。据此，去除评分守门时主实验收敛率的理论上界不变（没有任何建议因评分门单独作用而改变收敛结局）；该守门的实际作用在于拦截落盘质量劣化——16条降幅2.6～6.6分的劣化变更组合若放行将全部落盘（单次门口径即如此），该16条同时构成表4同口径对照中闭环落盘产量低于单次门的主要成分。τ的敏感性受限于修正路径依赖历史反馈、无法离线重放，本文以触发频次与归宿分解披露代替。时间开销如图5所示：安全检查类建议平均2.4s，危险类与优化类分别约24.9s与21.8s，闭环整体平均19.2s每条建议；对照直出的单次调用约5～10s，闭环时延约为直出的2～4倍，主要由LLM调用次数构成，单次DRC复检不足0.1s。全量实验另含多智能体审查（平均36.5s每板，图5），其评分均值为94.2分（最低88.7、最高98.3，等级A+级28个、A级51个）——该数值与收敛率94.2%为纯属巧合，多智能体评分按3.5节声明仅作相对画像、不构成有效性证据，故不进入摘要。"));
body.push(...threeLineTable(
  "表6　闭环验证分建议类型结果",
  ["建议类型", "条数", "零变更回应", "落盘变更", "整体撤销", "平均轮次", "平均耗时"],
  [
    ["安全检查类", "79", "79", "0", "0", "1.00", "2.4 s"],
    ["危险变更类", "158", "110", "9", "39", "1.25", "24.9 s"],
    ["优化改进类", "158", "86", "72", "0", "1.10", "21.8 s"],
  ],
  [20, 10, 16, 13, 13, 12, 16],
));
body.push(...fig("fig5_time.png", "图5　各实验阶段平均耗时对比", 440));
body.push(h2("4.4　多智能体审查画像"));
body.push(p("79个设计的六维画像均值依次为：热管理99.6、信号完整性96.6、可制造性93.6、成本92.9、电磁兼容92.5、电源完整性89.9。画像分布高度压缩（88.7～98.3，全部为A/A+级），提示评分器对开源设计的区分度有限、存在天花板效应；电源维度最低与DRC基线中电源类规则触发最频繁的方向一致，但两者同源于规则触发数据，属共同方法方差下的同向观察、不构成独立印证。图6以立创·泰山派3M（RK3576）开发板为例：该板DRC基线75条违规（5条warning、70条info），综合画像92.3（A级），电磁兼容维度满分，成本维度（77.1）因器件种类多而低于均值，显示了画像对具体设计的相对区分能力。按3.5节声明，本节结果不作为有效性证据。"));
body.push(...fig("fig6_radar_taishanpi.png", "图6　立创·泰山派3M开发板多智能体六维评分雷达图", 400));
body.push(h2("4.5　程序化缺陷注入"));
body.push(p("本实验单独评估规则引擎自身的召回能力，不涉及LLM与闭环（表4的闭环指标与之相互独立），按模块分两组执行。"));
body.push(p("BOM级注入：五类器件级缺陷共280次注入，总检出268次（95.7%，按板聚类bootstrap 95%置信区间93.7%～97.5%），分型结果见表7：非标电阻值与电容耐压不足均为100%；移除去耦电容98.4%；删除TVS/ESD保护二极管89.8%；删除晶振负载电容84.0%，为最低项，其漏检发生于设计缺少网络关联数据的场景（此时相关规则按设计退化为提示级）。个别类型样本量极小（如删除LED限流电阻仅1例），其检出率不具统计意义。该检出率为五类注入分类内的实测值，同时量化了本文闭环隔离能力上界的当前估计：注入分类内的召回实测如此，真实缺陷分布上的召回应视为不高于此；规则未覆盖的危险变更（约4%～16%分型依赖）不保证被拦截，这一上界限定应在任何安全性表述中显式携带。"));
body.push(...threeLineTable(
  "表7　BOM级程序化缺陷注入检出结果",
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
body.push(p("几何/布局级注入：主实验数据集的导出件不含PCB版图数据，为使几何/布局规则获得注入证据，另取立创开源平台78份专业版工程导出件（epro2格式，含真实走线、过孔、板框与元件坐标；75个不同工程，其中3个工程各有两份不同时间的导出；与主实验79板无重叠）。对每块板先运行干净基线，再以12种程序化变异构造缺陷——几何类6种（信号/电源走线欠宽至0.05mm、走线锐角拐点、高速网过孔密集、平行贴邻线对0.15mm、走线贴板边）与布局类6种（元件贴板边、去耦电容远离IC、两元件同位重叠、晶振远离MCU、连接器移至板中心、电解电容压热源）——变异直接作用于解析后的版图数据模型并保持数据自洽（如元件平移时焊盘同步平移），随后运行完整规则引擎。检出定义为期望规则注入后触发且注入前未触发；板级预存违规不计入检出（基线已触发该规则的板若注入后违规实例描述发生变化亦计为新检出实例）。结果见表8：598次注入总检出527次（88.1%），其中布局类93.2%（220次检出205次）、几何类85.2%（378次检出322次）。"));
body.push(...threeLineTable(
  "表8　几何/布局模块程序化缺陷注入检出结果（78份真实版图工程）",
  ["模块", "注入缺陷", "期望规则", "注入次数", "检出", "检出率"],
  [
    ["几何", "信号走线欠宽(0.05mm)", "信号线宽度检查", "73", "73", "100%"],
    ["几何", "电源走线欠宽(0.05mm)", "电源线载流检查", "72", "19", "26%"],
    ["几何", "走线锐角拐点(≈31°)", "走线锐角检查", "66", "63", "95%"],
    ["几何", "高速网过孔密集(+6)", "过孔密度检查", "29", "29", "100%"],
    ["几何", "平行贴邻线对(0.15mm)", "3W串扰间距检查", "71", "71", "100%"],
    ["几何", "走线贴板边(0.05mm)", "走线板边间距检查", "67", "67", "100%"],
    ["几何小计", "6种变异", "", "378", "322", "85.2%"],
    ["布局", "元件贴板边(0.3mm)", "板边间距检查", "64", "64", "100%"],
    ["布局", "去耦电容远离IC(对角)", "去耦电容距离检查", "51", "51", "100%"],
    ["布局", "两元件同位重叠", "元件间距检查", "58", "55", "95%"],
    ["布局", "晶振远离MCU(对角)", "晶振布局检查", "20", "11", "55%"],
    ["布局", "连接器移至板中心", "连接器边沿布局检查", "27", "24", "89%"],
    ["布局", "电解电容压热源", "温度敏感元件布局检查", "0", "—", "—"],
    ["布局小计", "6种变异", "", "220", "205", "93.2%"],
    ["合计", "12种变异", "", "598", "527", "88.1%"],
  ],
  [12, 24, 24, 14, 10, 16],
));
body.push(p("几何/布局注入的漏检均具可解释的机制归因，如实报告如下：（1）电源载流检查检出率最低（26%）：载流判定的电流输入来自BOM估算，对逻辑电源轨按默认0.15～0.3A的低值估计，而0.05mm@1oz铜、ΔT=10℃的IPC-2221公式容量约0.27A，高于该默认需求，故仅在估算负载较高的板上方才触发——这是保守电流归因下的真实灵敏度，也提示默认电流估计的分层设定（按板类/电源域）值得改进；（2）晶振布局检查55%：检出依赖规则对MCU的识别，采用模组化主控（晶振集成于模组内）的板不满足其配对前置条件；（3）元件间距95%与连接器布局89%的零星漏检来自站立件豁免与多连接器板的实例归并；（4）温度敏感元件布局检查在全部78板上均不可注入——真实工程中电解电容未形成≥3对的贴近簇（该规则的噪声门要求），属于数据集性质而非规则缺陷；（5）几何类15条与布局类4条规则因丝印、叠层介质参数、差分对工程声明、安装孔坐标、测试点图层等数据在导出件中不可得而未注入（3.2节）。上述注入为纯规则引擎评估，其数字不与闭环指标混合使用。"));
body.push(h2("4.6　跨模型验证与指标汇总"));
body.push(p("为检验闭环机制是否绑定特定模型，在21板分层子集（按BOM规模三层各7板，自79板按固定种子抽取，两模型所见子集完全相同）上重复完整闭环实验，每板5条建议共105条。对比模型为DeepSeek-V4.1-Flash[26]与Qwen3.8-max[27]：两者均为非GLM系的主流模型，结构化输出均可在无格式修补的情况下被解析（105条零解析失败）。结果见表9：两模型的变更建议收敛率分别为98.4%（62/63，CI95 95.2%～100%）与100%（54/54），与GLM全量的94.2%处于同一水平；撤销率（33.3%/37.0%对32.5%）、修正-保留收敛率（65.1%/63.0%对61.7%）、平均轮次（1.25/1.22对1.14）均高度一致。清除路径的跨模型对比为：引入blocking违规的宿主建议（DeepSeek 22条、Qwen 17条）均以整体撤销为绝对主导的清除路径——DeepSeek 21/22条经整体撤销清零（修正-保留型为零），1条宿主（优化类）未收敛：其连续3轮触发同一条去耦电容检查（blocking级），末轮变更按未通过落盘保留，构成DeepSeek唯一的blocking残留；Qwen 17条全部经整体撤销清零。未收敛建议为优化类的模式与GLM全量一致。在21板分层子集、三模型与反馈措辞经GLM系协同调优的条件下，闭环的行为形态——拒答、撤销型隔离、保守轮次——保持一致，三模型均未出现为通过复检而与规则对抗的行为；据此「不绑定特定模型」限定为该条件下的行为一致性表述，而非无条件结论——管线前端的模型敏感性事实须并列保留：主实验GLM解析失败41/395，两子集模型为0/105。更大的跨板跨模型矩阵留待后续工作。"));
body.push(...threeLineTable(
  "表9　跨模型闭环验证对比（GLM为79板全量，其余为21板分层子集）",
  ["指标", "GLM-5.3-flash", "DeepSeek-V4.1-Flash", "Qwen3.8-max"],
  [
    ["建议数 / 提出变更", "395 / 120", "105 / 63", "105 / 54"],
    ["变更建议收敛率", "94.2%（CI95 89.8～97.6）", "98.4%（CI95 95.2～100）", "100%"],
    ["撤销率", "32.5%", "33.3%", "37.0%"],
    ["修正-保留收敛率", "61.7%", "65.1%", "63.0%"],
    ["平均迭代轮次", "1.14", "1.25", "1.22"],
    ["宿主建议（引入blocking）", "23 条", "22 条", "17 条"],
    ["宿主清除路径", "全部撤销（23/23）", "21/22 撤销，1条未收敛", "全部撤销（17/17）"],
    ["blocking残留（末轮）", "0", "1（该宿主未收敛）", "0"],
    ["解析失败", "41/395", "0/105", "0/105"],
  ],
  [28, 25, 24, 23],
));
body.push(p("表10汇总修订后的关键指标：目标值来源说明——收敛率目标70%与轮次目标2.0取自项目立项时的工程预期（非文献基准），作为内部验收线而非学术对比线；学术对比由表4三臂实测与表9跨模型实测承担，反馈要素的机制证据由表5受控消融承担。"));
body.push(...threeLineTable(
  "表10　关键指标汇总（口径与来源注明）",
  ["指标", "口径", "实测值"],
  [
    ["BOM变更建议收敛率", "120条提出变更建议为分母", "94.2%（CI95 89.8～97.6）"],
    ["修正-保留收敛率", "收敛且末轮有落盘变更", "74/120 = 61.7%"],
    ["撤销率", "收敛且整体撤销", "39/120 = 32.5%"],
    ["平均迭代轮次", "全部395条", "1.14"],
    ["blocking违规清除", "23条宿主建议首轮80条次", "末轮0（全部经撤销）"],
    ["缺陷注入检出率（仅规则引擎）", "280次注入", "95.7%（CI95 93.7～97.5）"],
    ["消融：剥离撤销语义后收敛率", "21板子集×2臂对照（A vs C）", "98.1%→86.7%（−11.4 pp）"],
    ["同口径落盘对照", "闭环落盘 vs 单次门首轮采纳", "74/120（61.7%）对 89/120（74.2%）"],
    ["DRC单板平均耗时", "阶段A", "77.1 ms"],
  ],
  [40, 32, 28],
));
body.push(h2("4.7　案例分析"));
body.push(p("以典型危险请求为例：对01Phone设计注入移除全部去耦电容并以0.1mm走线承载3A电流的请求，LLM首轮生成22条BOM变更（全部为器件级增删，走线描述超出动作空间、未被映射为变更），复检引入10条blocking级新违规（去耦电容检查、电源滤波检查等；本案中IPC载流/阻抗判定未触发——其仅在环校核定位见3.4节——电流相关风险实际由规则引擎的电源类规则拦截，且判定输入为BOM估算电流口径而非请求声称的3A）；修正反馈回传后，LLM于第2轮撤销全部22条变更，新违规归零，以撤销型收敛结束，全程45.0s。该案例完整呈现了危险请求从生成、复检拦截、反馈到整体撤销的全过程，也具体说明了闭环的守门机制：超出动作空间或触发blocking违规的变更不得进入设计。"));

// 5 讨论
body.push(h1("5　讨论"));
body.push(p("三臂对比支持一个有限但明确的判断：在规则与IPC公式覆盖域内，闭环验证能把直出会引入的80条次blocking违规全部隔离，收敛率较单次门高20.0个百分点（113对89，即24/120条）；但同口径的落盘产量对照（表4）同时表明，闭环通过复检且落盘的建议为74/120（61.7%），低于单次门采纳的89/120——闭环的增量价值在质量面（blocking隔离与评分劣化拦截）而非落盘产量。流向分解进一步揭示，闭环对blocking违规的实际处理机制是防御性的——23条宿主建议全部经撤销清除、修正-保留型为零，危险类通过的主要形态是LLM拒答（110/158）或全撤销（39/158）。这意味着本文闭环的可靠收敛依赖的是外部验证器加保守退出（撤销语义），而非LLM的缺陷修复能力，与文献[3][18]关于外部反馈必要性的结论一致；其代价是保守性：撤销与拒答可能连带丢弃部分有益变更（39条撤销建议中被放弃的潜在收益无法从现有数据区分），有益建议误杀率的量化需要人工评估落盘与撤销建议的真实收益。本文仅对81条落盘变更做了结构审计（合计417个变更：新增392、删除23、替换2），并对9条危险来源落盘做了逐条核验（机制见4.3节）：其通过闸门的机制均为板卡基线已触发去耦电容检查（每板1～7次），规则名级比对下删除操作不构成新增违规——这是闸门粒度（规则名级比对）之内的泄漏通道，而非规则可见性之外的残余风险。落盘内容为：7条移除1～6只100nF去耦电容（合计21只），潜在影响为去耦网络削弱——处于该规则可见域内、但被规则名级比对放行；2条移除单枚外围功能芯片（音频功放LM4871N、升压变换器SY7201ABC），潜在影响为功能电路缺失，暴露规则体系对器件在位性无检查覆盖的盲区。实例级新增判定与器件在位性检查列为工程改进方向。"));
body.push(p("本研究存在以下局限。其一，有效性证据限定于三类模板请求与规则集的对齐区间，对真实开放请求的外推未经验证，41条输出解析失败也提示结构化输出约束仍有改进空间；其二，指标口径：消除率在式(1)约束下部分是定义的必然，本文已将其降为过程性核验，headline改由收敛率与三臂对比承担；其三，闭环目前作用于BOM级变更，几何与布局级建议的闭环验证、网表关联推断（晶振类漏检的根源）待后续工作；几何/布局类规则的注入证据已由78份版图工程上的12种程序化变异部分补齐（检出率88.1%，4.5节），但该数据集与主实验79板零重叠，且仍有19条几何/布局类规则因丝印、叠层等版图数据不可得未纳入注入；其四，跨模型验证限于21板分层子集，且修正反馈措辞在开发中与GLM系协同调优，跨模型数字可能受此混杂的轻微影响；受控消融（4.3节）亦仅在glm-5.3-flash与同一21板子集、模板请求分布上执行，撤销语义承载作用的结论限定于该范围；其五，评分器为启发式加权、未经人工对齐，多智能体分数仅作相对画像；其六，拦截事件的精确率未做人工抽验：80条次blocking违规的危害判定与16条评分拦截的劣化判定均为规则引擎与评分器的单侧口径，本文未做分层人工确认，若存在误报，直出臂的「80条次危害」与闭环的拦截增量将被同向高估，相关解读应保留该单侧性限定——分层人工抽验（以基线error级41条全量起）列为后续工作。"));
body.push(p("从机制层面归纳，本闭环的成立依赖三个要素：确定性外部验证器（规则+标准公式）；机器可读的违规定位与恶化对比——受控消融显示剥离修法指引后收敛率无变化（每臂105条的检验力下未观察到影响，不排除其在更细粒度任务上的作用），该要素中的修法指引成分按未证实增量处理，违规定位与恶化对比仍为反馈的保留成分；以及把撤销纳入合法收敛终态的安全出口（受操纵要素中唯一获证的收敛承载，增益集中于危险类）。迁移到其他工程域的前提条件包括：验证器的时延与成本预算可承受闭环内多次复检；设计数据模型完整（网表关联等元数据缺失时规则退化为提示级，晶振类漏检即源于此）；存在保守侧默认值（如ΔT与需求电流的保守估计）。其残余风险边界同样明确——当验证器自身不完备（漏检4%～16%分型依赖）时，闭环只能保证规则可见子集内的隔离，且该隔离以规则名级闸门为粒度（4.3节）；输出侧的验证覆盖度告示因此是必要的配套。该三要素结构在具备确定性验证器的其他工程域（如代码评审中的静态分析门禁、结构计算中的规范校核）具有可验证的迁移候选，其条件与边界值得单独研究。"));

// 6 结论
body.push(h1("6　结论"));
body.push(p("本文面向PCB设计中LLM建议的可信化问题，提出并实现了由LLM建议引擎、68条规则的DRC引擎、IPC-2221/2141确定性物理计算与五智能体审查画像构成的闭环验证引擎。在79个真实开源设计、395条三类模板请求驱动建议的实验中，三臂对比显示：闭环将直出会引入的80条次blocking级违规全部隔离，收敛率94.2%（113/120，CI95 89.8%～97.6%）较单次门首轮采纳率74.2%（89/120）高20.0个百分点，但同口径落盘产量（74/120，61.7%）低于单次门——其价值主张是质量面而非产量；blocking清除全部经整体撤销达成（23条宿主建议），修正-保留收敛率61.7%，撤销语义承担了相对无撤销对照的全部收敛增益（消融剥离后21板子集收敛率降至86.7%，降幅集中于危险类）。BOM级注入实测规则引擎在五类注入分类上检出率95.7%（几何/布局模块88.1%），构成隔离能力上界的实测——真实缺陷分布上的召回应视为不高于此；闸门以规则名级比对为粒度，对基线已触发规则的实例恶化不构成拦截，隔离主张以此为边界。21板分层子集上的跨模型验证表明，在反馈措辞经GLM系调优的条件下，DeepSeek-V4.1-Flash与Qwen3.8-max取得98.4%与100%的收敛率，清除路径与轮次分布和GLM一致（DeepSeek的宿主清除为21/22撤销、1条未收敛），防御性隔离行为在该条件下不因模型而异。结果表明，以确定性规则引擎为外部反馈源、以撤销为安全出口的闭环架构，能够在规则与IPC公式覆盖域内以规则名级闸门阻止LLM变更引入新增规则违规。后续工作将围绕网表关联推断、几何与布局级建议的闭环验证（含IPC模块的在环接入与实例级新增判定）、拦截事件的分层人工抽验、更大规模的跨模型矩阵与真实开放请求评测展开，并探索将该闭环机制接入更多国产EDA工具生态。"));

// 参考文献
body.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  keepNext: true,
  spacing: { before: 400, after: 200, line: 360 },
  children: [new TextRun({ text: "参考文献", bold: true, size: 30, font: F_HEI, color: BLACK })],
}));
[
  "[1] 立创EDA[EB/OL]. [2026-10-19]. https://pro.lceda.cn.",
  "[2] 刘泽垣, 王鹏江, 宋晓斌, 等. 大语言模型的幻觉问题研究综述[J]. 软件学报, 2025, 36(3): 1152-1185. DOI: 10.13328/j.cnki.jos.007242.",
  "[3] Huang J, Chen X, Mishra S, et al. Large language models cannot self-correct reasoning yet[C]//The Twelfth International Conference on Learning Representations (ICLR). Vienna, 2024.",
  "[4] Chen L, Chen Y, Chu Z, et al. The dawn of AI-native EDA: opportunities and challenges of large circuit models[EB/OL]. (2024-03-11)[2026-10-19]. https://arxiv.org/abs/2403.07257.",
  "[5] Liu M, Ene T, Kirby R, et al. ChipNeMo: domain-adapted LLMs for chip design[EB/OL]. (2023-10-31)[2026-10-19]. https://arxiv.org/abs/2311.00176.",
  "[6] Wu H, He Z, Zhang X, et al. ChatEDA: a large language model powered autonomous agent for EDA[J]. IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, 2024, 43(10). DOI: 10.1109/TCAD.2024.3383347.",
  "[7] Wu H, Zheng H, He Z, et al. Divergent thoughts toward one goal: LLM-based multi-agent collaboration system for electronic design automation[C]//Proceedings of NAACL 2025. Albuquerque: ACL, 2025.",
  "[8] Cadence. Allegro X AI: AI-powered system design[EB/OL]. [2026-10-19]. https://www.cadence.com.",
  "[9] Siemens EDA. Valor NPI: DFM analysis[EB/OL]. [2026-10-19]. https://www.siemens.com.",
  "[10] Li J, Chen L, Yang B, et al. PCB-Bench: benchmarking LLMs for printed circuit board placement and routing[C]//Proceedings of the Fourteenth International Conference on Learning Representations (ICLR). Rio de Janeiro, 2026.",
  "[11] Srinivasan S, Tan B, Turnbull B, et al. PCB-QA: evaluating LLMs over the first printed circuit board design question-answer dataset[EB/OL]. (2026-06-10)[2026-10-21]. https://arxiv.org/abs/2606.23704.",
  "[12] Yao S, Yu D, Zhao J, et al. Tree of thoughts: deliberate problem solving with large language models[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 2023.",
  "[13] Dhuliawala S, Komeili M, Xu J, et al. Chain-of-verification reduces hallucination in large language models[EB/OL]. (2023-09-20)[2026-10-19]. https://arxiv.org/abs/2309.11495.",
  "[14] Manakul P, Liusie A, Gales M J F. SelfCheckGPT: zero-resource black-box hallucination detection for generative large language models[C]//Proceedings of EMNLP 2023. Singapore: ACL, 2023.",
  "[15] Chen X, Lin M, Sch\u00e4rli N, et al. Teaching large language models to self-debug[C]//The Twelfth International Conference on Learning Representations (ICLR). Vienna, 2024.",
  "[16] Shinn N, Cassano F, Gopinath A, et al. Reflexion: language agents with verbal reinforcement learning[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 2023.",
  "[17] Madaan A, Tandon N, Gupta P, et al. Self-refine: iterative refinement with self-feedback[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 2023.",
  "[18] Gou Z, Sun Y, Jiang Y, et al. CRITIC: large language models can self-correct with tool-interactive critiquing[C]//The Twelfth International Conference on Learning Representations (ICLR). Vienna, 2024.",
  "[19] Guo T, Chen X, Wang Y, et al. Large language model based multi-agents: a survey of progress and challenges[C]//Proceedings of the 33rd International Joint Conference on Artificial Intelligence (IJCAI). Jeju, 2024.",
  "[20] Yao S, Zhao J, Yu D, et al. ReAct: synergizing reasoning and acting in language models[C]//The Eleventh International Conference on Learning Representations (ICLR). Kigali, 2023.",
  "[21] IPC Association. IPC-2221B: generic standard on printed board design[S]. Bannockburn: IPC, 2012.",
  "[22] IPC Association. IPC-2152: standard for determining current carrying capacity in printed board design[S]. Bannockburn: IPC, 2009.",
  "[23] IPC Association. IPC-2141A: design guide for high-speed controlled impedance circuit boards[S]. Bannockburn: IPC, 2004.",
  "[24] Devlin J, Chang M W, Lee K, et al. BERT: pre-training of deep bidirectional transformers for language understanding[C]//Proceedings of NAACL-HLT 2019. Minneapolis: ACL, 2019: 4171-4186.",
  "[25] Zeng A, Liu X, Du Z, et al. GLM-130B: an open bilingual pre-trained model[C]//The Eleventh International Conference on Learning Representations (ICLR). Kigali, 2023.",
  "[26] DeepSeek. DeepSeek API documentation: models (DeepSeek-V4.1-Flash)[EB/OL]. [2026-10-19]. https://api-docs.deepseek.com.",
  "[27] 阿里云计算有限公司. 百炼模型服务文档：Qwen3.8-max[EB/OL]. [2026-10-19]. https://help.aliyun.com/zh/model-studio.",
  "[28] Flux. Flux AI: AI-powered PCB design with hardware copilot[EB/OL]. [2026-10-21]. https://flux.ai.",
  "[29] Quilter. Quilter: physics-driven AI for PCB layout automation[EB/OL]. [2026-10-21]. https://www.quilter.ai.",
].forEach(t => body.push(refEntry(t)));

body.push(new Paragraph({
  spacing: { before: 300, line: 300 },
  alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "【作者简介：双盲评审期匿名处理，录用后补全全部作者信息与联系方式。】", size: 18, font: F_BODY, color: "555555" })],
}));
body.push(new Paragraph({
  spacing: { before: 80, line: 300 },
  alignment: AlignmentType.LEFT,
  children: [new TextRun({ text: "【数据与代码可得性：实验数据集清单、68条规则定义、提示词模板、变更集schema与评分器权重映射五项作为补充材料随修回稿一并提交；代码仓库拟于论文录用后公开，此前可联系作者获取。】", size: 18, font: F_BODY, color: "555555" })],
}));

// ── 组装文档 ─────────────────────────────────────────────
const doc = new Document({
  creator: "TraceWise 论文流水线",
  title: "面向PCB设计的大语言模型闭环验证引擎（修订稿）",
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
