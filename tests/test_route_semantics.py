"""本地路由语义回归 — 2026-10-14 NLU 误路由修复批的锁定测试。

修复内容（scripts/probe_route_semantics.py 全量探针 59/59）：
- _match_keyword 最长关键词优先（原先注册序先到先得，短词抢占长词：
  check_rule「线宽」⊂ calc_trace_width「走线宽度」→ 走线宽度计算被
  路由到全量 DRC 扫描）
- 裸泛关键词卫生（封装/有什么/线宽）+ 生成句式前置判断
- calc_trace_width 本地真实计算（原先命中后只回「需要 AI 支持」）
- 知识问句 NLU 守卫（「什么是去耦电容？」不再触发 DRC）

本文件只测 headless 决策路径（_match_keyword / _local_fallback / handler），
不测 LLM 模式。探针脚本覆盖更全的句式与 NLU/Router 对照。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.core.controller import AppController


@pytest.fixture(scope="module")
def controller():
    return AppController(api_key="")


def _route_tool(controller, text):
    """路由命中 → tool 名集合（经 _resolve_handler_by_tool 反查）"""
    handler = controller._match_keyword(text)
    if handler is None:
        return frozenset()
    from src.agent.tools import ToolRegistry
    return frozenset(
        t.name
        for t in ToolRegistry.get_all()
        if getattr(controller._resolve_handler_by_tool(t.name), "__name__", None)
        == getattr(handler, "__name__", None)
    )


class TestTraceWidthRouting:
    """记忆中的误路由句 + 工具箱前缀句 — 必须命中 calc_trace_width"""

    @pytest.mark.parametrize("text", [
        "走线宽度 1A",                # 工具箱预填前缀句
        "走线宽度 2A 温升20",
        "帮我计算1A电流的走线宽度",     # 2026-10-13 headless 实测误路由句
        "计算1A电流需要的走线宽度",
        "1A电流线宽要多少",
        "0.5A信号线宽计算",
        "2A电流需要多大载流能力",
        "帮我算一下1A的走线要多宽",
        "计算1A电流需要的线宽",
    ])
    def test_routes_to_calc(self, controller, text):
        assert "calc_trace_width" in _route_tool(controller, text), text

    def test_not_routed_to_drc(self, controller):
        # 修复前：「走线宽度 1A」被 check_rule 的「线宽」抢占 → 全量 DRC
        assert "check_rule" not in _route_tool(controller, "走线宽度 1A")

    def test_prefix_sentence_still_drc_for_power_line(self, controller):
        # DRC 语义不被误伤：电源线宽度够不够 → 仍是设计规则检查
        assert "check_rule" in _route_tool(controller, "电源线宽度够不够")


class TestTraceWidthCalculation:
    """本地真实计算（IPC-2221），双入口共享 handler"""

    def test_prefix_sentence_calculates(self, controller):
        out = controller._local_fallback("走线宽度 1A")
        assert "走线宽度计算" in out
        assert "mm" in out
        assert "电流 1 A" in out

    def test_natural_sentence_calculates(self, controller):
        out = controller._local_fallback("帮我计算1A电流的走线宽度")
        assert "走线宽度计算" in out

    def test_temp_rise_parsed(self, controller):
        out = controller._calc_trace_width_handler("走线宽度 2A 温升20")
        assert "电流 2 A" in out
        assert "20 °C" in out

    def test_milliamp_converted(self, controller):
        out = controller._calc_trace_width_handler("500毫安走线要多宽")
        assert "电流 0.5 A" in out

    def test_explicit_params(self, controller):
        out = controller._calc_trace_width_handler(
            current_a=3.0, temp_rise_c=20.0, copper_oz=2.0,
        )
        assert "电流 3 A" in out
        assert "铜厚 2 oz" in out

    def test_inner_layer_detected(self, controller):
        out = controller._calc_trace_width_handler("内层走线 1A")
        assert "内层" in out

    def test_no_current_gives_guidance(self, controller):
        out = controller._calc_trace_width_handler("走线宽度")
        assert "电流" in out and "例如" in out

    def test_agent_loop_dispatch_with_params(self, controller):
        out = controller._dispatch_operation(
            "calc_trace_width", {"current_a": 2, "temp_rise": 15, "copper_oz": 1},
        )
        assert "电流 2 A" in out and "15 °C" in out

    def test_zero_arg_tools_still_called(self, controller):
        # _call_route_handler 兼容零参 handler（pcb_status 无 BOM 数据也安全）
        out = controller._local_fallback("查看PCB状态")
        assert isinstance(out, str) and out
        assert "PCB" in out

    def test_data_tool_without_bom_is_friendly(self, controller):
        # chat 入口不要求预载 BOM；无数据时执行类指令给提示而非抛 BOMEmptyError
        out = controller._local_fallback("合并BOM")
        assert "导入 BOM" in out


class TestShadowingRegressions:
    """其余误路由家族的锁定"""

    @pytest.mark.parametrize("text,expected", [
        ("帮我看看这张原理图", "analyze_image"),       # 「原理」⊂「原理图」
        ("筛选0603封装的电阻", "filter_components"),   # 裸「封装」抢占
        ("0603封装的尺寸是多少", "component_lookup"),
        ("导出BOM到CSV", "export_bom_csv"),            # 「导出」抢占
        ("帮我写一个去耦电容检查的DRC规则", "generate_drc_rule"),
        ("生成一个检查LED限流电阻的规则", "generate_drc_rule"),
        ("编写一个电源线宽检查规则", "generate_drc_rule"),
        ("验证这条设计建议", "verify_suggestion"),      # 裸「验证」抢占
        ("查询知识库里IPC-2221的载流规定", "rag_query"),
        ("模拟数字地要不要分开", "check_rule"),
    ])
    def test_routes(self, controller, text, expected):
        assert expected in _route_tool(controller, text), text

    def test_knowledge_question_no_action(self, controller):
        # 知识问答不触发选型搜索（裸「有什么」已移除）
        assert not _route_tool(controller, "STM32和GD32有什么区别")


class TestKnowledgeQuestionGuard:
    """「什么是X」类问句 — NLU 高置信 TEXT_CHAT 时本地不执行动作工具"""

    def test_guard_intercepts(self, controller):
        reply = controller._local_fallback("什么是去耦电容？")
        assert "知识型问题" in reply

    def test_guard_passes_operation_intent(self, controller):
        # 「怎么+操作」NLU 判为操作意图 → 守卫放行，正常路由
        assert "merge_bom" in _route_tool(controller, "怎么合并BOM")

    def test_guard_pattern_anchored(self):
        # 操作指令不以问词开头/结尾 → 不进守卫
        assert controller_question_match("合并BOM") is None
        assert controller_question_match("走线宽度 1A") is None
        assert controller_question_match("什么是去耦电容？") is not None


def controller_question_match(text):
    return AppController._QUESTION_PATTERN.search(text.strip())
