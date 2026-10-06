"""BootSequencer 单元测试 — 两段式启动的步骤状态机

守住三件事:
  1. ready 只看 critical 步骤 —— 知识库预热不该把用户挡在小窗外；
  2. failed 也算结束 —— 附属功能失败绝不能让人永远卡在加载界面；
  3. step() 上下文管理器吞异常但记账（启动步骤失败不致命）。
"""

import json
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.boot import (  # noqa: E402
    BootSequencer,
    BootStep,
    DEFAULT_STEPS,
    DONE,
    FAILED,
    PENDING,
    RUNNING,
)


def _seq():
    return BootSequencer((
        BootStep("services", "注册热键", critical=True),
        BootStep("knowledge", "预热知识库", critical=False),
    ))


class TestInitialState:
    def test_not_started(self):
        b = _seq()
        st = b.status()
        assert st["started"] is False
        assert st["ready"] is False
        assert st["warm"] is False
        assert st["percent"] == 0
        assert st["elapsed_ms"] == 0

    def test_first_text_is_first_step(self):
        b = _seq()
        assert b.status()["text"] == "注册热键"
        assert b.status()["step"] == "services"

    def test_default_steps_shape(self):
        assert [s.key for s in DEFAULT_STEPS] == ["services", "knowledge"]
        assert [s.critical for s in DEFAULT_STEPS] == [True, False]


class TestProgression:
    def test_ready_only_needs_critical(self):
        b = _seq()
        b.start()
        b.begin("services")
        b.done("services")
        st = b.status()
        assert st["ready"] is True
        assert st["warm"] is False            # 知识库还在后面
        assert st["text"] == "预热知识库"      # 文案自动跟到下一步
        assert b.started is True

    def test_warm_after_everything(self):
        b = _seq()
        b.start()
        b.done("services")
        b.done("knowledge")
        st = b.status()
        assert st["warm"] is True and st["ready"] is True
        assert st["percent"] == 100
        assert st["text"] == "即将就绪"

    def test_failed_critical_still_counts_as_ready(self):
        """关键步骤失败也必须放行 —— 否则小窗永远展不开。"""
        b = _seq()
        b.start()
        b.fail("services", RuntimeError("no hotkey"))
        b.done("knowledge")
        st = b.status()
        assert st["ready"] is True and st["warm"] is True
        assert st["errors"] == {"services": "no hotkey"}
        assert [s["state"] for s in st["steps"]] == [FAILED, DONE]

    def test_done_does_not_overwrite_failure(self):
        b = _seq()
        b.start()
        b.fail("services", "boom")
        b.done("services")
        assert b.status()["steps"][0]["state"] == FAILED

    def test_begin_is_not_reopened_after_finish(self):
        b = _seq()
        b.start()
        b.done("services")
        b.begin("services")
        assert b.status()["steps"][0]["state"] == DONE

    def test_out_of_order_is_fine(self):
        b = _seq()
        b.start()
        b.done("knowledge")
        assert b.status()["ready"] is False
        b.done("services")
        assert b.status()["ready"] is True

    def test_unknown_key_is_tolerated(self):
        b = _seq()
        b.start()
        b.begin("nope")
        b.done("nope")
        b.fail("nope", "x")
        assert b.status()["steps"][0]["state"] == PENDING

    def test_start_is_idempotent(self):
        b = _seq()
        b.start()
        first = b.status()["elapsed_ms"]
        b.start()
        assert b.status()["elapsed_ms"] >= first


class TestStepContext:
    def test_records_done(self):
        b = _seq()
        with b.step("services"):
            pass
        assert b.status()["steps"][0]["state"] == DONE

    def test_swallows_exception_but_records_it(self):
        b = _seq()
        with b.step("services"):
            raise ValueError("tray exploded")
        st = b.status()
        assert st["steps"][0]["state"] == FAILED
        assert "tray exploded" in st["errors"]["services"]
        # 异常不冒泡 → 这里仍然能继续执行

    def test_running_state_visible_inside_block(self):
        b = _seq()
        seen = {}
        with b.step("services"):
            seen = b.status()
        assert seen["step"] == "services"
        assert seen["steps"][0]["state"] == RUNNING
        assert seen["percent"] == 0


class TestStatusContract:
    def test_json_serialisable(self):
        b = _seq()
        b.start()
        b.done("services")
        assert json.loads(json.dumps(b.status()))["ready"] is True

    def test_no_critical_steps_is_immediately_ready(self):
        b = BootSequencer((BootStep("knowledge", "预热", critical=False),))
        assert b.ready is True
        assert b.warm is False

    def test_empty_steps_do_not_divide_by_zero(self):
        b = BootSequencer(())
        st = b.status()
        assert st["percent"] == 0 and st["warm"] is True


class TestThreadSafety:
    def test_parallel_writers_keep_counts(self):
        steps = tuple(BootStep(f"s{i}", f"step {i}", critical=True) for i in range(60))
        b = BootSequencer(steps)
        b.start()

        def worker(i):
            with b.step(f"s{i}"):
                pass

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(60)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        st = b.status()
        assert st["warm"] is True and st["ready"] is True
        assert st["percent"] == 100
        assert all(s["state"] == DONE for s in st["steps"])
