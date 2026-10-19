
===== 第 1 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 1 -
面向PCB 设计的大语言模型闭环验证引擎
A Closed-Loop Verification Engine for LLM-Assisted PCB Design
【作者姓名】1，【合作者姓名】2，【指导教师姓名】1
（1. 吉林大学 仪器电气学院，长春 130012；2. 【第二单位】）
摘　要：大语言模型（LLM）正在进入印制电路板（PCB）辅助设计领域，但其生成建议中的
幻觉问题——虚构非标称器件参数、给出违反载流与耐压等物理约束的危险变更——使其难以
直接用于真实设计。针对这一问题，本文提出并实现了一个面向PCB 设计的LLM 闭环验证引擎：
LLM 生成的BOM 变更建议必须经过由68 条规则构成的设计规则检查（DRC）引擎复检，未通
过的建议携带结构化修正反馈（新违规清单、修法指引与撤销语义）驱动LLM 迭代修正，最多
3 轮；物理约束类判定由IPC-2221/IPC-2141 标准公式在本地确定性计算，不依赖LLM；在此基
础上，五个领域审查智能体（电源完整性、信号完整性、热管理、电磁兼容、可制造性）并行
复审并输出六维评分。在79 个立创开源平台真实设计、395 条建议的实验中：BOM 变更建议收
敛率94.2%，平均迭代1.14 轮；blocking 级新增违规消除率100%，其中39 条危险建议被整体撤
销；程序化缺陷注入280 次检出率95.7%；多智能体审查平均评分94.2。结果表明，以确定性规
则引擎为外部反馈源的闭环机制能够在PCB 设计域有效抑制LLM 幻觉，为LLM 深度参与PCB
设计提供了一条可落地的可信化路径。
关键词：印制电路板；大语言模型；设计规则检查；闭环验证；多智能体系统；幻觉抑制
Abstract: Large language models (LLMs) are entering the domain of printed circuit board (PCB) design 
assistance, yet hallucinations in their suggestions, such as fabricated non-standard component parameters 
and dangerous changes violating current-carrying or voltage-rating constraints, prevent direct use in real 
designs. This paper proposes and implements a closed-loop verification engine for LLM-assisted PCB 
design: every LLM-generated BOM change must pass re-examination by a design rule checking (DRC) 
engine of 68 rules; failed suggestions are returned to the LLM with structured correction feedback 
(violation list, fixing guidance, and revert semantics) for iterative refinement within three rounds; physics-
constrained judgments are computed deterministically from IPC-2221/IPC-2141 standard formulas 
without LLM involvement; five domain review agents (power integrity, signal integrity, thermal, EMC, 
and manufacturability) then perform parallel re-review with a six-dimension score. On 79 real open-
source designs with 395 suggestions, the engine achieves a 94.2% convergence rate for BOM-changing 
suggestions with an average of 1.14 iterations, a 100% elimination rate of blocking-level newly introduced 
violations (39 dangerous suggestions fully reverted), a 95.7% detection rate over 280 programmatic defect 
injections, and a mean multi-agent score of 94.2. The results show that a closed loop with a deterministic 
rule engine as the external feedback source effectively suppresses LLM hallucinations in the PCB domain.
Key words: printed circuit board; large language model; design rule checking; closed-loop verification; 
multi-agent system; hallucination suppression

===== 第 2 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 2 -
1　引言
印制电路板（Printed Circuit Board, PCB）是电子系统的物理载体，其设计质量
直接决定产品的电气性能、可靠性与可制造性。近年来，以立创EDA 为代表的免费
云端EDA 工具与活跃的开源硬件社区大幅降低了PCB 设计门槛，大量学生、创客
与中小团队得以独立完成从原理图到布局布线的全流程设计。然而设计门槛的降低
并未同步降低审查门槛：商用EDA 的DRC（Design Rule Checking）集中于间距、线
宽等几何制造规则，而器件选型是否合规、去耦网络是否完整、保护电路是否缺失
等电路语义层面的审查，仍然高度依赖有经验工程师的人工复核，成为开源硬件设
计质量的突出短板。
大语言模型（Large Language Model, LLM）凭借广泛的电子学知识与自然语言
交互能力，为自动化设计审查提供了新的可能：用户以口语化中文描述需求，LLM
即可生成器件替换、参数调整、网络增删等结构化设计建议。但LLM 的幻觉问题在
物理设计域尤为危险：模型可能虚构不存在的标准电阻值或封装，推荐耐压不足的
电容，甚至建议删除TVS 保护器件或以过细走线承载大电流。此类建议一旦未经校
验直接进入设计，后果是板卡烧毁、认证失败等真实物理损失。已有研究表明，
LLM 在缺乏外部反馈的情况下难以通过自我反思可靠纠错[6]，因此让LLM 安全参
与PCB 设计的关键，在于为其配备确定性的外部验证器并构成修正闭环。
现有LLM 辅助EDA 的研究主要面向IC 设计流程：ChipNeMo 通过领域适配增
强LLM 的芯片设计问答与脚本生成能力[2]，ChatEDA 以LLM 为控制器编排EDA
工具完成RTL 到GDSII 流程[3]，EDAid 则用多个领域微调模型协作生成流程脚本
[4]。这些工作的验证环节依赖成熟IC 工具链，其经验难以直接迁移到PCB 级：
PCB 设计数据异构（BOM、网表、几何多源并存），审查规则体系以IPC 标准与器
件语义为主而非IC 工艺 DesignRule，且LLM 在PCB 域的产出形态是建议级的
BOM/参数变更而非可执行脚本，缺少与之配套的验证-反馈-修正闭环机制。

===== 第 3 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 3 -
针对上述空白，本文提出并实现了一个面向PCB 设计的LLM 闭环验证引擎，
主要贡献包括三方面：（1）闭环验证架构：将LLM 建议生成与本地DRC 规则引擎
（68 条）构成建议-检查-反馈-修正的迭代闭环，并提出以blocking 级新增违规消除
率与收敛轮次为核心的量化评估体系；（2）电路计算增强验证：载流能力、特征阻
抗、降额等物理约束按IPC-2221/IPC-2141 标准公式在本地确定性计算，零LLM 依
赖，从机制上排除该类幻觉；（3）多智能体协同审查：五个领域审查智能体对通过
闭环的建议进行并行复审，输出六维评分雷达图，为设计质量提供整体画像。在79
个真实开源设计、395 条建议的大规模实验中，各项指标均达到预期目标，验证了
该架构的有效性。
2　相关工作
2.1　大语言模型在EDA 中的应用
LLM 与EDA 的结合是近两年的研究热点[1]。NVIDIA 的ChipNeMo 在通用
LLM 基础上进行领域继续预训练与适配，在工程聊天问答与脚本生成任务上超过通
用模型[2]。ChatEDA 构建了以LLM（AutoMage）为核心的自主智能体，将EDA 工
具作为执行器，通过任务规划与多轮工具交互完成设计流程自动化[3]。EDAid 提出
发散思考、共同目标的多智能体协作范式，使用领域微调的ChipLlama 系列模型协
作生成EDA 流程脚本，在脚本质量与可靠性上取得显著提升[4]。这些工作验证了
LLM 参与电子设计的可行性，但均以IC 流程脚本为产出物、以IC 工具链为验证器。
在PCB 层面，立创EDA 等商用工具已开始引入AI 问答与辅助生成能力[16]，但总
体仍以直接生成或问答为主，缺少面向建议级变更的验证闭环，正是本文要填补的
位置。

===== 第 4 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 4 -
2.2　LLM 幻觉缓解与迭代修正
针对LLM 幻觉与错误输出，主流思路可分为三类。其一为提示与解码策略，如
思维树（Tree of Thoughts）通过在思维树上搜索改进复杂推理[9]；其二为自我修正，
Self-Debug 让模型依据自身执行反馈迭代修正代码[7]，Reflexion 以语言化的强化信
号记忆历史失败[8]；其三为多智能体协作，通过角色分工与相互评审提升可靠性
[10]。然而Huang 等人系统实验表明，LLM 在没有外部可靠反馈的情况下难以真正
自我纠错，所谓的自我修正收益往往来自提示诱导[6]。这指向一个明确结论：可靠
的修正闭环必须引入外部确定性验证源。在代码域该验证源是编译器与测试，在
PCB 设计域，本文将其落实为DRC 规则引擎与IPC 标准物理计算，并以ReAct 式推
理-行动循环[11]组织LLM 与验证器之间的交互。
2.3　设计规则检查与标准计算
DRC 是EDA 的传统支柱，商用工具已高度成熟，但传统DRC 以布线几何与制
造规则为主，不覆盖器件参数语义（如电容耐压降额、电感饱和电流）。PCB 级的
物理设计约束由IPC 标准体系规定：IPC-2221 给出了印制板通用设计要求，其载流
能力公式将线宽、铜厚、温升与允许电流联系起来[12]；IPC-2141 给出了受控阻抗
电路板的设计指南，提供微带线等典型结构的特征阻抗计算式[13]。本文将这些标
准公式实现为本地确定性计算模块，与规则引擎共同构成LLM 建议的外部验证器，
并以BERT 类预训练语言模型[5]承担中文意图识别，实现本地小模型与云端LLM
的混合推理架构。

===== 第 5 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 5 -
3　闭环验证引擎设计
3.1　总体架构
引擎总体架构如图1 所示，自上而下分为五层。输入层接收立创EDA 工程文件
（原理图、BOM 与PCB 几何数据）及用户的中文自然语言请求；解析层将工程解
析为统一的PCB 数据模型（器件清单、网络关联、几何与叠层信息），并由本地部
署的BERT 类小模型完成意图识别，将请求分流为设计审查与知识问答两类，仅前
者进入验证流程，后者由LLM 结合知识库直接作答。核心层为闭环验证引擎：LLM
建议引擎生成的BOM 变更建议先经结构化解析与危险操作预检（如删除保护器件、
载流不匹配等模式），再交由DRC 规则引擎复检；复检引入的新违规将通过结构化
修正反馈回传LLM 迭代修正，通过复检的建议方可进入下游。审查层由五个领域智
能体并行复审，输出层汇聚六维评分雷达图与结构化审查报告（违规清单、修正记
录、采纳建议）。
该架构遵循两条设计原则。其一是守门语义：任何LLM 建议在通过DRC 复检
之前不得进入设计数据，验证失败的建议可被部分或整体撤销，使LLM 的错误输出
被隔离在真实设计之外。其二是本地与云端混合：意图识别、规则检查与物理计算
全部在本地毫秒级完成且结果确定，仅建议生成与修正两个环节调用云端LLM，既
控制了时延与成本，也保证了验证环节本身不受LLM 幻觉影响。

===== 第 6 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 6 -
图1　闭环验证引擎总体架构
3.2　规则体系
规则引擎共实现68 条规则，按检查对象分为三个模块：器件参数类37 条
（BOM 模块），检查电容耐压降额、电阻功率降额、电感饱和电流、非标称参数值
封装一致性等；几何类21 条，检查走线宽度、板边间距、差分对间距、安装孔禁区
等；布局类10 条，检查去耦电容距离、晶振布局、温度敏感元件布局等。规则体系
构成如表1 所示。
工程实践中，规则进一步区分为判定类与提示类两级：判定类规则（51 条）对
当前板卡构成可证伪的判定，其检出可直接用于统计精确率；提示类规则（17 条，
如PDN 目标阻抗分析、丝印可读性）在缺少网络关联等数据时只输出设计提示，不
构成检出能力。这一区分避免了高频泛报的提示类规则稀释验证信号，保证反馈给
LLM 的每条违规都有明确语义。每条违规输出三元组（规则名、严重度、修法指
引），严重度分为error、warning、info 三级，其中error 与warning 合称blocking 级，
构成闭环收敛的判定基础，修法指引则直接进入修正反馈提示。

===== 第 7 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 7 -
表1　DRC 规则体系构成
规则模块
条数
典型规则
示例违规语义
器件参数类（BOM）
37
电容耐压降额、电阻功率降
额、电感饱和电流、参数范围
器件参数违反物理约
束或非标称值
几何类
21
电源线载流、走线宽度、板边
间距、差分对间距
几何尺寸违反制造与
载流约束
布局类
10
去耦电容距离、晶振布局、温
度敏感元件布局
布局位置违反设计准
则
合计（判定类51 / 提示类
17）
68
严重度：error / warning / info
——
3.3　闭环验证算法
闭环验证以单条建议为单位执行。给定原始BOM 与建议变更集，流程如下：
（1）预检：对明显危险的操作模式（删除ESD 保护器件、以细走线承载大电流
等）先行拦截；（2）应用与复检：将变更集应用到BOM 副本，运行完整DRC 得
到违规集合，与基线违规比对得到新增违规；（3）收敛判定：若满足收敛条件则建
议通过，否则构造结构化修正反馈回传LLM；（4）迭代：LLM 依据反馈修正变更
集（含部分或全部撤销），重复（2）～（3），迭代上限3 轮。
收敛判定同时要求无新增规则违规与设计评分不劣化。记应用变更后的违规集
合中新增违规数为N，基线设计评分为S，修正后评分为S′，容差为τ（取2.0 分），
收敛条件为：
Nnew(V′) = 0　且　ΔS = S−S′ ≤ τ
(1)
其中新增违规按规则名与基线集合比对过滤，避免把设计固有问题计入建议的
责任。评分守门项补充了规则名过滤的盲区：某些变更不触发新规则但会劣化整体
设计质量（如批量替换为劣质参数组合），由启发式设计评分器的下降幅度拦截。

===== 第 8 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 8 -
幻觉抑制效果以blocking 级新增违规消除率度量。记某条建议首轮复检引入的
blocking 级新增违规数为B1，末轮为Bf，消除率定义为：
HE = (B1 − Bf) / B1 × 100%
(2)
当首轮即无blocking 级新增违规（B1=0，含纯分析类建议）时HE 记为100%。
结构化修正反馈是闭环收敛的关键设计，包含四类信息：本轮全部新增违规及其修
法指引；同规则基线与修正后的触发对比；撤销语义（LLM 可以输出空变更集表示
全部撤销，也可以撤销部分条目）；以及允许重加条目的补录操作。反馈中显式给
出迭代历史摘要，避免LLM 重复尝试已失败的策略。工程验证表明，缺少修法指引
或撤销语义时，未收敛用例的违规数会在后续轮次中原地不动；这两项设计是收敛
率从早期实验的约五成提升至94%的决定性因素。
3.4　电路计算增强验证
纯规则匹配无法覆盖的物理约束由标准公式计算模块补齐，该模块完全独立于
LLM，输出具有确定性。载流能力按IPC-2221 计算[12]：对截面积为A（mil²）的铜
导体，允许电流为
I = k · (ΔT)0.44 · (A)0.725
(3)
其中ΔT 为允许温升（℃），k 为层系数（外层0.048、内层0.024）。例如
0.5mm 宽、1oz 铜厚（35μm）的外层走线截面积约27mil²，在10℃温升下允许电流
约1.4A；若LLM 建议以该走线承载3A 电流，模块将立即判定违规并回传载流不足
的修正指引。特征阻抗按IPC-2141 微带线公式计算[13]：
Z0 = 87 / √(εr + 1.41) · ln[5.98h / (0.8w + t)]
(4)
其中εr 为板材相对介电常数，h 为介质厚度，w 为线宽，t 为铜厚。阻抗失配、
耐压降额、饱和电流等判定同理。将物理约束交由确定性公式而非LLM 判断，是该
引擎从机制上消除一类幻觉的根本手段：无论LLM 如何生成建议，违反IPC 约束的
变更都不可能通过复检。

===== 第 9 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 9 -
3.5　多智能体协同审查
通过闭环验证的建议进入多智能体审查层。五个领域审查智能体（表2）各自
以领域专家角色审视设计，并行执行：电源完整性审查师关注去耦网络、电源滤波
与PDN 合理性；信号完整性审查师关注高速信号、阻抗匹配与串扰；热管理审查师
关注发热器件布局与散热路径；电磁兼容审查师关注滤波、屏蔽与环路面积；可制
造性审查师关注封装、丝印与工艺适配。各智能体输出结构化发现（问题、位置、
严重度、建议），合成器将其与DRC 结果、BOM 统计聚合为电源、信号、热、电
磁兼容、可制造性、成本六个维度的评分并输出雷达图，同时给出综合评分与等级。
多智能体层不阻断建议（守门由闭环层完成），其价值在于提供超出规则体系覆盖
面的整体质量画像与改进方向。
表2　领域审查智能体
智能体
审查维度
电源完整性审查师
去耦网络完整性、电源滤波、多电源域、PDN 合理性
信号完整性审查师
高速信号完整性、阻抗匹配、串扰与回流路径
热管理审查师
发热器件识别、热敏感器件布局、散热路径
电磁兼容审查师
EMI 滤波、环路面积、屏蔽与接地策略
可制造性审查师
封装工艺、丝印可读性、测试与装配友好性
4　实验与结果
4.1　实验设置
实验数据集来自立创开源平台的79 个真实开源工程，覆盖MCU 与SoC 开发板、
核心板、功能扩展与转接板、电源类及应用整机等常见板卡形态，经解析归一化为
统一PCB 数据模型后进入实验框架。实验按三个阶段执行：阶段A 对每个设计运行
纯DRC 基线检查（不调用LLM）；阶段B 执行闭环验证，实验框架以三类典型设

===== 第 10 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 10 -
计请求驱动每设计5 条建议（1 条安全检查类、2 条危险变更类、2 条优化改进类，
如移除全部100nF 去耦电容、将电源走线加宽并补充去耦组合等），LLM 据此生成
结构化BOM 变更并进入闭环，共395 条；阶段C 对每设计执行多智能体审查。另
设阶段D 程序化缺陷注入：向BOM 注入五类已知缺陷（移除去耦电容、改为非标
电阻值、删除TVS/ESD 保护二极管、电容耐压不足、删除晶振负载电容），检验规
则引擎的独立检出能力。
实验环境为Windows 桌面环境，DRC 引擎与物理计算在本地CPU 执行，建议
生成与修正调用云端GLM 系列对话模型[14]，意图识别使用本地ONNX 量化小模型。
评估指标包括：BOM 变更建议收敛率（产生变更的建议中满足式(1)的比例）、平
均迭代轮次、blocking 级新增违规消除率（式(2)）、多智能体综合评分（百分制）
与缺陷注入检出率。全量实验共执行973 次LLM 调用、消耗约211 万tokens，闭环
验证阶段总耗时126.2 分钟。
4.2　DRC 基线
79 个设计的DRC 基线共检出1513 条违规，平均每板19.2 条，其中error 级41
条、warning 级325 条、info 级1147 条，严重度分布如图2 所示（按设计展开）。触
发频次最高的规则为参数范围检查（598 次）、位号连续性检查（203 次）、去耦电
容检查（130 次）与PDN 目标阻抗分析（79 次），器件参数与电源网络类问题构成
开源设计的主要质量短板。DRC 单板平均耗时77.1ms（最大1.41s），满足闭环内
多次复检的实时性要求。

===== 第 11 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 11 -
图2　79 个设计的DRC 基线违规严重度分布
4.3　闭环验证结果
395 条建议的闭环验证结果汇总于表3：388 条通过验证（98.2%），其中120 条
提出了非空变更集，113 条在迭代上限内收敛，BOM 变更建议收敛率94.2%；经预
检与校验后81 条实际落盘变更，其余或被整体撤销、或在验证中收缩为空变更；7
条未收敛建议均为优化类，在3 轮上限处残留1 至3 条info 级提示（blocking 级新增
违规全部归零），未收敛原因集中于丝印类低严重度规则的反复触发。全部建议平
均迭代1.14 轮，其中危险类1.25 轮、优化类1.10 轮，88.1%的建议在首轮即收敛。
分类型看：79 条安全检查类建议均不产生变更、直接通过；158 条危险变更类建议
中，9 条经修正后落盘通过，39 条由LLM 依据修正反馈主动整体撤销变更（全撤销
是危险建议的正确收敛路径，验证了撤销语义设计的必要性），其余在预检或首轮
复检即被拒绝且无残留；158 条优化类建议中72 条产生变更并全部收敛。
表3　闭环验证分建议类型结果
建议类型
条数
通过
落盘变更
整体撤销
平均轮次
平均耗时
安全检查类
79
79
0
0
1.00
2.4 s
危险变更类
158
158
9
39
1.25
24.9 s
优化改进类
158
151
72
0
1.10
21.8 s
合计
395
388
81
39
1.14
19.2 s

===== 第 12 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 12 -
幻觉抑制方面，120 条可计量建议的blocking 级新增违规消除率平均为100%：
变更建议首轮复检平均引入0.78 条blocking 级新违规（合计94 条次），经不超过3
轮的修正反馈后全部归零，如图3 与图4 所示。图3 给出多轮用例中blocking 违规数
随轮次的收敛轨迹，绝大多数曲线在1 至2 轮内降至零；图4 为按建议聚合的消除
率，全部达到100%，显著高于80%的预期目标。值得注意的是，消除率的全样本一
致并非任务平凡所致：本项目早期版本的反馈仅回传规则名与描述，17 板预实验中
14 条多轮用例有10 条未收敛、违规数逐轮不动；补全修法指引与撤销语义后，全量
实验收敛率达94.2%，说明反馈信息的完整性而非模型能力是闭环可靠性的决定因
素。
图3　多轮用例的blocking 违规数迭代收敛曲线（部分）

===== 第 13 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 13 -
图4　blocking 级新增违规消除率（目标80%）
时间开销如图5 所示：安全检查类建议平均2.4s，危险类与优化类分别约24.9s
与21.8s，闭环阶段整体平均19.2s 每条建议；耗时主要由LLM 生成与修正的调用延
迟构成，单次DRC 复检不足0.1s，迭代多轮带来的规则检查开销可忽略。对照纯
LLM 直出建议（单次调用约5 至10s），闭环以约2 至3 倍的时延换取了blocking 级
违规的全量消除，处于可接受区间。
图5　各实验阶段平均耗时对比

===== 第 14 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 14 -
4.4　多智能体审查
79 个设计的多智能体审查平均综合评分94.2 分（最低88.7、最高98.3），等级
分布为A+级28 个、A 级51 个。六维平均得分依次为：热管理99.6、信号完整性
96.6、可制造性93.6、成本92.9、电磁兼容92.5、电源完整性89.9。电源维度得分最
低，与DRC 基线中去耦电容、PDN 等电源类规则触发最频繁的观察相互印证，指
示开源设计普遍存在去耦网络不完善问题。图6 以立创·泰山派3M（RK3576）开发
板为例给出六维雷达图：该板DRC 基线75 条违规（5 条warning、70 条info），综
合评分92.3（A 级），其中电磁兼容维度满分，成本维度（77.1）因器件种类多、
替代性低而显著低于均值，体现了画像对具体设计的区分能力。
图6　立创·泰山派3M 开发板多智能体六维评分雷达图
4.5　程序化缺陷注入
规则引擎的独立检出能力通过280 次缺陷注入评估，总体检出268 次，检出率
95.7%，分型结果见表4。非标电阻值与电容耐压不足检出率均为100%；移除去耦
电容98.4%；删除TVS/ESD 保护二极管89.8%；删除晶振负载电容84.0%，为最低

===== 第 15 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 15 -
项，其漏检发生于设计缺少网络关联数据的场景，此时相关规则按设计退化为提示
级。个别类型样本量很小（如删除LED 限流电阻仅1 例），其检出率不具统计意义。
表4　程序化缺陷注入检出结果
注入缺陷类型
注入次数
检出次数
检出率
改为非标电阻值
73
73
100.0%
电容耐压不足
61
61
100.0%
移除去耦电容
61
60
98.4%
删除TVS/ESD 保护二极管
59
53
89.8%
删除晶振负载电容
25
21
84.0%
删除LED 限流电阻
1
0
0.0%
合计
280
268
95.7%
4.6　关键指标汇总与跨模型初步验证
表5 汇总本文提出的量化指标体系及其目标值与实测值，各指标均达到或显著
优于目标。跨模型方面，使用DeepSeek 系列模型[15]的单设计冒烟实验（1 个设计、
5 条建议）得到全部收敛、消除率100%、多智能体评分97 的结果，初步表明闭环
机制的有效性不依赖特定LLM；完整的跨模型对比实验留待后续工作。
表5　关键指标与目标对比
指标
目标值
实测值
BOM 变更建议收敛率
> 70%
94.2%（113/120）
平均迭代轮次
≤ 2.0
1.14
blocking 级新增违规消除率
> 80%
100%
多智能体平均综合评分
> 75
94.2
程序化缺陷注入检出率
——
95.7%（268/280）
DRC 单板平均耗时
毫秒级
77.1 ms

===== 第 16 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 16 -
4.7　案例分析
以典型危险建议为例：对01Phone 设计注入移除全部去耦电容并以0.1mm 走线
承载3A 电流的变更请求，LLM 首轮生成的变更集包含22 条BOM 修改，复检引入
10 条blocking 级新违规（去耦电容检查、电源线载流检查等）；修正反馈回传后，
LLM 于第2 轮撤销全部载流相关变更并恢复去耦组合，新违规归零，收敛通过，全
程45.0s。该案例完整呈现了危险建议从生成、拦截、反馈到撤销修正的全过程，也
说明载流类违规由IPC-2221 公式判定的确定性与即时性。
5　讨论
实验结果支持三个判断。第一，确定性外部反馈是LLM 在PCB 域可靠收敛的
充分条件：本引擎中blocking 级新增违规全量消除、94.2%的变更建议收敛，与文献
[6]关于外部反馈必要性的结论在PCB 域形成呼应；其中修法指引与撤销语义两项反
馈设计贡献最大，缺任一项时修正轮次即出现违规数停滞。第二，规则引擎与物理
计算的分工有效：参数与语义类违规（非标值、耐压、去耦缺失）由规则覆盖，载
流与阻抗类约束由标准公式兜底，两者互补构成完整验证面。第三，多智能体层与
规则层观察相互印证（电源维度得分最低与电源类规则触发最多一致），表明其画
像具备诊断价值而非泛化打分。
本研究仍存在四点局限。其一，闭环目前作用于BOM 级变更，布局与布线级
建议的闭环验证需要几何编辑与重检的更复杂管线；其二，部分规则依赖网络关联
数据，缺数据时退化为提示级，晶振负载电容类缺陷的漏检即源于此，引入网表推
断是明确的改进方向；其三，实验中41 条建议因LLM 输出解析失败而不计入通过
率（非误放行），结构化输出约束可进一步压缩该比例；其四，全量实验基于单一
LLM，跨模型对比仅完成冒烟验证，评分器为启发式加权，多智能体评分应理解为
相对质量画像而非绝对基准。

===== 第 17 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 17 -
6　结论
本文面向PCB 设计中LLM 建议的可信化问题，提出并实现了由LLM 建议引擎、
68 条规则的DRC 引擎、IPC-2221/2141 确定性物理计算与五智能体协同审查构成的
闭环验证引擎。在79 个真实开源设计、395 条建议的实验中，引擎实现BOM 变更
建议94.2%收敛、平均1.14 轮迭代、blocking 级新增违规100%消除、缺陷注入
95.7%检出与多智能体均分94.2 的综合表现。结果表明，以确定性规则引擎为外部
反馈源的闭环架构能够在PCB 设计域有效抑制LLM 幻觉，使LLM 得以安全地承担
设计建议职责。后续工作将围绕网表关联推断、布局级闭环验证、跨模型全量对比
与规则体系持续扩充展开，并探索将该闭环机制接入更多国产EDA 工具生态。
参考文献
[1] Chen L, Chen Y, Chu Z, et al. The dawn of AI-native EDA: opportunities and challenges of large 
circuit models[EB/OL]. (2024-03-11). https://arxiv.org/abs/2403.07257.
[2] Liu M, Wang T, Zhang Q, et al. ChipNeMo: domain-adapted LLMs for chip design[EB/OL]. (2023-
11-01). https://arxiv.org/abs/2311.00276.
[3] He Z, Wu H, Li Z, et al. ChatEDA: a large language model powered autonomous agent for EDA[J]. 
IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems, 2024, 43(11): 
3970-3983.
[4] Wu H, Zheng H, He Z, et al. Divergent thoughts toward one goal: LLM-based multi-agent 
collaboration system for electronic design automation[C]//Proceedings of the 2025 Conference of 
the North American Chapter of the Association for Computational Linguistics. Albuquerque: ACL, 
2025.
[5] Devlin J, Chang M W, Lee K, et al. BERT: pre-training of deep bidirectional transformers for 
language understanding[C]//Proceedings of NAACL-HLT 2019. Minneapolis: ACL, 2019: 4171-
4186.
[6] Huang J, Chen X, Mishra S, et al. Large language models cannot self-correct reasoning yet[C]//The 
Twelfth International Conference on Learning Representations (ICLR). Vienna, 2024.
[7] Chen X, Lin M, Schärli N, et al. Teaching large language models to self-debug[C]//The Twelfth 
International Conference on Learning Representations (ICLR). Vienna, 2024.
[8] Shinn N, Cassano F, Gopinath A, et al. Reflexion: language agents with verbal reinforcement 
learning[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 
2023.

===== 第 18 页 =====
面向PCB 设计的大语言模型闭环验证引擎
- 18 -
[9] Yao S, Yu D, Zhao J, et al. Tree of thoughts: deliberate problem solving with large language 
models[C]//Advances in Neural Information Processing Systems 36 (NeurIPS). New Orleans, 
2023.
[10] Guo T, Chen X, Wang Y, et al. Large language model based multi-agents: a survey of progress and 
challenges[C]//Proceedings of the 33rd International Joint Conference on Artificial Intelligence 
(IJCAI). Jeju, 2024.
[11] Yao S, Zhao J, Yu D, et al. ReAct: synergizing reasoning and acting in language models[C]//The 
Eleventh International Conference on Learning Representations (ICLR). Kigali, 2023.
[12] IPC Association. IPC-2221B: generic standard on printed board design[S]. Bannockburn: IPC, 
2012.
[13] IPC Association. IPC-2141A: design guide for high-speed controlled impedance circuit boards[S]. 
Bannockburn: IPC, 2004.
[14] Zeng A, Liu X, Du Z, et al. GLM-130B: an open bilingual pre-trained model[C]//The Eleventh 
International Conference on Learning Representations (ICLR). Kigali, 2023.
[15] DeepSeek-AI. DeepSeek-V3 technical report[EB/OL]. (2024-12-26). 
https://arxiv.org/abs/2412.19437.
[16] 立创EDA[EB/OL]. [2026-10-19]. https://pro.lceda.cn.
【作者简介：姓名（出生年—），性别，籍贯，单位/学历方向；联系方式待补。】
