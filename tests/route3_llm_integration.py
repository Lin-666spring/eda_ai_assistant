"""
路线三 LLM 联调脚本 — 使用真实 DeepSeek API 测试闭环验证全链路

测试场景:
  1. 安全建议 → 1轮通过
  2. 危险建议 → DRC 拦截 + LLM 修正
  3. 多智能体协同审查
  4. 验证报告 Markdown 输出

用法: python tests/route3_llm_integration.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── 日志文件（同时输出到终端和文件）──
LOG_FILE = Path(__file__).resolve().parent.parent / "route3_test_output.txt"


class Tee:
    """同时写入 stdout 和日志文件"""
    def __init__(self, filepath):
        self.file = open(filepath, "w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, message):
        self.stdout.write(message)
        self.file.write(message)

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()


sys.stdout = Tee(LOG_FILE)

from src.core.controller import AppController
from src.core.verifier import (
    VerificationEngine, VerificationReport, VerificationStatus,
    SuggestionCategory, create_verifier_from_controller,
)
from src.rules.checker import DesignRuleChecker, RuleViolation, RuleSeverity

# ── 配置 ──

SAMPLE_BOM = Path(__file__).parent / "sample_bom.csv"
SAMPLE_POSITIONS = Path(__file__).parent / "sample_positions.csv"
SAMPLE_PCB = Path(__file__).parent / "sample_pcb.json"

SEPARATOR = "=" * 70


def setup_controller():
    """初始化带 LLM 和 BOM 数据的控制器"""
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    if SAMPLE_POSITIONS.exists():
        ctrl.load_positions(str(SAMPLE_POSITIONS))
    if SAMPLE_PCB.exists():
        ctrl.load_pcb(str(SAMPLE_PCB))

    # 确认 LLM 已配置
    if not ctrl.is_agent_available():
        print("❌ LLM 未配置！请检查 .env 中的 LLM_API_KEY")
        sys.exit(1)

    print(f"✅ LLM 已连接: {ctrl.agent.provider_label} / {ctrl.agent.model}")
    print(f"✅ BOM 已加载: {len(ctrl.context.bom_items)} 个元件")
    if ctrl.context.pcb_data:
        print(f"✅ PCB 已加载: {ctrl.context.pcb_data.net_count} 个网络, "
              f"{ctrl.context.pcb_data.trace_count} 条走线")
    else:
        print("⚠️  未加载 PCB 数据（部分检查受限）")
    print()
    return ctrl


def run_drc_baseline(ctrl):
    """运行 DRC 获取基线违规"""
    checker = DesignRuleChecker()
    violations = checker.check_all(
        ctrl.context.bom_items,
        ctrl.context.positions,
        pcb_data=ctrl.context.pcb_data,
    )
    print(f"📋 DRC 基线: {len(violations)} 条违规")
    for v in violations[:5]:
        sev = v.severity.value if hasattr(v.severity, 'value') else str(v.severity)
        print(f"   [{sev}] {v.rule_name}: {v.description[:60]}")
    if len(violations) > 5:
        print(f"   ... 还有 {len(violations) - 5} 条")
    print()
    return violations


# ═══════════════════════════════════════════════════════════
#  场景 1: 安全建议 — 预期 1 轮通过
# ═══════════════════════════════════════════════════════════

def test_scenario_1_safe_suggestion(ctrl):
    """测试安全的设计建议 — 不引入新违规"""
    print(SEPARATOR)
    print("🧪 场景 1: 安全建议 — 检查现有 BOM 不做修改")
    print(SEPARATOR)

    suggestion = "保持现有 BOM 不变，检查当前设计是否满足基本 PCB 设计要求"

    print(f"💬 输入建议: {suggestion}")
    print()

    result_json = ctrl.verify_suggestion(suggestion)
    report = json.loads(result_json)

    print(f"📊 结果: accepted={report['accepted']}, "
          f"status={report['final_status']}, "
          f"rounds={report['rounds']}, "
          f"issues={report['total_issues']}")
    print()

    if report["details"]:
        for d in report["details"]:
            print(f"   第 {d['round']} 轮 [{d['status']}]: {len(d['issues'])} 个问题")
            for iss in d["issues"][:3]:
                print(f"     - [{iss['severity']}] {iss['rule']}: {iss['description'][:80]}")

    print()
    print(f"📝 总结: {report.get('summary', '无')}")
    print()
    return report


# ═══════════════════════════════════════════════════════════
#  场景 2: 危险建议 — DRC 拦截 + LLM 修正迭代
# ═══════════════════════════════════════════════════════════

def test_scenario_2_dangerous_suggestion(ctrl):
    """测试危险建议 — 预期被拦截或经 LLM 修正"""
    print(SEPARATOR)
    print("🧪 场景 2: 危险建议 — 移除所有去耦电容")
    print(SEPARATOR)

    suggestion = "移除所有去耦电容以降低 BOM 成本，用 0.1mm 走线承载 5A 电流"

    print(f"💬 输入建议: {suggestion}")
    print()

    result_json = ctrl.verify_suggestion(suggestion)
    report = json.loads(result_json)

    print(f"📊 结果: accepted={report['accepted']}, "
          f"status={report['final_status']}, "
          f"rounds={report['rounds']}, "
          f"issues={report['total_issues']}")
    print()

    for d in report["details"]:
        print(f"   第 {d['round']} 轮 [{d['status']}]: {len(d['issues'])} 个问题")
        for iss in d["issues"][:5]:
            print(f"     - [{iss['severity']}] {iss['rule']}: {iss['description'][:100]}")
        if d.get("corrected"):
            print(f"   ✏️ LLM 修正: {d['corrected'][:150]}")

    print()
    print(f"📝 总结: {report.get('summary', '无')}")
    print()
    return report


# ═══════════════════════════════════════════════════════════
#  场景 3: 具体设计变更 — 差分验证
# ═══════════════════════════════════════════════════════════

def test_scenario_3_design_change(ctrl):
    """测试具体的设计变更建议"""
    print(SEPARATOR)
    print("🧪 场景 3: 合理优化建议 — 添加去耦电容")
    print(SEPARATOR)

    suggestion = (
        "在 MCU 的每个 VDD 引脚附近添加 100nF X7R 陶瓷去耦电容，"
        "电容距离引脚不超过 5mm，使用 10mil 以上走线连接"
    )

    print(f"💬 输入建议: {suggestion}")
    print()

    # 使用差分验证 — 变更前后对比
    from src.core.verifier import VerificationEngine
    engine = create_verifier_from_controller(ctrl)
    report = engine.verify(suggestion, category=SuggestionCategory.BOM_CHANGE)

    print(f"📊 结果: accepted={report.accepted}, "
          f"status={report.final_status.value}, "
          f"rounds={report.round_count}, "
          f"issues={report.total_issues}")
    print()

    for r in report.rounds:
        print(f"   第 {r.round} 轮 [{r.status.value}]: {len(r.issues)} 个问题")
        for iss in r.issues[:3]:
            print(f"     - [{iss.severity}] {iss.rule_name}: {iss.description[:100]}")
        if r.corrected_suggestion:
            print(f"   ✏️ LLM 修正: {r.corrected_suggestion[:150]}")

    print()
    md = report.to_markdown()
    print("📄 Markdown 报告（摘要）:")
    for line in md.split("\n")[:20]:
        print(f"   {line}")
    print()
    return report


# ═══════════════════════════════════════════════════════════
#  场景 4: 多智能体协同审查
# ═══════════════════════════════════════════════════════════

def test_scenario_4_multi_agent_review(ctrl):
    """测试多智能体协同审查"""
    print(SEPARATOR)
    print("🧪 场景 4: 多智能体协同审查 (5 Agent × LLM 深度分析)")
    print(SEPARATOR)

    result_json = ctrl.review_design_multi_agent()
    report = json.loads(result_json)

    if "error" in report:
        print(f"❌ 错误: {report['error']}")
        return report

    print(f"📊 总评分: {report['overall_score']:.0f} / 100  ({report['overall_grade']})")
    print()
    print("🎯 雷达图数据:")
    for item in report["radar_data"]:
        dim = item.get("dimension", item.get("name", "?"))
        score = item.get("score", 0)
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        print(f"   {dim:12s} {bar} {score:.0f}")
    print()

    print("🤖 各 Agent 审查结果:")
    for key, agent in report.get("agents", {}).items():
        findings = agent.get("findings", [])
        print(f"   {agent.get('emoji', '')} {agent['name']}: "
              f"评分 {agent['score']:.0f}, "
              f"{len(findings)} 个发现")
        if findings:
            for f in findings[:2]:
                print(f"       [{f['severity']}] {f['title']}: {f['detail'][:80]}")

    print()
    if report.get("critical_issues"):
        print(f"🔴 关键问题 ({len(report['critical_issues'])} 项):")
        for ci in report["critical_issues"][:5]:
            print(f"   [{ci['severity']}] {ci['agent_emoji']} {ci['title']}: {ci['suggestion'][:80]}")

    print()
    if report.get("improvement_roadmap"):
        print("🗺️ 改进路线图:")
        for step in report["improvement_roadmap"][:5]:
            print(f"   {step}")

    print()
    print(f"📝 共识摘要（前 200 字）:\n   {report.get('consensus', '')[:200]}")
    print()
    return report


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def main():
    print()
    print("╔" + "═" * 68 + "╗")
    print("║  路线三 闭环验证 + 多智能体 LLM 联调测试" + " " * 24 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    ctrl = setup_controller()
    run_drc_baseline(ctrl)

    results = {}

    try:
        results["scenario_1"] = test_scenario_1_safe_suggestion(ctrl)
    except Exception as e:
        print(f"❌ 场景 1 失败: {e}")
        import traceback; traceback.print_exc()

    try:
        results["scenario_2"] = test_scenario_2_dangerous_suggestion(ctrl)
    except Exception as e:
        print(f"❌ 场景 2 失败: {e}")
        import traceback; traceback.print_exc()

    try:
        results["scenario_3"] = test_scenario_3_design_change(ctrl)
    except Exception as e:
        print(f"❌ 场景 3 失败: {e}")
        import traceback; traceback.print_exc()

    try:
        results["scenario_4"] = test_scenario_4_multi_agent_review(ctrl)
    except Exception as e:
        print(f"❌ 场景 4 失败: {e}")
        import traceback; traceback.print_exc()

    # ── 汇总 ──
    print(SEPARATOR)
    print("📋 联调汇总")
    print(SEPARATOR)
    for name, r in results.items():
        if isinstance(r, VerificationReport):
            icon = "✅" if r.accepted else "❌"
            print(f"  {icon} {name}: rounds={r.round_count}, issues={r.total_issues}, "
                  f"status={r.final_status.value}")
        elif isinstance(r, dict):
            if "error" in r:
                print(f"  ❌ {name}: {r['error'][:80]}")
            elif "overall_score" in r:
                print(f"  📊 {name}: score={r['overall_score']:.0f}, grade={r['overall_grade']}")
            elif "accepted" in r:
                icon = "✅" if r["accepted"] else "❌"
                print(f"  {icon} {name}: rounds={r.get('rounds', '?')}, "
                      f"issues={r.get('total_issues', '?')}, "
                      f"status={r.get('final_status', '?')}")
    elapsed = time.time() - _start_time
    print(f"\n⏱️ 总耗时: {elapsed:.1f} 秒")
    print(f"📁 日志已保存到: {LOG_FILE}")
    print("✅ 路线三 LLM 联调完成！")
    sys.stdout.close()


_start_time = time.time()

if __name__ == "__main__":
    main()
