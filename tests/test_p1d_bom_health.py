"""P1-19 回归（验收 2026-10-24）：单物料网络失败降级 + 有界并发 + 端点兜底。

修复前：bom_health.check() 里一个物料的网络异常中断整张 BOM 的健康检查，
REST /health/check 无兜底直接 500；串行逐个请求最坏 ~21 分钟。
负样本断言方向：坏物料不拖垮其余物料的结果，整体不抛异常、端点不 500。
"""

import pytest
from fastapi.testclient import TestClient

from src.bom.parser import BOMItem
from src.supply.bom_health import BOMHealthChecker
from src.supply.lcsc_client import ComponentInfo, SearchResult


class _StubClient:
    """is_available 可按型号注入失败的客户端桩（不触网）。"""

    def __init__(self, fail_parts=(), stock_by_part=None):
        self.fail_parts = set(fail_parts)
        self.stock_by_part = dict(stock_by_part or {})
        self.queries: list[str] = []

    def is_available(self, part: str):
        self.queries.append(part)
        if part in self.fail_parts:
            raise ConnectionError(f"network down: {part}")
        stock = self.stock_by_part.get(part, 1000)
        return ComponentInfo(lcsc_part="C1", mfr_part=part, stock=stock, min_price=0.1)

    def search_by_part(self, keyword: str, package: str = "") -> SearchResult:
        return SearchResult(keyword=keyword, items=[])


def _item(ref: str, part: str, qty: int = 1) -> BOMItem:
    return BOMItem(reference=ref, value="x", package="0603", part_number=part, quantity=qty)


class TestPerItemDegradation:
    def test_single_network_failure_does_not_abort_batch(self):
        """一个物料网络失败：其余物料结果必须完整，总体不抛异常。"""
        client = _StubClient(fail_parts=["BAD_PART"])
        checker = BOMHealthChecker(client)
        report = checker.check([
            _item("R1", "GOOD_A"),
            _item("U1", "BAD_PART"),
            _item("R2", "GOOD_B"),
        ])
        assert report.in_stock_count == 2
        assert [w["reference"] for w in report.network_errors] == ["U1"]
        assert report.network_errors[0]["part"] == "BAD_PART"
        assert "network down" in report.network_errors[0]["error"]

    def test_network_error_not_misclassified(self):
        """失败物料不得冒充「有货/缺货/未收录」任一结论。"""
        checker = BOMHealthChecker(_StubClient(fail_parts=["BAD_PART"]))
        report = checker.check([_item("U1", "BAD_PART")])
        assert "U1" not in report.not_found
        assert report.out_of_stock == []
        assert report.low_stock == []
        assert report.in_stock_count == 0
        assert report.health_score < 100.0   # 查不出 ≠ 满分健康

    def test_all_items_failing_still_returns_report(self):
        client = _StubClient(fail_parts={"A", "B", "C"})
        checker = BOMHealthChecker(client)
        report = checker.check([_item("R1", "A"), _item("R2", "B"), _item("R3", "C")])
        assert len(report.network_errors) == 3
        assert report.in_stock_count == 0

    def test_duplicate_parts_share_one_query(self):
        """同型号多个位号只查一次（并发压缩时长的前提，也是回归锚点）。"""
        client = _StubClient()
        checker = BOMHealthChecker(client)
        checker.check([_item("R1", "SAME"), _item("R2", "SAME"), _item("R3", "SAME")])
        assert client.queries == ["SAME"]

    def test_mixed_results_keep_per_item_classification(self):
        client = _StubClient(
            fail_parts=["BAD"],
            stock_by_part={"IN": 1000, "LOW": 50, "OUT": 0},
        )
        checker = BOMHealthChecker(client)
        report = checker.check([
            _item("R1", "IN"), _item("U1", "BAD"), _item("R2", "LOW"), _item("C1", "OUT"),
        ])
        assert report.in_stock_count == 1
        assert [m["reference"] for m in report.low_stock] == ["R2"]
        assert [m["reference"] for m in report.out_of_stock] == ["C1"]
        assert [w["reference"] for w in report.network_errors] == ["U1"]

    def test_format_report_lists_network_errors(self):
        checker = BOMHealthChecker(_StubClient(fail_parts=["BAD"]))
        report = checker.check([_item("U1", "BAD")])
        text = BOMHealthChecker.format_report(report)
        assert "网络查询失败" in text
        assert "U1" in text


class TestEstimateCostDegraded:
    def test_failed_item_skipped_not_fatal(self):
        """整 BOM 成本估值：失败物料只跳过该项，不炸整个估值。"""
        client = _StubClient(fail_parts=["BAD"])
        checker = BOMHealthChecker(client)
        items = [_item("R1", "GOOD", qty=10), _item("U1", "BAD", qty=10)]
        cost = checker.estimate_total_cost(items, quantity=1)
        assert cost == 1.0    # 只有 GOOD 计入（0.1 × 10），失败项跳过


class TestEndpointFallback:
    def test_health_check_endpoint_returns_ok_false_not_500(self, monkeypatch):
        """调用端点兜底：check_bom_health 抛未预期异常 → ok=False 而非 500。"""
        from src.api.server import app
        client = TestClient(app, base_url="http://127.0.0.1:8710")

        def _boom(self):
            raise RuntimeError("health engine exploded")

        monkeypatch.setattr("src.core.controller.AppController.check_bom_health", _boom)
        resp = client.post("/api/v1/health/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert "exploded" in data["report"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
