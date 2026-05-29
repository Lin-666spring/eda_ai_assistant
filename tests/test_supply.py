"""供应链模块测试 — LCSC 客户端 + BOM 健康检查"""

from unittest.mock import MagicMock, patch

import pytest

from src.supply.lcsc_client import (
    ComponentInfo, SearchResult, LcscSearchClient, LCSCClient, JlcSearchClient,
)
from src.supply.bom_health import BOMHealthChecker, BOMHealthReport
from src.bom.parser import BOMItem
from src.exceptions import SupplyAPIError, SupplyAuthError


# ══════════════════════════════════════════════════════
#  ComponentInfo / SearchResult
# ══════════════════════════════════════════════════════

class TestComponentInfo:
    def test_in_stock_positive(self):
        info = ComponentInfo(stock=100)
        assert info.in_stock

    def test_in_stock_zero(self):
        info = ComponentInfo(stock=0)
        assert not info.in_stock

    def test_price_display_with_prices(self):
        info = ComponentInfo(price_list=[
            {"qty": 1, "price": 0.35},
            {"qty": 100, "price": 0.28},
        ])
        assert "0.35" in info.price_display

    def test_price_display_empty(self):
        info = ComponentInfo()
        assert info.price_display == "N/A"

    def test_defaults(self):
        info = ComponentInfo()
        assert info.lcsc_part == ""
        assert info.availability == "Unknown"


class TestSearchResult:
    def test_empty_result(self):
        r = SearchResult(keyword="STM32")
        assert r.total == 0
        assert r.items == []

    def test_with_items(self):
        r = SearchResult(keyword="STM32", total=2, items=[
            ComponentInfo(lcsc_part="C12345"),
            ComponentInfo(lcsc_part="C67890"),
        ])
        assert len(r.items) == 2
        assert r.total == 2


# ══════════════════════════════════════════════════════
#  LCSCClient (official API)
# ══════════════════════════════════════════════════════

class TestLCSCClient:
    def test_not_configured_by_default(self):
        client = LCSCClient()
        assert not client.is_configured

    def test_configured_with_keys(self):
        client = LCSCClient(api_key="key123", api_secret="secret456")
        assert client.is_configured

    def test_search_without_auth_raises(self):
        client = LCSCClient()
        with pytest.raises(SupplyAuthError):
            client.search("STM32")

    def test_detail_without_auth_raises(self):
        client = LCSCClient()
        with pytest.raises(SupplyAuthError):
            client.get_detail("C12345")

    def test_sign_generates_headers(self):
        client = LCSCClient(api_key="test_key", api_secret="test_secret")
        headers = client._sign()
        assert "api_key" in headers
        assert headers["api_key"] == "test_key"
        assert "nonce" in headers
        assert len(headers["nonce"]) == 16
        assert "timestamp" in headers
        assert "sign" in headers
        assert len(headers["sign"]) == 32  # MD5 hex

    @patch("src.supply.lcsc_client.requests.Session.get")
    def test_search_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "list": [
                    {
                        "product_code": "C12345",
                        "mfr_part": "STM32F103C8T6",
                        "brand_name": "ST",
                        "package": "LQFP-48",
                        "describe": "MCU 32-bit",
                        "stock_number": 500,
                    }
                ],
                "total": 1,
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = LCSCClient(api_key="k", api_secret="s")
        result = client.search("STM32")
        assert result.total == 1
        item = result.items[0]
        assert item.lcsc_part == "C12345"
        assert item.mfr_part == "STM32F103C8T6"
        assert item.in_stock

    @patch("src.supply.lcsc_client.requests.Session.get")
    def test_search_http_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.ConnectionError("timeout")
        client = LCSCClient(api_key="k", api_secret="s")
        with pytest.raises(SupplyAPIError):
            client.search("STM32")

    @patch("src.supply.lcsc_client.requests.Session.get")
    def test_detail_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "product_code": "C12345",
                "mfr_part": "STM32F103",
                "stock_number": 200,
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = LCSCClient(api_key="k", api_secret="s")
        info = client.get_detail("C12345")
        assert info is not None
        assert info.lcsc_part == "C12345"


# ══════════════════════════════════════════════════════
#  JlcSearchClient (public fallback)
# ══════════════════════════════════════════════════════

class TestJlcSearchClient:
    @patch("src.supply.lcsc_client.requests.get")
    def test_search_returns_items(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"lcsc": "C12345", "mfr": "STM32", "stock": 100, "price": 0.5},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        client = JlcSearchClient()
        result = client.search("STM32")
        assert result.total == 1
        assert result.items[0].lcsc_part == "C12345"

    @patch("src.supply.lcsc_client.requests.get")
    def test_search_http_error(self, mock_get):
        import requests as req
        mock_get.side_effect = req.ConnectionError("timeout")
        client = JlcSearchClient()
        with pytest.raises(SupplyAPIError):
            client.search("STM32")


# ══════════════════════════════════════════════════════
#  LcscSearchClient (unified)
# ══════════════════════════════════════════════════════

class TestLcscSearchClient:
    def test_init_creates_cache_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.supply.lcsc_client.SETTINGS_DIR", tmp_path)
        client = LcscSearchClient()
        assert (tmp_path / "lcsc_cache").is_dir()

    def test_search_by_part_fallback(self):
        client = LcscSearchClient()
        client._cache_get = MagicMock(return_value=None)  # skip cache
        item = ComponentInfo(lcsc_part="C12345", mfr_part="STM32", stock=500)
        client._public.search = MagicMock(return_value=SearchResult(
            keyword="STM32", total=1, items=[item],
        ))
        result = client.search_by_part("STM32")
        assert result.total == 1
        assert result.items[0].lcsc_part == "C12345"

    def test_is_available_found(self):
        client = LcscSearchClient()
        item = ComponentInfo(lcsc_part="C12345", mfr_part="STM32", stock=500)
        client.is_available = MagicMock(return_value=item)
        info = client.is_available("STM32")
        assert info is not None
        assert info.in_stock
        assert info.mfr_part == "STM32"

    def test_is_available_none(self):
        client = LcscSearchClient()
        client.is_available = MagicMock(return_value=None)
        info = client.is_available("RARE_PART")
        assert info is None

    def test_batch_search(self):
        client = LcscSearchClient()
        client._cache_get = MagicMock(return_value=None)
        item = ComponentInfo(lcsc_part="C1", stock=10)
        client._public.search = MagicMock(return_value=SearchResult(
            keyword="test", total=1, items=[item],
        ))
        result = client.batch_search([
            {"part": "A", "package": "0805"},
        ])
        assert "A" in result
        assert len(result["A"]) == 1


# ══════════════════════════════════════════════════════
#  BOMHealthReport
# ══════════════════════════════════════════════════════

class TestBOMHealthReport:
    def test_health_score_perfect(self):
        r = BOMHealthReport(total_items=10, in_stock_count=10)
        assert r.health_score == 100.0

    def test_health_score_empty(self):
        r = BOMHealthReport()
        assert r.health_score == 100.0

    def test_health_score_deduct_out_of_stock(self):
        r = BOMHealthReport(total_items=10, in_stock_count=9, out_of_stock=[{"part": "X"}])
        assert r.health_score < 100.0

    def test_health_score_floor_zero(self):
        r = BOMHealthReport(total_items=1, out_of_stock=[{}, {}, {}, {}, {}, {}])
        assert r.health_score == 0.0


# ══════════════════════════════════════════════════════
#  BOMHealthChecker
# ══════════════════════════════════════════════════════

class TestBOMHealthChecker:
    @staticmethod
    def _make_client():
        client = LcscSearchClient()
        client.is_available = MagicMock()
        client.search_by_part = MagicMock()
        return client

    def test_check_all_in_stock(self):
        client = self._make_client()
        client.is_available.return_value = ComponentInfo(
            lcsc_part="C1", mfr_part="R10K", stock=1000, min_price=0.05,
        )
        checker = BOMHealthChecker(client)
        items = [
            BOMItem(reference="R1", value="10k", package="0805", part_number="RC0805-10K", quantity=5),
            BOMItem(reference="R2", value="1k", package="0805", part_number="RC0805-1K", quantity=3),
        ]
        report = checker.check(items)
        assert report.in_stock_count == 2
        assert len(report.out_of_stock) == 0
        assert report.health_score == 100.0

    def test_check_out_of_stock(self):
        client = self._make_client()
        client.is_available.return_value = ComponentInfo(
            lcsc_part="C1", stock=0, min_price=0,
        )
        checker = BOMHealthChecker(client)
        items = [BOMItem(reference="U1", value="MCU", package="LQFP-48", part_number="STM32F103", quantity=1)]
        report = checker.check(items)
        assert len(report.out_of_stock) == 1
        assert report.out_of_stock[0]["part"] == "STM32F103"

    def test_check_none_result(self):
        client = self._make_client()
        client.is_available.return_value = None
        checker = BOMHealthChecker(client)
        items = [BOMItem(reference="U1", value="RARE", package="BGA", part_number="RARE_CHIP", quantity=1)]
        report = checker.check(items)
        assert "U1" in report.not_found

    def test_check_no_part_number(self):
        client = self._make_client()
        checker = BOMHealthChecker(client)
        items = [BOMItem(reference="R1", value="10k", package="0805", part_number="N/A", quantity=1)]
        report = checker.check(items)
        assert "R1" in report.not_found

    def test_format_report(self):
        report = BOMHealthReport(
            total_items=3, in_stock_count=2,
            out_of_stock=[{"reference": "U1", "part": "STM32", "package": "LQFP-48"}],
            total_cost_estimate=12.50,
        )
        text = BOMHealthChecker.format_report(report)
        assert "BOM 健康检查报告" in text
        assert "STM32" in text
        assert "12.50" in text

    def test_estimate_total_cost(self):
        client = self._make_client()
        client.is_available.return_value = ComponentInfo(min_price=1.50)
        checker = BOMHealthChecker(client)
        items = [BOMItem(reference="R1", value="10k", package="0805", part_number="R1", quantity=10)]
        cost = checker.estimate_total_cost(items, quantity=2)
        assert cost == 30.0  # 10 * 2 * 1.50

    def test_recommend_alternatives_returns_list(self):
        client = self._make_client()
        checker = BOMHealthChecker(client)
        alts = checker.recommend_alternatives("UNKNOWN_PART", "0805")
        assert isinstance(alts, list)
