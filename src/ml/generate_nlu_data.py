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
        "有没有锐角走线？",
        "板边的间距够不够？",
        "模拟和数字区域分开了吗？",
        "每个IC都有去耦电容吗？",
        "检查一下复位电路是否完整",
        "PDN阻抗达标了吗？",
        "这个设计有什么隐患？",
        "帮我跑一下所有DRC规则",
        "看看我的PCB过EMC有没有问题",
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


def _expand_templates(raw_templates: dict[str, list[str]], count_per_class: int) -> list[dict]:
    """展开模板为训练样本

    每个模板使用多次（随机选术语），确保每个类别有 count_per_class 条。
    """
    samples: list[dict] = []

    for intent, templates in raw_templates.items():
        if len(templates) >= count_per_class:
            # 模板足够多，随机采样
            chosen = random.sample(templates, count_per_class)
            for t in chosen:
                samples.append({"text": _fill_template(t), "intent": intent})
        else:
            # 模板不够，需要复用（每次随机选术语，产生不同变体）
            for i in range(count_per_class):
                t = random.choice(templates)
                samples.append({"text": _fill_template(t), "intent": intent})

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
    total_per_class = int(count_per_class / (1 - val_split))
    all_samples = _expand_templates(_RAW_TEMPLATES, total_per_class)

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
        split_idx = int(len(items) * (1 - val_split))
        train_samples.extend(items[:split_idx])
        val_samples.extend(items[split_idx:])

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
