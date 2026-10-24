"""P1 批次A 回归测试（验收 2026-10-24）

覆盖:
- P1-1 anthropic_client 工具执行异常不再炸掉 Agent Loop
- P1-2 anthropic_client 429/5xx 退避重试 / max_iterations 摘要 / _history 锁
- P1-3 nlu_engine 关键词评分遍历补充后的 self._descriptors
- P1-4 design_templates 2 字符裸关键词词边界匹配（TMP36 不再误判 Buck）
"""
import concurrent.futures
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import requests

from src.agent.anthropic_client import AnthropicClient
from src.agent.design_templates import DesignTemplateEngine, _keyword_in_text
from src.agent.nlu_engine import NLUEngine
from src.bom.parser import BOMItem


# ——— 公共夹具/桩 ———

FUNC_DEF = {
    "function": {
        "name": "probe_tool",
        "description": "probe",
        "parameters": {"type": "object", "properties": {}},
    }
}

TOOL_USE_RESP = {
    "content": [{
        "type": "tool_use",
        "id": "tu_1",
        "name": "probe_tool",
        "input": {"x": 1},
    }],
    "stop_reason": "tool_use",
}

FINAL_RESP = {
    "content": [{"type": "text", "text": "最终答复"}],
    "stop_reason": "end_turn",
}


class _FakeResp:
    """requests.post 返回值桩：raise_for_status 按 status_code 抛 HTTPError"""

    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} error", response=self)

    def json(self):
        return self._payload

    @property
    def text(self):
        return ""


@pytest.fixture
def engine_keyword_only():
    """禁用本地模型与 embedding，钉死纯关键词评分路径（测试确定性）"""
    engine = NLUEngine(api_key="")
    engine._embedding_failed = True
    engine._local_model_attempted = True
    return engine


# ——— P1-1: 工具异常隔离 ———


class TestP1ToolException:
    def test_tool_exception_becomes_tool_result(self, monkeypatch):
        """P1-1: 单个工具抛异常不得终止 Agent Loop —— 错误作为 tool_result
        回传后 LLM 继续给出最终答复（对齐 llm_client.chat_with_tools 口径）"""
        calls = []

        def boom(name, args):
            raise ValueError("元件库连接超时")

        client = AnthropicClient(api_key="k", tool_executor=boom)
        responses = [dict(TOOL_USE_RESP), dict(FINAL_RESP)]

        def fake_api_call(payload):
            calls.append(payload)
            return responses.pop(0)

        monkeypatch.setattr(client, "_api_call", fake_api_call)
        reply = client.chat_with_tools("查一下", functions=[FUNC_DEF])

        assert reply == "最终答复"  # 循环挺过工具失败并走完
        assert len(calls) == 2
        tool_results = calls[1]["messages"][-1]["content"]
        assert tool_results[0]["type"] == "tool_result"
        assert "工具执行失败" in tool_results[0]["content"]
        assert "元件库连接超时" in tool_results[0]["content"]

    def test_partial_tool_failure_keeps_other_results(self, monkeypatch):
        """P1-1: 混合批次中一个工具失败，其余工具结果仍完整回传"""
        def flaky(name, args):
            if name == "bad_tool":
                raise RuntimeError("boom")
            return "ok"

        client = AnthropicClient(api_key="k", tool_executor=flaky)
        multi_tool_resp = {
            "content": [
                {"type": "tool_use", "id": "t1", "name": "bad_tool", "input": {}},
                {"type": "tool_use", "id": "t2", "name": "good_tool", "input": {}},
            ],
            "stop_reason": "tool_use",
        }
        calls = []
        responses = [multi_tool_resp, dict(FINAL_RESP)]

        def fake_api_call(payload):
            calls.append(payload)
            return responses.pop(0)

        monkeypatch.setattr(client, "_api_call", fake_api_call)
        reply = client.chat_with_tools("批量", functions=[FUNC_DEF])
        assert reply == "最终答复"
        results = {b["tool_use_id"]: b["content"]
                   for b in calls[1]["messages"][-1]["content"]}
        assert "工具执行失败" in results["t1"]
        assert results["t2"] == "ok"


# ——— P1-2: 重试 / 迭代耗尽 / 历史锁 ———


class TestP1Retry:
    def test_429_5xx_backoff_retry(self, monkeypatch):
        """P1-2: 429/503 依次重试并按 1.5s/4s 退避，最终成功"""
        client = AnthropicClient(api_key="k")
        sleeps = []
        monkeypatch.setattr("src.agent.anthropic_client.time.sleep",
                            lambda s: sleeps.append(s))
        seq = [_FakeResp(429), _FakeResp(503), _FakeResp(200, {"ok": True})]
        monkeypatch.setattr("src.agent.anthropic_client.requests.post",
                            lambda *a, **kw: seq.pop(0))
        out = client._api_call({"model": "m"})
        assert out == {"ok": True}
        assert sleeps == [1.5, 4.0]

    def test_4xx_not_retried(self, monkeypatch):
        """P1-2 负样本: 401 等参数类错误不重试、不等待"""
        client = AnthropicClient(api_key="k")
        sleeps = []
        monkeypatch.setattr("src.agent.anthropic_client.time.sleep",
                            lambda s: sleeps.append(s))
        monkeypatch.setattr("src.agent.anthropic_client.requests.post",
                            lambda *a, **kw: _FakeResp(401))
        with pytest.raises(requests.exceptions.HTTPError):
            client._api_call({"model": "m"})
        assert sleeps == []

    def test_retry_exhausted_raises(self, monkeypatch):
        """P1-2: 5xx 持续失败时至多重试 2 次（1.5s+4s）后照常抛出"""
        client = AnthropicClient(api_key="k")
        sleeps = []
        monkeypatch.setattr("src.agent.anthropic_client.time.sleep",
                            lambda s: sleeps.append(s))
        monkeypatch.setattr("src.agent.anthropic_client.requests.post",
                            lambda *a, **kw: _FakeResp(500))
        with pytest.raises(requests.exceptions.HTTPError):
            client._api_call({"model": "m"})
        assert sleeps == [1.5, 4.0]

    def test_stream_path_retries(self, monkeypatch):
        """P1-2: 流式路径走同一重试通道（首次 503，重试后成功）"""
        client = AnthropicClient(api_key="k")
        sleeps = []
        monkeypatch.setattr("src.agent.anthropic_client.time.sleep",
                            lambda s: sleeps.append(s))

        ok_resp = _FakeResp(200, {})
        ok_resp.iter_lines = lambda decode_unicode=True: iter([])
        attempts = []

        def fake_post(*args, **kwargs):
            attempts.append(kwargs.get("stream"))
            if kwargs.get("stream") and len(attempts) > 1:
                return ok_resp
            return _FakeResp(503)

        monkeypatch.setattr("src.agent.anthropic_client.requests.post", fake_post)
        out = client._api_stream({"messages": []}, on_token=None)
        assert out == ""
        assert attempts == [True, True]  # 流式请求失败后原样重发
        assert sleeps == [1.5]


class TestP1MaxIterations:
    def test_exhausted_loop_returns_summary_not_empty(self, monkeypatch):
        """P1-2: max_iterations 耗尽不能返回空串 —— 返回已执行操作摘要并记入历史
        （修复前 stop_reason 停在 tool_use 时 extract_text 得到 ""）"""
        client = AnthropicClient(api_key="k",
                                 tool_executor=lambda name, args: "结果OK")
        monkeypatch.setattr(client, "_api_call",
                            lambda payload: dict(TOOL_USE_RESP))
        reply = client.chat_with_tools("一直调工具", functions=[FUNC_DEF],
                                       max_iterations=3)
        assert reply.strip() != ""
        assert "已达到最大操作步数限制" in reply
        assert "[probe_tool]" in reply
        assert "结果OK" in reply
        history = client.get_history()
        assert history[-1]["role"] == "assistant"
        assert "已达到最大操作步数限制" in history[-1]["content"]

    def test_final_text_preferred_over_summary(self, monkeypatch):
        """P1-2: 迭代耗尽但最后一轮带文本时，优先返回该文本"""
        client = AnthropicClient(api_key="k", tool_executor=lambda n, a: "ok")
        partial_resp = {
            "content": [{"type": "text", "text": "尽量收尾的文本"}],
            "stop_reason": "stop_sequence",
        }
        monkeypatch.setattr(client, "_api_call",
                            lambda payload: dict(partial_resp))
        reply = client.chat_with_tools("问", functions=[FUNC_DEF],
                                       max_iterations=2)
        assert reply == "尽量收尾的文本"


class TestP1HistoryLock:
    def test_history_lock_present(self):
        client = AnthropicClient(api_key="k")
        assert isinstance(client._history_lock, type(threading.Lock()))

    def test_concurrent_record_turn_no_loss(self):
        """P1-2: 并发 _record_turn 不丢轮次、不越界（封顶线内一条不少）"""
        client = AnthropicClient(api_key="k")
        client.seed_history([])

        def worker(i):
            client._record_turn(f"q{i}", f"a{i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(worker, range(20)))
        assert len(client.get_history()) == 40  # 20 轮 × 2 条，恰在封顶线内


# ——— P1-3: 关键词评分使用补充后的描述符表 ———


class TestP1RegistryKeywords:
    def test_trace_width_keyword_score_above_gate(self, engine_keyword_only):
        """P1-3: ToolRegistry 补充关键词须参与评分 —— 「计算走线宽度」的
        PCB_ANALYSIS 关键词得分 ≥ 0.40 门限（修复前 0.181 且被 RULE_CHECK
        的「线宽」以 0.235 反超）"""
        scores = engine_keyword_only._compute_keyword_score("计算走线宽度")
        assert scores["PCB_ANALYSIS"] >= 0.40
        # 负样本对照：修复前 PCB_ANALYSIS(0.181) < RULE_CHECK(0.235) 误路由
        assert scores["PCB_ANALYSIS"] > scores["RULE_CHECK"]

    def test_trace_width_keyword_path_intent(self, engine_keyword_only):
        """P1-3: 纯关键词路径下「计算走线宽度」应判为 PCB_ANALYSIS 而非
        RULE_CHECK（旧实现 TOOL 补充词缺席导致误路由）"""
        name, _, _ = engine_keyword_only.classify("计算走线宽度")
        assert name == "PCB_ANALYSIS"

    def test_full_engine_confidence_above_gate(self):
        """P1-3 验收断言: 标准引擎（本地 BERT 在场）下「计算走线宽度」
        置信度 ≥ 0.40，直接执行而不降级追问"""
        engine = NLUEngine(api_key="")
        engine._embedding_failed = True
        name, confidence, _ = engine.classify("计算走线宽度")
        assert name == "PCB_ANALYSIS"
        assert confidence >= 0.40

    def test_registry_keyword_present_in_descriptors(self, engine_keyword_only):
        """P1-3: 补充关键词确实进入评分表（「走线宽度」来自 ToolRegistry）"""
        from src.agent.tools import ToolRegistry
        assert "走线宽度" in ToolRegistry.get_keywords_by_intent("PCB_ANALYSIS")
        pcb_desc = engine_keyword_only._descriptors["PCB_ANALYSIS"]
        assert "走线宽度" in pcb_desc.keywords


# ——— P1-4: 2 字符裸关键词词边界 ———


class TestP1ShortKeywordBoundary:
    def test_short_keyword_left_boundary_semantics(self):
        """P1-4: 「MP」命中型号前缀（MP1584）、不命中型号中段（TMP36）；
        3 字符以上编号词（485）维持原子串口径"""
        assert _keyword_in_text("MP", "U1 MP1584EN 3A")
        assert not _keyword_in_text("MP", "U2 TMP36 模拟温度传感器")
        assert _keyword_in_text("485", "U3 MAX485 收发器")

    def _tmp36_bom(self):
        return [
            BOMItem(reference="U1", value="", package="LQFP-48",
                    part_number="STM32F103C8T6", description="MCU", quantity=1),
            BOMItem(reference="U2", value="TMP36", package="TO-92",
                    part_number="TMP36", description="模拟温度传感器", quantity=1),
            BOMItem(reference="R1", value="10k", package="0603",
                    part_number="", description="电阻", quantity=1),
        ]

    def test_tmp36_bom_not_buck(self):
        """P1-4 负样本: STM32+TMP36 的 BOM 不应命中 Buck 降压模板
        （修复前「MP」裸子串命中 TMP36 → 62% 匹配度 + 误报缺失元件）"""
        matches = DesignTemplateEngine().match(self._tmp36_bom())
        buck = [m for m in matches if m.template_name == "Buck 降压电路"]
        assert buck == []

    def test_tmp36_alone_not_buck(self):
        """P1-4 负样本: 仅 TMP36 也不得触发 Buck 模板"""
        items = [BOMItem(reference="U2", value="TMP36", package="TO-92",
                         part_number="TMP36FT9", description="温度传感器",
                         quantity=1)]
        matches = DesignTemplateEngine().match(items)
        assert [m for m in matches
                if m.template_name == "Buck 降压电路"] == []

    def test_mp_series_still_matches_buck(self):
        """P1-4 正样本: MP1584 等真实 MPS 芯片仍应命中 Buck 模板
        （左词边界保留家族前缀命中能力）"""
        items = [
            BOMItem(reference="U1", value="", package="SOT-23",
                    part_number="MP1584EN", description="电源转换芯片 3A",
                    quantity=1),
            BOMItem(reference="L1", value="10uH", package="CD54",
                    part_number="", description="功率电感", quantity=1),
            BOMItem(reference="C1", value="100uF", package="SMD",
                    part_number="", description="电解电容", quantity=1),
            BOMItem(reference="R1", value="10k", package="0603",
                    part_number="", description="电阻", quantity=1),
        ]
        matches = DesignTemplateEngine().match(items)
        buck = [m for m in matches if m.template_name == "Buck 降压电路"]
        assert len(buck) == 1
        assert any("MP" in c for c in buck[0].matched_components)

    def test_bq_series_still_matches_battery(self):
        """P1-4: 同为 2 字符家族前缀的「BQ」不受词边界影响
        （BQ25895 仍命中锂电池供电系统模板）"""
        items = [BOMItem(reference="U1", value="", package="VQFN",
                         part_number="BQ25895", description="充电管理",
                         quantity=1)]
        matches = DesignTemplateEngine().match(items)
        assert any(m.template_name == "锂电池供电系统" for m in matches)
