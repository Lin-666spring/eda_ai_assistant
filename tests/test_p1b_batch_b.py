"""批次B P1 修复回归测试（验收 2026-10-24）。

钉死验收报告第三节以下条目（负样本断言优先——不应崩溃 / 不应误报 / 不应假通过）：
- P1-5  analyze_image 在 Agent Loop 必 TypeError（dispatch 缺参数特判）；
        verify_suggestion 的 params=None 同款隐患；function definitions 冒烟
- P1-6  design_scorer 字典重复键「封装一致性」→ DFM 维度永远收不到该类违规
- P1-7  electrical_check 串扰检测传编造值 span*2 当间距 → 恒通过（虚假安全）
- P1-8  persistence `with conn` 只管事务不管 close
- P1-9  controller 历史合并的 generation 复核在锁外（TOCTOU 旧轮次复活）
- P1-10 persistence.save_all 带 workspaces 裸 INSERT 撞主键 → 整体回滚
- P1-12 file_watcher 前置防抖 → 写一半就回调、写完反被抑制
- P1-20 CSV 导出无公式注入防护
"""

import csv
import sqlite3
import sys
import threading
import time
import json
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.core.controller import AppController
from src.bom.parser import BOMItem


@pytest.fixture
def controller():
    """无 AI 的 controller（本地模式，conftest 已隔离真实 API Key）"""
    return AppController(api_key="")


@pytest.fixture
def controller_with_data(controller):
    controller.context.bom_items = [
        BOMItem(reference="R1", value="10kΩ", package="0603",
                part_number="C25804", description="贴片电阻", quantity=1),
        BOMItem(reference="C1", value="100nF", package="0603",
                part_number="C1588", description="贴片电容", quantity=1),
    ]
    return controller


@pytest.fixture
def store_fixture(tmp_path):
    from src.core.persistence import SessionStore
    return SessionStore(db_path=tmp_path / "sessions.db")


# ═══════════════════════════════════════════════════════
#  P1-5 dispatch 参数适配
# ═══════════════════════════════════════════════════════


class TestP1_5DispatchParams:
    def test_analyze_image_with_image_data_reaches_vision(self, controller, monkeypatch):
        """schema 参数 image_data 应适配到 _analyze_image，不再 TypeError"""
        seen = {}

        def fake_vision(text, image_b64):
            seen["args"] = (text, image_b64)
            return "VISION_OK"

        monkeypatch.setattr(controller, "_analyze_image", fake_vision)
        result = controller._dispatch_operation(
            "analyze_image", {"image_data": "aGVsbG8=", "text": "找布局缺陷"},
        )
        assert result == "VISION_OK"
        assert seen["args"] == ("找布局缺陷", "aGVsbG8=")

    def test_analyze_image_without_image_data_returns_guidance(self, controller):
        """缺 image_data：给引导文案而不是崩（修复前此处必 TypeError）"""
        result = controller._dispatch_operation("analyze_image", {})
        assert isinstance(result, str)
        assert "图片" in result

    def test_dispatch_none_params_no_crash(self, controller):
        """LLM arguments 解析出 None 时归一成 dict，不得 AttributeError"""
        for op in ("verify_suggestion", "rag_query", "analyze_image"):
            result = controller._dispatch_operation(op, None)
            assert isinstance(result, str) and result, op

    def test_local_keyword_route_to_analyze_image_no_crash(self, controller):
        """本地关键词路由（"图片"）命中 analyze_image：零参调用给引导不崩"""
        result = controller._local_fallback("帮我看一下这张图片")
        assert "图片" in result

    def test_function_definitions_dispatch_smoke(self, controller_with_data, monkeypatch):
        """验收报告§五.6：每个 function definition 用 schema 合成参数冒烟
        _dispatch_operation —— 参数化工具缺 dispatch 适配（P1-5 类 TypeError）
        在此处直接红灯。网络/落盘/重索引终端打桩，其余走真实 dispatch。"""
        from src.agent.tools import ToolRegistry

        controller = controller_with_data
        # 网络终端（LCSC 健康检查）与落盘终端（导出到仓库 output/）打桩
        monkeypatch.setattr(controller, "check_bom_health",
                            lambda: "HEALTH_OK", raising=False)
        monkeypatch.setattr(controller, "query_knowledge_base",
                            lambda query="": "KB_OK", raising=False)
        monkeypatch.setattr(controller, "generate_html_bom",
                            lambda path=None: "HTML_OK", raising=False)
        monkeypatch.setattr(controller, "export_bom_csv",
                            lambda path=None: "CSV_OK", raising=False)

        def synth(prop):
            t = prop.get("type")
            if t == "number":
                return 1.0
            if t == "integer":
                return 1
            if t == "boolean":
                return False
            if "base64" in str(prop.get("description", "")):
                return "aGVsbG8="
            return "冒烟参数"

        funcs = ToolRegistry.get_function_definitions()
        assert funcs, "function definitions 不应为空"
        for f in funcs:
            name = f["function"]["name"]
            props = f["function"]["parameters"]["properties"]
            args = {k: synth(v) for k, v in props.items()}
            # 修复前 analyze_image 在此抛 TypeError —— 不 catch，让它炸出来
            result = controller._dispatch_operation(name, args)
            assert isinstance(result, str) and result, name


# ═══════════════════════════════════════════════════════
#  P1-6 design_scorer 重复键
# ═══════════════════════════════════════════════════════


class TestP1_6DesignScorerDfm:
    def _pkg_violation(self):
        from src.rules.checker import RuleViolation, RuleSeverity
        return RuleViolation(
            rule_name="封装一致性检查", description="型号 [STM32F103C8T6] 出现多种封装",
            severity=RuleSeverity.WARNING, location="U1",
            suggestion="统一封装", theory="同型号多封装易误贴",
        )

    def test_package_consistency_reaches_dfm(self):
        """DFM 维度必须收到封装一致性违规（修复前恒 100 分 0 违规）"""
        from src.core.design_scorer import DesignScorer
        report = DesignScorer().score([self._pkg_violation()], [])
        dfm = report.dimensions["dfm"]
        assert dfm.violation_count >= 1
        assert dfm.score < 100.0
        assert any("封装一致性" in i["rule_name"] for i in dfm.top_issues)

    def test_package_consistency_also_counts_cost(self):
        """双维度归属：cost 的 0.5 权重判定也保留生效"""
        from src.core.design_scorer import DesignScorer
        report = DesignScorer().score([self._pkg_violation()], [])
        cost = report.dimensions["cost"]
        assert cost.violation_count >= 1
        assert cost.score < 100.0

    def test_dimension_weights_kept_distinct(self):
        """dfm(1.5) 比 cost(0.5) 权重高 —— 同一违规 dfm 扣分更多"""
        from src.core.design_scorer import DesignScorer
        report = DesignScorer().score([self._pkg_violation()], [])
        assert report.dimensions["dfm"].score < report.dimensions["cost"].score

    def test_multi_dimension_map_shape(self):
        from src.core.design_scorer import RULE_DIMENSION_MAP
        assert RULE_DIMENSION_MAP["封装一致性"] == (("dfm", 1.5), ("cost", 0.5))


# ═══════════════════════════════════════════════════════
#  P1-7 串扰真实间距
# ═══════════════════════════════════════════════════════


def _make_pcb(traces):
    from src.pcb.models import PCBData
    return PCBData(format="test", traces=traces)


class TestP1_7CrosstalkSpacing:
    def _bom(self):
        return [BOMItem(reference="R1", value="10kΩ", package="0603",
                        part_number="C25804", description="贴片电阻", quantity=1)]

    def _run(self, traces):
        from src.core.electrical_check import run_electrical_health_check
        return json.loads(run_electrical_health_check(_make_pcb(traces), self._bom()))

    @staticmethod
    def _trace(net, y, width=0.3):
        from src.pcb.models import PCBTrace
        return PCBTrace(net_name=net, layer="TopLayer", width_mm=width,
                        segments=[(0.0, y, 10.0, y)])

    def test_violating_2w_spacing_is_reported(self):
        """间距 0.5mm < 2W(0.6mm) → 必须产出串扰问题（修复前恒通过）"""
        result = self._run([self._trace("CLK", 0.0), self._trace("DATA", 0.5)])
        crosstalk = result["details"]["crosstalk"]
        assert crosstalk, "违反 2W 的走线对未报串扰（虚假安全结论）"
        assert any("CLK" in s and "DATA" in s for s in crosstalk)
        assert any("实测间距" in s for s in crosstalk), "报告应给出实测间距而非编造值"

    def test_crossing_traces_reported(self):
        """不同网络走线几何相交 → 间距 0，必须报串扰"""
        from src.pcb.models import PCBTrace
        vertical = PCBTrace(net_name="INT", layer="TopLayer", width_mm=0.3,
                            segments=[(5.0, -5.0, 5.0, 5.0)])
        result = self._run([self._trace("CLK", 0.0), vertical])
        assert any("CLK" in s and "INT" in s for s in result["details"]["crosstalk"])

    def test_compliant_spacing_not_reported(self):
        """间距 3mm ≥ 3W(0.9mm) → 不误报"""
        result = self._run([self._trace("CLK", 0.0), self._trace("DATA", 3.0)])
        assert result["details"]["crosstalk"] == []

    def test_same_net_pair_skipped(self):
        """同网络走线等电位/物理相连，间距不构成串扰风险，不得误报"""
        result = self._run([self._trace("VCC", 0.0), self._trace("VCC", 0.1)])
        assert result["details"]["crosstalk"] == []

    def test_missing_geometry_is_indeterminate_not_pass(self):
        """缺几何数据：如实记"无法判定"，绝不假通过"所有检查通过\""""
        from src.pcb.models import PCBTrace
        t1 = PCBTrace(net_name="CLK", layer="TopLayer", width_mm=0.3, segments=[])
        t2 = PCBTrace(net_name="DATA", layer="TopLayer", width_mm=0.3, segments=[])
        result = self._run([t1, t2])
        crosstalk = result["details"]["crosstalk"]
        assert any("无法判定" in s for s in crosstalk)
        assert "所有电气检查通过" not in json.dumps(result, ensure_ascii=False)
        assert "所有电气检查通过" not in result["markdown"]


# ═══════════════════════════════════════════════════════
#  P1-8 连接 close 语义
# ═══════════════════════════════════════════════════════


class TestP1_8ConnectionClose:
    def test_every_opened_connection_is_closed(self, tmp_path, monkeypatch):
        import src.core.persistence as persistence

        opened, closed = [], []
        real_connect = sqlite3.connect

        class TrackedConn(sqlite3.Connection):
            def close(self):
                closed.append(self)
                super().close()

        def tracking_connect(path, *args, **kwargs):
            kwargs["factory"] = TrackedConn
            conn = real_connect(path, *args, **kwargs)
            opened.append(conn)
            return conn

        monkeypatch.setattr(persistence.sqlite3, "connect", tracking_connect)

        store = persistence.SessionStore(db_path=tmp_path / "t.db")
        store.save_state("k", "v")
        assert store.load_state("k") == "v"
        assert store.load_all()

        assert opened, "应至少打开过一次连接"
        assert len(closed) == len(opened), "每个打开的连接都应被显式 close"

    def test_transaction_rollback_semantics_unchanged(self, store_fixture):
        """close 封装不得改变事务行为：约束冲突照旧抛异常、回滚不损库"""
        import sqlite3
        store_fixture.save_assistant("a1", "eda-general", "助手")
        store_fixture.save_conversation("c1", "a1", "对话")
        with pytest.raises(sqlite3.IntegrityError):
            store_fixture.save_message("missing_conv", "user", "x")  # FK 约束
        assert store_fixture.load_messages("c1") == []
        assert len(store_fixture.load_conversations("a1")) == 1


# ═══════════════════════════════════════════════════════
#  P1-9 历史合并 TOCTOU
# ═══════════════════════════════════════════════════════


class _HookedLock:
    """带 acquire 钩子的锁替身 —— 钩子在真正拿锁前运行，
    用于确定性复现「复核通过之后、拿锁之前」的竞态空档。"""

    def __init__(self, inner, hook):
        self._inner = inner
        self._hook = hook

    def acquire(self, *args, **kwargs):
        self._hook()
        return self._inner.acquire(*args, **kwargs)

    def release(self):
        self._inner.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


class TestP1_9HistoryMergeTOCTOU:
    def _controller_with_shared(self, controller):
        from unittest.mock import MagicMock
        controller.agent = MagicMock()
        controller.agent.api_key = "sk-test"
        controller.agent.base_url = ""
        controller.agent.model = "test-model"
        controller.agent.provider_name = "deepseek"
        controller.agent.get_history.return_value = []
        return controller.agent

    def test_stale_merge_discarded_when_clear_races_at_lock(self, controller):
        """清空对话恰好发生在复核之后、拿锁之前的空档 → 旧轮次不得复活。
        （修复前复核在锁外，此确定性竞态下 extend_history 会被照常调用）"""
        shared = self._controller_with_shared(controller)

        fired = {"once": False}

        def hook():
            if not fired["once"]:
                fired["once"] = True
                controller.clear_conversation()  # 模拟并发清空挤进空档

        controller._history_lock = _HookedLock(threading.Lock(), hook)

        with controller._llm_session() as session:
            session.extend_history([{"role": "user", "content": "迟到的轮次"}])

        shared.extend_history.assert_not_called()

    def test_merge_still_happens_without_race(self, controller):
        """无竞态时正常合并 —— 修复不得牺牲正常路径"""
        shared = self._controller_with_shared(controller)
        with controller._llm_session() as session:
            session.extend_history([{"role": "user", "content": "新轮次"}])
        shared.extend_history.assert_called_once_with(
            [{"role": "user", "content": "新轮次"}])


# ═══════════════════════════════════════════════════════
#  P1-10 save_all 工作区主键冲突
# ═══════════════════════════════════════════════════════


class TestP1_10SaveAllWorkspaces:
    def test_save_all_with_existing_default_workspace_no_rollback(self, store_fixture):
        """快照永远带 ws_default（_ensure_db 已创建）—— upsert 后整个
        退出保存不再回滚，assistants / app_state 必须落库。"""
        from src.core.persistence import DEFAULT_WORKSPACE_ID

        workspaces = [
            {"workspace_id": DEFAULT_WORKSPACE_ID, "name": "默认工作区"},
            {"workspace_id": "w1", "name": "项目A", "path": "C:/proj/a"},
        ]
        assistants = [{"instanceId": "a1", "typeId": "eda-general", "name": "EDA助手"}]
        conversations = {"a1": [{"id": "c1", "title": "对话1"}]}

        # 修复前此处抛 IntegrityError → 整个事务回滚
        store_fixture.save_all(assistants, conversations, "a1", "c1",
                               workspaces=workspaces,
                               active_workspace=DEFAULT_WORKSPACE_ID)

        data = store_fixture.load_all()
        assert len(data["assistants"]) == 1, "save_all 整体回滚：assistants 丢失"
        assert data["active_workspace"] == DEFAULT_WORKSPACE_ID
        ws = {w["workspace_id"]: w for w in data["workspaces"]}
        assert set(ws) == {DEFAULT_WORKSPACE_ID, "w1"}
        assert ws["w1"]["name"] == "项目A"

    def test_save_all_upserts_existing_workspace(self, store_fixture):
        from src.core.persistence import DEFAULT_WORKSPACE_ID
        store_fixture.save_workspace(DEFAULT_WORKSPACE_ID, "旧名字", "", 0)
        store_fixture.save_all(
            [], {}, None, None,
            workspaces=[{"workspace_id": DEFAULT_WORKSPACE_ID, "name": "新名字"}],
        )
        ws = {w.workspace_id: w for w in store_fixture.load_workspaces()}
        assert ws[DEFAULT_WORKSPACE_ID].name == "新名字"

    def test_save_all_without_workspaces_still_works(self, store_fixture):
        """不带 workspaces 的旧调用口径保持不变"""
        store_fixture.save_all(
            [{"instanceId": "a1", "typeId": "t", "name": "A"}],
            {"a1": [{"id": "c1", "title": "T"}]}, "a1", "c1",
        )
        assert len(store_fixture.load_all()["assistants"]) == 1


# ═══════════════════════════════════════════════════════
#  P1-12 trailing 防抖
# ═══════════════════════════════════════════════════════


class TestP1_12TrailingDebounce:
    DEBOUNCE = 0.25

    def _handler(self, calls):
        from src.core.file_watcher import PCBFileHandler
        return PCBFileHandler(lambda src: calls.append((time.perf_counter(), src)),
                              debounce_sec=self.DEBOUNCE)

    @staticmethod
    def _event(path):
        return SimpleNamespace(is_directory=False, src_path=str(path))

    def test_continuous_writes_fire_once_after_last(self, tmp_path):
        """持续写入（间隔 < 防抖窗口）只触发一次，且在最后一次写入之后。
        修复前：首个事件立即回调（文件写一半），写完的事件反被抑制。"""
        calls = []
        handler = self._handler(calls)
        target = tmp_path / "board.epro2"

        event_times = []
        for _ in range(5):
            handler.on_modified(self._event(target))
            event_times.append(time.perf_counter())
            time.sleep(0.1)  # < DEBOUNCE，全部落在同一静默期

        time.sleep(self.DEBOUNCE + 0.5)  # 等静默期结束
        assert len(calls) == 1, f"应只触发一次，实际 {len(calls)} 次"
        assert calls[0][0] >= event_times[-1], "回调必须发生在最后一次写入之后"

    def test_new_write_session_fires_again(self, tmp_path):
        """静默期结束后又有一次写入 → 再触发一次（防抖不吞新写入会话）"""
        calls = []
        handler = self._handler(calls)
        target = tmp_path / "board.epro2"

        handler.on_modified(self._event(target))
        time.sleep(self.DEBOUNCE + 0.5)
        handler.on_modified(self._event(target))
        time.sleep(self.DEBOUNCE + 0.5)

        assert len(calls) == 2

    def test_non_pcb_file_ignored(self, tmp_path):
        calls = []
        handler = self._handler(calls)
        handler.on_modified(self._event(tmp_path / "readme.txt"))
        time.sleep(self.DEBOUNCE + 0.4)
        assert calls == []

    def test_cancel_pending_prevents_callback(self, tmp_path):
        calls = []
        handler = self._handler(calls)
        handler.on_modified(self._event(tmp_path / "board.epro2"))
        handler.cancel_pending()
        time.sleep(self.DEBOUNCE + 0.4)
        assert calls == []


# ═══════════════════════════════════════════════════════
#  P1-20 CSV 公式注入防护
# ═══════════════════════════════════════════════════════


class TestP1_20CsvFormulaInjection:
    def test_malicious_cells_neutralized(self, controller_with_data, tmp_path):
        controller_with_data.context.bom_items = [
            BOMItem(reference="R1", value="10kΩ", package="0603",
                    part_number="C25804", description="贴片电阻",
                    quantity=1, manufacturer="YAGEO"),
            BOMItem(reference="X1", value="=cmd|' /C calc'!A0", package="0603",
                    part_number="@SUM(1)", description="+HYPERLINK(http://evil)",
                    quantity=2, manufacturer="-evil\t Industries"),
        ]
        out = tmp_path / "bom.csv"
        result = controller_with_data.export_bom_csv(str(out))
        assert "已导出" in result

        with open(out, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        assert rows[0][0] == "位号"  # 表头不受影响
        normal = rows[1]
        assert normal[0] == "R1" and normal[1] == "10kΩ" and normal[2] == "0603"
        assert normal[6] == "YAGEO"

        malicious = rows[2]
        assert malicious[1].startswith("'=") and "cmd" in malicious[1]
        assert malicious[3].startswith("'@")
        assert malicious[4].startswith("'+")
        assert malicious[6].startswith("'-")
        # 数值列（数量）不转义
        assert malicious[5] == "2"

    def test_tab_and_cr_prefixes_escaped(self, controller_with_data, tmp_path):
        controller_with_data.context.bom_items = [
            BOMItem(reference="\tTAB", value="\rCR",
                    package="0603", part_number="C1", quantity=1),
        ]
        out = tmp_path / "bom.csv"
        controller_with_data.export_bom_csv(str(out))
        with open(out, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[1][0].startswith("'")
        assert rows[1][1].startswith("'")
