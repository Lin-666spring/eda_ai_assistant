"""NLU 意图分类训练数据生成器

使用模板 + 术语表替换生成多样化的中文 PCB/电子查询样本。
输出 JSON 格式：{"text": str, "intent": str}

使用方式:
    python src/ml/generate_nlu_data.py              # 生成默认 600 条
    python src/ml/generate_nlu_data.py --count 1000  # 生成 1000 条
    python src/ml/generate_nlu_data.py --output data/nlu_train.json
"""

import argparse
import json
import random
import sys
from pathlib import Path

from src.ml.split_utils import split_by_template

# ── 术语表 ──

_TERMS = {
    "{board}": [
        "PCB", "电路板", "开发板", "电源板", "这块板子", "这块PCB",
        "STM32开发板", "电机驱动板", "DCDC电源板", "ESP32音频板",
    ],
    "{area}": [
        "电源区域", "模拟区域", "数字区域", "高频区域", "晶振周围",
        "MCU周围", "去耦电容", "功率电感", "LDO输出端", "USB接口",
    ],
    "{issue}": [
        "走线宽度", "过孔数量", "去耦电容", "信号完整性", "电源完整性",
        "EMC", "间距", "爬电距离", "阻抗匹配", "热管理",
        "接地", "滤波", "保护电路", "复位电路", "晶振电路",
    ],
    "{component}": [
        "电阻", "电容", "电感", "二极管", "三极管", "MOSFET",
        "LDO", "DC-DC", "运放", "比较器", "晶振", "磁珠",
        "ESD保护管", "TVS管", "光耦", "继电器", "蜂鸣器",
        "LED", "排针", "USB座", "TF卡座", "按键", "开关",
    ],
    "{rule}": [
        "去耦电容", "电源线宽", "信号线间距", "过孔密度", "差分对",
        "板边间距", "锐角走线", "模拟数字分离", "热焊盘", "ESD保护",
        "复位电路", "晶振负载电容", "PDN目标阻抗", "阻抗匹配",
    ],
    "{mcu}": [
        "STM32F103", "STM32F407", "ESP32", "GD32", "ATmega328P",
        "CH32V307", "AIR32F103", "nRF52840", "RP2040", "i.MX RT",
    ],
    "{package}": [
        "0603", "0805", "1206", "0402", "SOT-23", "SOT-223",
        "SOP-8", "QFN-32", "LQFP-48", "BGA-256", "TO-220",
        "DO-214AC", "SOD-323", "SC-70", "DFN-10",
    ],
    "{file}": [
        "BOM.csv", "BOM.xlsx", "bom.xls", "物料清单.csv", "元件表.xlsx",
        "PCB.json", "网表.net", "坐标文件.csv", "pcb_data.json",
    ],
    "{action}": [
        "分析", "检查", "校验", "审查", "验证", "查看", "展示", "显示",
    ],
    "{supplier}": [
        "立创商城", "得捷", "贸泽", "云汉芯城", "硬之城", "华秋",
        "淘宝", "Arrow", "Farnell",
    ],
    # 电流/电压 — 走线宽度计算句式（2026-10-14 误路由批：数字+单位句式零覆盖
    # 导致 calc 类句子全灭，被 RULE_CHECK 的「宽度+电流」模板抢走）
    "{current}": [
        "1A", "2A", "0.5A", "500mA", "1.5A", "3A", "100mA", "5A", "10A", "800mA",
    ],
    "{voltage}": [
        "5V", "3.3V", "12V", "24V", "1.8V", "9V",
    ],
    # {aspect} — A-10 意图批（2026-10-24）：通用求建议句式的性能维度术语，
    # 支撑「怎么提高EMC性能」类 TEXT_CHAT 通用咨询句族
    "{aspect}": [
        "EMC性能", "EMI抑制", "信号完整性", "电源完整性", "散热能力",
        "抗干扰能力", "转换效率", "稳定性", "可靠性", "EMC",
    ],
}


# ── 模板定义 ──

_RAW_TEMPLATES: dict[str, list[str]] = {
    "TEXT_CHAT": [
        # 从 INTENT_DESCRIPTORS examples 扩展
        "什么是去耦电容？",
        "STM32和GD32有什么区别？",
        "0603封装的电阻功率一般是多少？",
        "如何选择合适的LDO？",
        "PCB设计中有哪些常见问题？",
        "{component}的选型要注意什么？",
        "介绍一下{mcu}的特点",
        "DCDC和LDO各有什么优缺点？",
        "什么情况下需要做阻抗匹配？",
        "如何降低EMI干扰？",
        "四层板和两层板有什么差别？",
        "信号完整性是个什么概念？",
        "过孔会带来什么问题？",
        "模拟地和数字地为什么要分开？",
        "电源纹波一般要求多少？",
        "晶振的负载电容怎么选？",
        "为什么要在芯片旁边放去耦电容？",
        "PCB走线拐直角有什么不好？",
        "回流焊和波峰焊有什么区别？",
        "ESD保护的常用方法有哪些？",
        "讲讲差分信号的好处",
        "热焊盘有什么用？",
        "什么封装的电阻适合手焊？",
        "BGA封装有什么优缺点？",
        "说说你对接地设计的理解",
        "安规间距一般要求多少？",
        "帮我解释一下PDN是什么",
        "常用的PCB板材有哪些？",
        "铜厚一般选多少？",
        "沉金和喷锡有什么区别？",
         # ── A-10 意图批（2026-10-24）：通用求建议句族 + PCB 常识问答 ──
        # 口径：不指向「这块板/我的PCB」的通用咨询 → TEXT_CHAT；
        # 明确评估当前板子才归 PCB_ANALYSIS
        "怎么提高{aspect}",
        "如何改善{aspect}",
        "怎么优化{aspect}",
        "有没有提升{aspect}的办法",
        "{aspect}方面有什么实用技巧",
        "怎么把{aspect}做得更好",
        "虚焊一般是什么原因引起的？",
        "飞线是什么意思？",
        "PCB打样一般要多少钱？",
        "FR-4和高频板材有什么区别？",
        "过孔为什么要盖油？",
        "什么情况下需要加散热孔？",
         # ── A-10 二轮（2026-10-24）：封装级常识问句族 ──
        # 口径：「一般是多少」的封装级常识 → TEXT_CHAT；具体料号参数查询 →
        # COMPONENT_LOOKUP（错例「0603电阻的功率一般是多少」曾判 COMPONENT_LOOKUP）。
        # 均含占位符；{package}=0603+{component}=电阻 恰好填出评估句时由碰撞回避重填
        "{package}{component}的功率一般是多少",
        "{package}的{component}耐压一般是多少",
        "{package}封装一般配多大的{component}",
    ],
    "BOM_ANALYSIS": [
        "帮我合并BOM中的同类元件",
        "检查一下元件的封装对不对",
        "看看有没有重复的位号",
        "整理物料清单",
        "BOM合并",
        "AI智能合并元件",
        "筛选出所有{package}封装的{component}",
        "校验BOM中的封装型号是否匹配",
        "帮我看看BOM有没有漏掉什么元件",
        "合并相同的料号",
        "按照参数归类物料",
        "检查位号有没有冲突",
        "帮我分析BOM中的元件类型分布",
        "统计一下用了哪些封装",
        "查一下BOM中有没有{package}的元件",
        "帮我整理一下{file}",
        "把相同型号的器件合并到一起",
        "看看BOM中哪些电阻可以合并",
        "对比两个BOM的差异",
        "有没有位号重复的情况？",
        "帮我查一下这个BOM的元件数量",
        "把{component}都筛选出来",
        # ── 筛选句式变体（「筛选0603封装的电阻」类原本判成 TEXT_CHAT）──
        "筛选{package}封装的{component}",
        "筛选所有{package}{component}",
        "过滤出所有{component}",
        "过滤{package}的电容",
        "找出所有{package}电阻",
        # ── 短命令/查表型句式（2026-10-14 BERT 批：短输入上下文少，
        # 无覆盖时 rbt3 曾把「查重」0.93 判成 RULE_CHECK）──
        "查重",
        "BOM查重",
        "位号查重",
        "封装匹配检查",
        "封装匹不匹配",
        "重码检查",
         # ── A-10 意图批（2026-10-24）：BOM 数量/清点问句族 ──
        # 口径：对已导入 BOM 的内容做数量/构成提问 → BOM_ANALYSIS
        #（针对评估错例「BOM里有多少个电阻」曾被判 COMPONENT_LOOKUP）
        "BOM里有多少个{component}",
        "BOM里{component}用了几个",
        "数一下BOM里的{component}",
        "BOM一共有多少个元件",
        "统计BOM中{component}的数量",
        "看看{component}在BOM里有几条",
        "BOM中{package}封装的元件有几个",
        "BOM里元件总数是多少",
        "BOM里各种元件分别有多少",
        "这版BOM一共用了多少种元件",
        "BOM里{component}占了多少",
        "数数BOM里有多少个料",
         # ── A-10 二轮（2026-10-24）：筛选/过滤 + 查重族扩容 ──
        #（错例「筛选0603封装的电阻」「过滤出所有电容」曾判 TEXT_CHAT/LOCAL_ONLY、
        #「查重」曾判 RULE_CHECK：单模板家族在模板级切分下可能整族落单侧零学习）
        "筛选出{package}的{component}",
        "把{package}的{component}过滤出来",
        "筛一下{component}",
        "只看{package}封装的{component}",
        "列出BOM里的{component}",
        "查一下重复",
        "重复检查",
        "位号有重复吗",
        "料号查重",
         # ── A-10 三轮（2026-10-24）：BOM_ANALYSIS 物料清单整理句族（错例「整理物料清单」两模型皆误判 BOM_HEALTH，原模板逐字等于评估句被整族移出，补口语化存活变体） ──
        "整理一下物料清单",
        "物料清单整理",
        "把物料清单整理一下",
        "整理下BOM",
    ],
    "BOM_HEALTH": [
        "检查BOM中哪些元件缺货",
        "这个物料有没有停产？",
        "帮我找更便宜的替代料",
        "估算一下所有元件的总成本",
        "这些料的生命周期如何？",
        "查一下这个物料的库存",
        "这个元件在{supplier}有没有货？",
        "帮我检查BOM的健康状况",
        "有没有元件快停产了？",
        "推荐一些{component}的替代料",
        "这个{component}太贵了，有没有便宜的？",
        "查一下这个料的价格",
        "BOM中有没有采购风险的元件？",
        "看看哪些物料交期比较长",
        "这个元件的生命周期状态是什么？",
        "帮我评估一下供货风险",
        "这几个元件哪家有现货？",
        "找一下封装兼容的替代料",
        "把成本高的元件都标出来",
        "查一下立创商城的库存",
        # ── 健康/供应链检查入口句式 ──
        "BOM健康检查",
        "检查BOM健康状态",
        "跑一下BOM健康",
        "评估供应链风险",
        "供应链风险评估",
        # ── 库存短问句（2026-10-14 BERT 批：「看看库存还够不够」曾被判 RULE_CHECK）──
        "看看库存还够不够",
        "库存够吗",
        "库存还够吗",
        "还缺料吗",
        "物料够不够",
         # ── A-10 意图批（2026-10-24）：供应链/货源问句族 ──
        "BOM里有没有临停产的料",
        "帮我看看哪些元件涨价了",
        "这个型号最近货期多长",
        "第二货源有哪些可以选",
        "哪些物料只有单一货源",
        "哪种料采购最紧迫",
         # ── A-10 三轮（2026-10-24）：BOM_HEALTH 缺货/成本健康问句族（错例「检查BOM中哪些元件缺货」判 BOM_ANALYSIS、「估算一下所有元件的总成本」判 LOCAL_ONLY，两模板均被整族移出训练） ──
        "看看哪些元件缺货",
        "查一下缺料的元件",
        "BOM里有什么缺货的",
        "看看BOM缺不缺料",
        "估算BOM总成本",
        "算一下所有元件的成本",
        "估一下物料总成本",
        "统计一下BOM的总价",
    ],
    "RULE_CHECK": [
        "检查设计规则",
        "运行DRC",
        "看看去耦电容放对没有",
        "电源线宽度够不够",
        "检查走线有没有问题",
        "跑一下{rule}检查",
        "检查{area}的{issue}",
        "{board}有没有什么问题？",
        "帮我做一次完整的DRC检查",
        "检查一下{rule}是否合规",
        "看看有没有间距违规",
        "晶振的负载电容对吗？",
        "电源走线的宽度够不够承载这个电流？",
        "过孔数量会不会太多？",
        "检一下差分对的等长等间距",
        "差分对有没有等长",
        "差分线等长了吗",
        "检查一下差分等长",
        "有没有锐角走线？",
        "板边的间距够不够？",
        "模拟和数字区域分开了吗？",
        "每个IC都有去耦电容吗？",
        "检查一下复位电路是否完整",
        "PDN阻抗达标了吗？",
        "这个设计有什么隐患？",
        "帮我跑一下所有DRC规则",
        "看看我的PCB过EMC有没有问题",
        # ── 模数分离检查句式（与 TEXT_CHAT 的「为什么要分开」知识问句区分）──
        "模拟数字地要不要分开",
        "检查模数分离",
        "检查一下模拟数字隔离",
        "模拟地和数字地区分了吗",
        # ── 闭环验证句式（verify_suggestion 挂在 RULE_CHECK 意图下）──
        "验证这条设计建议",
        "帮我验证这个设计建议",
        "闭环验证这个修改",
        "验证一下这条修改建议",
        # ── 短命令/违规解释句式（2026-10-14 BERT 批：「全板DRC跑一遍」
        #    曾被判 PCB_ANALYSIS、「解释规则原理」被判 VISUAL）──
        "全板DRC跑一遍",
        "DRC跑一遍",
        "把DRC全跑一遍",
        "规则全跑一遍",
        "解释一下这条规则的原理",
        "这条规则为什么违规",
        "说说这个违规的原理",
         # ── A-10 意图批（2026-10-24）：检查命令变体 ──
        "检查一下走线间距",
        "帮我检查过孔",
        "把设计规则检查跑一下",
        "看看晶振电路有没有问题",
        "检查一下电源完整性",
        "查一下有没有直角走线",
        "差分阻抗检查一下",
        "所有规则都检查一遍",
         # ── A-10 二轮（2026-10-24）：摆放/密度检查族扩容 ──
        #（错例「去耦电容放的位置对不对」「过孔密度是不是太密了」曾判
        # BOM_ANALYSIS/PCB_ANALYSIS：摆放合理性/密度核查走规则检查口径）
        "{component}放的位置对不对",
        "去耦电容位置合理吗",
        "检查{component}的摆放位置",
        "过孔会不会太密",
        "{rule}达标吗",
         # ── A-10 三轮（2026-10-24）：RULE_CHECK DRC/电源线宽/模数地/规则解释句族（错例「电源线宽度够不够」「模拟数字地要不要分开」「运行DRC」「解释一下这条规则的原理」四个原模板均被整族移出训练，补占位符变体与措辞不同的短命令） ──
        "{board}的电源线宽度够不够",
        "电源线宽达标吗",
        "运行一下DRC",
        "DRC检查",
        "执行设计规则检查",
        "模数地需不需要分开",
        "模拟数字地分不分开",
        "检查一下模数地分离",
        "解释下这条规则",
        "讲讲这条规则的依据",
        "这条规则的原理是什么",
    ],
    "PCB_ANALYSIS": [
        "帮我分析一下PCB布局",
        "看看走线是否合理",
        "PCB的电源网络能承载多大电流？",
        "这块板的层叠结构有问题吗？",
        "{board}的{issue}怎么样？",
        "分析一下PCB的信号完整性",
        "这块板的电源设计好不好？",
        "看看有没有信号串扰的问题",
        "PCB散热怎么样？",
        "帮我审查一下PCB设计",
        "这个布线方案合理吗？",
        "看看高频信号的处理怎么样？",
        "分析PCB的电源分配网络",
        "地的设计有没有问题？",
        "帮我看看电磁兼容方面怎么样",
        "这块板的可制造性如何？",
        "分析一下走线的载流能力",
        "看看关键信号的回流路径",
        "这个层叠方案可以吗？",
        "帮我评估一下PCB设计质量",
        "多智能体审查一下这块板",
        # ── 走线宽度计算句式（2026-10-14 误路由批补齐：数字电流句式
        #    原本零覆盖，被 RULE_CHECK 的「宽度+电流」模板整体抢走）──
        "走线宽度 {current}",
        "帮我计算{current}电流的走线宽度",
        "计算走线宽度",
        "{current}线宽要多少",
        "{current}信号线宽计算",
        "{current}电流需要多大载流能力",
        "{current}的走线要多宽",
        "帮我算一下{current}的走线要多宽",
        "计算{current}需要的线宽",
        "{current}走多宽的线",
        "{current}要用多宽的铜线",
        # ── PCB 导入/状态 ──
        "导入PCB文件",
        "加载PCB",
        "打开PCB文件",
        "查看PCB状态",
        "PCB导入了吗",
        # ── 知识库查询（rag_query 挂在 PCB_ANALYSIS 意图下）──
        "查询知识库里IPC-2221的载流规定",
        "知识库里怎么规定{rule}",
        "查一下规范里{rule}的要求",
        "IPC标准对{issue}有什么规定",
        "设计指南里{rule}怎么说的",
        # ── 层叠分析变体（2026-10-14 BERT 批：「层叠结构有没有问题」
        #    曾被判 RULE_CHECK；走设计审查口径不走检查命令口径）──
        "层叠结构有没有问题",
        "叠层有没有问题",
        "层叠设计合不合理",
         # ── A-10 意图批（2026-10-24）：面向当前板的评估变体 ──
        # 与 TEXT_CHAT「怎么提高{aspect}」通用咨询划界：
        # 指向当前板/这块板 → PCB_ANALYSIS
        "评估一下这块板的EMC表现",
        "这块板子的布线密度怎么样",
        "帮我看看这块PCB的地处理得好不好",
        "整体布局有什么可以改进的地方",
        "电源部分的布局合理吗",
        "这块板的信号完整性风险大不大",
        "帮我总体评价一下这次设计",
         # ── A-10 二轮（2026-10-24）：PCB 状态问句族 ──
        # 口径：板子/PCB 状态 → PCB_ANALYSIS；系统/界面状态 → LOCAL_ONLY
        #（错例「查看PCB状态」曾判 LOCAL_ONLY；新句措辞均不同于评估句原句）
        "看看PCB状态",
        "PCB现在什么状态",
        "当前PCB的状态",
        "PCB加载好了吗",
         # ── A-10 三轮（2026-10-24）：PCB_ANALYSIS 走线评估/知识库查询句族（错例「看看走线是否合理」判 RULE_CHECK、「查询知识库里IPC-2221的载流规定」判 BOM_ANALYSIS，原模板均被整族移出训练） ──
        "看看布线是否合理",
        "评估走线是否合理",
        "走线设计得合理吗",
        "知识库查询{rule}",
        "查知识库里{rule}的规定",
        "查一下{rule}的相关标准",
    ],
    "CODE_RULE_GEN": [
        "帮我写一个{rule}的DRC规则",
        "生成自动化BOM校验脚本",
        "创建一个{rule}检查规则",
        "帮我生成一个检查脚本",
        "写一段代码来验证{rule}",
        "帮我写一个Python脚本来分析BOM",
        "生成{pin_count}脚芯片的去耦电容规则",
        "写一个自动检查{rule}的函数",
        "帮我生成DCR检查代码",
        "写一个封装验证的规则",
        "创建自定义的PCB检查项",
        "生成一个检查{issue}的脚本",
        "帮我写个自动化测试",
        "写一段代码计算走线载流量",
        "生成一个{component}的验证规则",
         # ── A-10 意图批（2026-10-24）：生成代码/规则变体 ──
        "写一个检查位号连续性的脚本",
        "帮我生成一段过孔密度统计代码",
        "用Python写个BOM编码规范检查",
        "生成一个电源树检查函数",
        "帮我定制一条焊盘对称性规则",
        "帮我写个自动布局检查的小工具",
        "帮我写一个检查封装库一致性的规则",
         # ── A-10 三轮（2026-10-24）：CODE_RULE_GEN 规则/校验代码生成句族扩容（二轮 val 仅 6 条未达标，补带占位符的脚本/函数生成变体） ──
        "写个规则检查{rule}",
        "生成一段校验代码",
        "帮我写个脚本检查{rule}",
        "写个函数做{rule}检查",
    ],
    "REPORT_GEN": [
        "生成HTML交互式BOM",
        "导出BOM到CSV",
        "生成设计规则检查报告",
        "给我一个元件统计摘要",
        "导出物料清单",
        "生成PCB设计报告",
        "导出统计数据",
        "帮我生成一份DRC报告",
        "输出BOM表格",
        "做一个元件分类统计",
        "导出所有违规的汇总",
        "生成一份设计评审报告",
        "把分析结果导出",
        "生成{board}的检测报告",
        "给我一份完整的评估报表",
        "导出当前的BOM数据",
        # ── 统计入口句式（「统计一下元件分布」原本判成 BOM_ANALYSIS）──
        "统计一下元件分布",
        "统计元件类型分布",
        "做一个元件分布统计",
         # ── A-10 意图批（2026-10-24）：导出/报表句族 ──
        "导出一份BOM汇总",
        "生成元件清单报表",
        "把DRC结果导出成报告",
        "输出一份检查报告",
        "生成BOM统计报表",
        "导出当前分析结果",
        "把违规明细导出成表格",
        "给我一份本次审查的报告",
         # ── A-10 二轮（2026-10-24）：导出格式句族 ──
        #（错例「导出一份Excel格式的BOM」曾判 CODE_RULE_GEN；新句均含格式词
        # 但措辞不同于评估句原句，避免与评估集逐字碰撞被整族丢弃）
        "把BOM导出成Excel",
        "导出CSV格式的BOM",
        "BOM导出为Excel",
        "导出一份CSV的BOM",
         # ── A-10 三轮（2026-10-24）：REPORT_GEN 交互式/网页 BOM 报告句族（错例「生成HTML交互式BOM」原模板因与评估句逐字相同被碰撞回避整族移出训练，补措辞不同的可存活变体） ──
        "生成一份交互式BOM",
        "生成网页版BOM",
        "生成HTML的BOM页面",
        "生成交互式物料清单",
        "输出HTML格式的BOM",
    ],
    "COMPONENT_LOOKUP": [
        "查询{mcu}的规格参数",
        "{package}封装的尺寸是多少？",
        "AMS1117-3.3的datasheet",
        "找一个5V转3.3V的LDO",
        "这个电容的耐压是多少？",
        "查一下{component}的规格书",
        "{package}的焊盘尺寸是多少？",
        "这个{component}的参数是什么？",
        "帮我找一下{mcu}的数据手册",
        "这个元件的引脚定义是什么？",
        "查一下{package}封装的功率能到多少",
        "{component}的典型应用电路是什么？",
        "这个电感的工作频率是多少？",
        "帮我搜一下{component}的替代型号",
        "看看这个元件有没有RoHS认证",
        "查一下这个料的工作温度范围",
        # ── 选型请求句式（「找一款/推荐一款」原本判成 TEXT_CHAT）──
        "找一款{voltage}转3.3V的LDO",
        "推荐一款{component}",
        "推荐个{voltage}的LDO",
        "有没有{voltage}转3.3V的LDO",
        "选一款{mcu}",
        "帮忙推荐个{component}型号",
         # ── A-10 意图批（2026-10-24）：具体元件参数查询句族 ──
        # 口径：查具体元件型号的参数/手册/引脚 → COMPONENT_LOOKUP
        #（与 BOM_ANALYSIS 数量问句划界：BOM 语境 → BOM_ANALYSIS）
        "{mcu}有多少个GPIO",
        "查一下{mcu}的Flash容量",
        "{component}的ESR是多少",
        "这个{component}耐压多少",
        "帮我查{mcu}的主频",
        "{component}的温度系数是多少",
        "{mcu}的RAM容量是多大",
        "这个{mcu}有几个UART串口",
        "查一下{mcu}的工作电压范围",
        "{component}的引脚数是多少",
         # ── A-10 二轮（2026-10-24）：选型请求句族扩容 ──
        #（错例「帮我选一颗LDO」曾判 BOM_ANALYSIS；「帮我选一颗{component}」
        # 恰好填出评估句原句时由碰撞回避逻辑重填）
        "帮我选一颗{component}",
        "帮我选个{mcu}",
        "帮我挑一款{component}",
        "给个{component}选型建议",
    ],
    "VISUAL": [
        "帮我看看这张原理图",
        "分析这个PCB截图中的问题",
        "这张波形图有什么异常？",
        "看看这个3D图",
        "帮我分析一下这张电路图",
        "截图里的走线有问题吗？",
        "看看这个PCB布局图",
        "分析一下这个示波器波形",
        "这张元器件布局怎么样？",
        "帮我看看这块板的3D渲染图",
        "从截图分析一下PCB的问题",
        "这个原理图截图帮我看看",
        "看看这个频谱图",
        "这个板子的实物照片，有什么问题？",
        "帮我分析一下这张PCB截面图",
        # ── 波形分析短句（2026-10-14 BERT 批：「波形怎么有振铃」
        #    曾被判 TEXT_CHAT；波形图分析走 VISUAL 口径）──
        "波形怎么有振铃",
        "看看这个波形有什么问题",
        "这个波形是不是振铃了",
        "帮我看看这个示波器截图",
         # ── A-10 意图批（2026-10-24）：图像分析句族 ──
        "这张布局图看着有没有明显缺陷",
        "帮我看看这截图里的焊盘",
        "分析一下这个热成像图",
        "这个原理图里有没有画错的地方",
        "看看这张阻抗仿真曲线",
        "这张图里的丝印标反了没有",
         # ── A-10 三轮（2026-10-24）：VISUAL 截图分析句族扩容（二轮 val 仅 5 条未达标，补措辞不同的截图/Layout 分析变体） ──
        "看看这张PCB截图",
        "截图里有什么问题",
        "看看这个Layout图",
    ],
    "LOCAL_ONLY": [
        "显示BOM统计信息",
        "查看当前状态",
        "汇总元件类型",
        "显示帮助",
        "看看当前打开了什么文件",
        "显示版本信息",
        "打开文件",
        "切换主题",
        "显示BOM概览",
        "查看系统信息",
        "列出所有可用的操作",
        "看看有什么功能",
        "统计一下",
        "汇总信息",
        "概览",
        "当前项目信息",
        # ── 系统状态短问句（2026-10-14 BERT 批：「现在系统什么状态」
        #    曾被判 TEXT_CHAT）──
        "现在系统什么状态",
        "系统什么状态",
        "系统状态怎么样",
        "当前什么状态",
         # ── A-10 意图批（2026-10-24）：本地界面操作句族 ──
        "打开设置页面",
        "切到分析页面",
        "显示当前文件路径",
        "看看帮助文档",
        "刷新一下界面",
        "把主题换成深色模式",
         # ── A-10 三轮（2026-10-24）：LOCAL_ONLY 帮助入口句族（错例「打开帮助」曾判 PCB_ANALYSIS conf 0.49，帮助句式覆盖薄，补措辞不同的帮助/说明入口变体） ──
        "打开帮助页面",
        "看下帮助",
        "帮助文档",
        "看看使用说明",
    ],
}


def _fill_template(template: str) -> str:
    """用随机术语填充模板中的占位符"""
    result = template
    for key, values in _TERMS.items():
        if key in result:
            result = result.replace(key, random.choice(values), 1)
    # 处理 {pin_count}
    if "{pin_count}" in result:
        result = result.replace("{pin_count}", str(random.choice([8, 16, 32, 48, 64, 100, 144])), 1)
    return result


def _fill_template_avoiding(template: str, banned: set[str], max_tries: int = 5) -> tuple[str, bool]:
    """填充模板并回避与固定评估集的逐字碰撞（A-10 二轮 2026-10-24）。

    评估句若逐字出现在 train/val，eval 精度就混入记忆成分（一轮实测
    train+val 与 data/nlu_eval.json 逐字碰撞 37 条）。填充后命中评估句 →
    换随机术语重填（至多 max_tries 次）；仍碰撞（无占位符的纯文本模板与
    评估句相同时必然如此，会被整模板丢弃）则丢弃该样本，由调用方计数。
    """
    text = _fill_template(template)
    for _ in range(max_tries):
        if text not in banned:
            return text, False
        text = _fill_template(template)
    return text, True


def _expand_templates(
    raw_templates: dict[str, list[str]],
    count_per_class: int,
    banned_texts: set[str] | None = None,
    drop_counts: dict[str, int] | None = None,
) -> list[dict]:
    """展开模板为训练样本

    每个模板使用多次（随机选术语），确保每个类别有 count_per_class 条。
    样本携带 ``_template``（来源模板原文）供模板级切分使用（验收 A-9），
    写盘前由 split_by_template 剥离。

    A-10 二轮（2026-10-24）：传入 banned_texts（评估集句文本集）时，填充
    结果逐字命中评估句 → 重填至多 5 次，仍命中则丢弃该样本并计入
    drop_counts[intent]（被丢弃的样本不补额，类别总量相应减少）。
    """
    samples: list[dict] = []

    def _make(intent: str, t: str) -> None:
        if banned_texts is None:
            samples.append({"text": _fill_template(t), "intent": intent,
                            "_template": t})
            return
        text, dropped = _fill_template_avoiding(t, banned_texts)
        if dropped:
            if drop_counts is not None:
                drop_counts[intent] = drop_counts.get(intent, 0) + 1
            return
        samples.append({"text": text, "intent": intent, "_template": t})

    for intent, templates in raw_templates.items():
        if len(templates) >= count_per_class:
            # 模板足够多，随机采样
            chosen = random.sample(templates, count_per_class)
            for t in chosen:
                _make(intent, t)
        else:
            # 模板不够，需要复用。先保证每个模板至少入训一次，剩余名额
            # 随机选术语造变体。（2026-10-14 BERT 批：纯 random.choice 会让
            # 部分模板零次入训——「运行DRC」恰好漏采，rbt3 对这个评估句
            # 稳定判错；全量覆盖对 TextCNN 同样受益。）
            for t in templates:
                _make(intent, t)
            for _ in range(count_per_class - len(templates)):
                t = random.choice(templates)
                _make(intent, t)

    return samples


def generate_data(
    count_per_class: int = 60,
    output_path: str = "data/nlu_train.json",
    val_split: float = 0.15,
    seed: int = 42,
) -> None:
    """生成训练/验证数据

    Args:
        count_per_class: 每个意图的训练样本数（验证集按比例）
        output_path: 输出路径（会生成 train 和 val 两个文件）
        val_split: 验证集比例
        seed: 随机种子
    """
    random.seed(seed)

    # 生成全量样本
    # 注意：不要往训练里加乱码/域外负例 —— 曾实验把乱码标 TEXT_CHAT，
    # 模型把「运行DRC」这类短指令也学成 TEXT_CHAT（评估集 94%→89%）。
    # 乱码过度自信由 nlu_engine 的 OOD 置信门（关键词零交集→压回
    # 关键词路径）确定性兜底，比表征层面的硬负例更精准。
    total_per_class = int(count_per_class / (1 - val_split))

    # ── A-10 二轮（2026-10-24）：eval 碰撞回避 ──
    # train/val 与固定评估集逐字相同的样本一律重填或丢弃，保证 eval 精度
    # 不混入记忆成分。无占位符的纯文本模板若与评估句完全相同会被整模板
    # 丢弃（计数见生成结束输出）。
    eval_path = Path("data/nlu_eval.json")
    banned_texts: set[str] = set()
    if eval_path.exists():
        with open(eval_path, "r", encoding="utf-8") as f:
            banned_texts = {s["text"] for s in json.load(f)}
        print(f"  eval 碰撞回避: 已加载 {len(banned_texts)} 条评估句（{eval_path}）")
    else:
        print(f"  eval 碰撞回避: 未找到 {eval_path}，跳过（不做回避）")
    drop_counts: dict[str, int] = {}
    all_samples = _expand_templates(_RAW_TEMPLATES, total_per_class,
                                    banned_texts=banned_texts,
                                    drop_counts=drop_counts)

    # 洗牌
    random.shuffle(all_samples)

    # 按类别分层分割
    from collections import defaultdict
    by_class: dict[str, list] = defaultdict(list)
    for s in all_samples:
        by_class[s["intent"]].append(s)

    train_samples = []
    val_samples = []
    for intent, items in by_class.items():
        # 模板级切分（验收 A-9，2026-10-24）：同一模板的全部变体进同一侧。
        # 此前样本级切分实测验证集 81% 与训练集逐字重复 —— val_acc 在测
        # 记忆而非泛化。
        tr, va = split_by_template(items, val_split, label_key="intent")
        train_samples.extend(tr)
        val_samples.extend(va)

    random.shuffle(train_samples)
    random.shuffle(val_samples)

    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # 写入文件
    base = Path(output_path).stem
    ext = Path(output_path).suffix
    train_path = output_dir / f"{base}_train{ext}"
    val_path = output_dir / f"{base}_val{ext}"

    for path, data in [(train_path, train_samples), (val_path, val_samples)]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"训练数据生成完成:")
    print(f"  训练集: {len(train_samples)} 条 → {train_path}")
    print(f"  验证集: {len(val_samples)} 条 → {val_path}")
    print(f"  类别分布:")
    for intent in sorted(by_class.keys()):
        train_cnt = sum(1 for s in train_samples if s["intent"] == intent)
        val_cnt = sum(1 for s in val_samples if s["intent"] == intent)
        label = intent
        print(f"    {label:20s}  训练 {train_cnt:3d}  验证 {val_cnt:3d}")

    if drop_counts:
        print("  eval 碰撞丢弃（重填 5 次仍与评估句逐字相同而弃用，不补额）:")
        for intent in sorted(drop_counts):
            print(f"    {intent:20s}  {drop_counts[intent]:3d} 条")
        print(f"    {'合计':20s}  {sum(drop_counts.values()):3d} 条")
    else:
        print("  eval 碰撞丢弃: 0 条")


def main():
    parser = argparse.ArgumentParser(
        description="生成 NLU 意图分类训练数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--count", type=int, default=60,
        help="每个意图的训练样本数 (default: 60, 总计约 600 条)",
    )
    parser.add_argument(
        "--output", type=str, default="data/nlu_train.json",
        help="输出路径 (default: data/nlu_train.json)",
    )
    parser.add_argument(
        "--val-split", type=float, default=0.15,
        help="验证集比例 (default: 0.15)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="随机种子 (default: 42)",
    )
    args = parser.parse_args()

    generate_data(
        count_per_class=args.count,
        output_path=args.output,
        val_split=args.val_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
