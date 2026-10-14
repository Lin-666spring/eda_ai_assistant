"""路由语义探针 — 全工具语义句子实测本地降级路由（无 LLM、纯离线）。

对每句同时输出三层结果：
  1. keyword   — controller._match_keyword（headless 唯一决策路径）
  2. nlu       — NLUEngine.classify（LLM 模式的本地意图分类）
  3. router    — LLMRouter._classify_by_keyword（LLM 路由降级）

用法:
    python scripts/probe_route_semantics.py            # 全量
    python scripts/probe_route_semantics.py --fails    # 只看未达标
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.controller import AppController  # noqa: E402
from src.agent.nlu_engine import NLUEngine  # noqa: E402
from src.agent.router import LLMRouter  # noqa: E402

# (句子, 可接受工具集合, 备注)
# acceptable=None  → 期望不命中任何动作工具（落到建议列表/帮助）
# soft=True 的句子属于跨家族歧义，只报告不计入失败数
CASES: list[tuple[str, frozenset, str, bool]] = [
    # ── 走线宽度计算 calc_trace_width ──
    ("走线宽度 1A", frozenset({"calc_trace_width"}), "工具箱前缀句", False),
    ("走线宽度 2A 温升20", frozenset({"calc_trace_width"}), "前缀句+温升", False),
    ("帮我计算1A电流的走线宽度", frozenset({"calc_trace_width"}), "记忆中的误路由句", False),
    ("计算1A电流需要的走线宽度", frozenset({"calc_trace_width"}), "自然句", False),
    ("1A电流线宽要多少", frozenset({"calc_trace_width"}), "线宽要多少", False),
    ("0.5A信号线宽计算", frozenset({"calc_trace_width"}), "线宽计算", False),
    ("2A电流需要多大载流能力", frozenset({"calc_trace_width"}), "载流能力", False),
    ("帮我算一下1A的走线要多宽", frozenset({"calc_trace_width"}), "要走多宽", False),
    ("计算1A电流需要的线宽", frozenset({"calc_trace_width"}), "倒装句", False),
    # ── 设计规则检查 check_rule ──
    ("检查设计规则", frozenset({"check_rule"}), "", False),
    ("运行DRC", frozenset({"check_rule"}), "", False),
    ("去耦电容放的位置对不对", frozenset({"check_rule"}), "去耦", False),
    ("电源线宽度够不够", frozenset({"check_rule"}), "电源线", False),
    ("过孔密度是不是太密了", frozenset({"check_rule"}), "过孔", False),
    ("差分对有没有等长", frozenset({"check_rule"}), "差分", False),
    ("模拟数字地要不要分开", frozenset({"check_rule"}), "模数", True),
    # ── PCB 分析 pcb_analysis ──
    ("帮我分析一下PCB布局", frozenset({"pcb_analysis"}), "", False),
    ("看看走线是否合理", frozenset({"pcb_analysis"}), "走线", False),
    ("层叠结构有没有问题", frozenset({"pcb_analysis"}), "层叠", False),
    ("这块板的阻抗控制得怎么样", frozenset({"pcb_analysis"}), "阻抗", False),
    ("分析一下布线", frozenset({"pcb_analysis"}), "布线", False),
    # ── PCB 状态 ──
    ("查看PCB状态", frozenset({"pcb_status"}), "", False),
    ("导入PCB文件", frozenset({"pcb_status"}), "", False),
    # ── BOM 合并 ──
    ("合并BOM", frozenset({"merge_bom", "ai_merge_bom"}), "", False),
    ("帮我合并同类元件", frozenset({"merge_bom"}), "", False),
    ("整理物料清单", frozenset({"merge_bom"}), "物料清单", False),
    ("AI智能合并元件", frozenset({"ai_merge_bom"}), "智能合并", False),
    # ── 校验封装 ──
    ("校验封装", frozenset({"validate_package"}), "", False),
    ("检查一下元件的封装对不对", frozenset({"validate_package"}), "封装对不对", False),
    ("封装匹配检查", frozenset({"validate_package"}), "", False),
    # ── 位号查重 ──
    ("查重", frozenset({"check_duplicates"}), "", False),
    ("看看有没有重复的位号", frozenset({"check_duplicates"}), "", False),
    # ── 筛选 ──
    ("筛选0603封装的电阻", frozenset({"filter_components"}), "筛选vs封装", False),
    ("过滤出所有电容", frozenset({"filter_components"}), "", False),
    # ── 报告导出 ──
    ("生成HTML交互式BOM", frozenset({"generate_html_bom"}), "", False),
    ("导出网页版BOM", frozenset({"generate_html_bom"}), "", False),
    ("导出BOM到CSV", frozenset({"export_bom_csv"}), "", False),
    ("统计一下元件分布", frozenset({"summary_report"}), "", False),
    # ── BOM 健康 / 供应链 ──
    ("检查BOM中哪些元件缺货", frozenset({"bom_health"}), "", False),
    ("BOM健康检查", frozenset({"bom_health"}), "", False),
    ("估算一下所有元件的总成本", frozenset({"bom_cost_summary", "bom_health"}), "", False),
    ("帮我找更便宜的替代料", frozenset({"find_alternatives"}), "", False),
    ("评估一下供应链风险", frozenset({"supply_risk"}), "", False),
    # ── 元件查询 / 选型 ──
    ("查询STM32F103C8T6的规格参数", frozenset({"component_lookup"}), "规格", False),
    ("0603封装的尺寸是多少", frozenset({"component_lookup"}), "尺寸vs封装", False),
    ("找一款5V转3.3V的LDO", frozenset({"search_component"}), "", False),
    ("推荐一款LDO", frozenset({"search_component"}), "", False),
    # ── 图像 ──
    ("帮我看看这张原理图", frozenset({"analyze_image"}), "原理图", False),
    ("分析一下这张PCB截图", frozenset({"analyze_image"}), "", False),
    # ── 规则生成 ──
    ("帮我写一个去耦电容检查的DRC规则", frozenset({"generate_drc_rule"}), "写一个检查", False),
    ("生成一个检查LED限流电阻的规则", frozenset({"generate_drc_rule"}), "生成…规则", False),
    ("编写一个电源线宽检查规则", frozenset({"generate_drc_rule"}), "编写…规则", False),
    # ── 解释 / 闭环验证 / 知识库 ──
    ("解释一下这条规则的原理", frozenset({"explain_design_rule"}), "", False),
    ("验证这条设计建议", frozenset({"verify_suggestion"}), "验证建议", False),
    ("查询知识库里IPC-2221的载流规定", frozenset({"rag_query"}), "", False),
    # ── 通用对话（不应触发动作工具）──
    ("什么是去耦电容？", None, "知识问句（NLU守卫）", False),
    ("STM32和GD32有什么区别", None, "", False),
    ("0603电阻的功率一般是多少", None, "", False),
    ("怎么合并BOM", frozenset({"merge_bom", "ai_merge_bom"}), "怎么+操作=放行", False),
]


def resolve_tool_name(ctrl: AppController, handler) -> frozenset:
    """handler 反查所有能解析到它的工具名"""
    if handler is None:
        return frozenset()
    names = set()
    from src.agent.tools import ToolRegistry
    for tool in ToolRegistry.get_all():
        resolved = ctrl._resolve_handler_by_tool(tool.name)
        if resolved is not None and getattr(resolved, "__name__", None) == getattr(handler, "__name__", None):
            names.add(tool.name)
    return frozenset(names)


def main() -> int:
    ctrl = AppController(api_key="")
    nlu = NLUEngine()
    router = LLMRouter.from_config(api_key="")

    # NLU 本地 TextCNN 预热（离线）
    try:
        nlu.warm_up()
    except Exception:
        pass

    hard_fail: list[str] = []
    soft_fail: list[str] = []
    n_mismatch_nlu = 0

    print(f"{'判定':4s} {'句子':<24s} {'期望':<20s} {'keyword路由':<28s} {'NLU意图':<16s} router意图")
    print("-" * 110)

    for sentence, acceptable, note, soft in CASES:
        if acceptable is None:
            # 「不动作」句判定 = 知识问句守卫生效 或 关键词无命中
            guard = ctrl._local_chat_guard(sentence)
            handler = ctrl._match_keyword(sentence)
            ok = guard is not None or handler is None
            actual: frozenset = frozenset({"(NLU守卫拦截)"}) if guard is not None else resolve_tool_name(ctrl, handler)
            nlu_intent, nlu_conf, _ = nlu.classify(sentence)
            router_intent = router.classify_intent(sentence)
            exp_txt = "(不动作)"
        else:
            handler = ctrl._match_keyword(sentence)
            actual = resolve_tool_name(ctrl, handler)
            nlu_intent, nlu_conf, _ = nlu.classify(sentence)
            router_intent = router.classify_intent(sentence)
            ok = bool(actual & acceptable)
            exp_txt = "/".join(sorted(acceptable))
        mark = "ok" if ok else ("soft" if soft else "FAIL")

        act_txt = "/".join(sorted(actual)) if actual else "(无命中→建议)"
        note_txt = f"  [{note}]" if note else ""
        print(f"{mark:4s} {sentence:<24s} {exp_txt:<20s} {act_txt:<28s} "
              f"{nlu_intent:<14s}{nlu_conf:.2f}  {router_intent.name}{note_txt}")

        if not ok:
            (soft_fail if soft else hard_fail).append(sentence)
        if acceptable and nlu_intent not in {
            t.upper() for t in acceptable
        } | {"TEXT_CHAT", "LOCAL_ONLY"}:
            # NLU/Router 属 LLM 模式路径，仅统计口径差异不计失败
            n_mismatch_nlu += 1

    print("-" * 110)
    total = len(CASES)
    print(f"共 {total} 句：达标 {total - len(hard_fail) - len(soft_fail)}，"
          f"硬失败 {len(hard_fail)}，软失败(歧义/跨家族) {len(soft_fail)}")
    if hard_fail:
        print("硬失败句：")
        for s in hard_fail:
            print(f"  - {s}")
    if soft_fail:
        print("软失败句：")
        for s in soft_fail:
            print(f"  - {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
