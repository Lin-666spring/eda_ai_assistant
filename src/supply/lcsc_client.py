"""
立创商城 API 客户端 — 多通道策略。

优先级: LCSC 官方 OpenAPI → jlcsearch 公开 API → 本地缓存
"""

import hashlib
import json
import logging
import os
import random
import string
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

from ..config import SETTINGS_DIR
from ..constants import SUPPLY
from ..exceptions import SupplyAPIError, SupplyAuthError, SupplyNotFoundError

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Data models
# ══════════════════════════════════════════════════════

@dataclass
class ComponentInfo:
    """LCSC 元器件信息"""
    lcsc_part: str = ""
    mfr_part: str = ""
    manufacturer: str = ""
    package: str = ""
    description: str = ""
    category: str = ""
    stock: int = 0
    stock_text: str = ""          # 如 "In Stock", "Pre-order"
    price_list: list[dict] = field(default_factory=list)
    min_price: float = 0.0
    datasheet_url: str = ""
    image_url: str = ""
    availability: str = "Unknown"

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def price_display(self) -> str:
        if not self.price_list:
            return "N/A"
        prices = sorted(self.price_list, key=lambda p: p.get("qty", 0))
        if not prices:
            return "N/A"
        first = prices[0]
        return f"¥{first.get('price', 0):.4f}" if first.get("price") else "N/A"


@dataclass
class SearchResult:
    """搜索结果"""
    keyword: str = ""
    total: int = 0
    items: list[ComponentInfo] = field(default_factory=list)


# ══════════════════════════════════════════════════════
#  LCSC OpenAPI client (primary channel)
# ══════════════════════════════════════════════════════

class LCSCClient:
    """立创商城官方 OpenAPI 客户端。

    需要 API Key，通过 LCSC 账号申请: https://www.lcsc.com/agent
    """

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key or os.getenv("LCSC_API_KEY", "")
        self.api_secret = api_secret or os.getenv("LCSC_API_SECRET", "")
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def search(
        self, keyword: str, match_type: str = "fuzzy",
        page: int = 1, in_stock_only: bool = False,
    ) -> SearchResult:
        """按关键字搜索元器件。"""
        if not self.is_configured:
            raise SupplyAuthError("LCSC API Key / Secret 未配置")

        auth_headers = self._sign()
        params = {
            "keyword": keyword,
            "match_type": match_type,
            "current_page": page,
            "page_size": SUPPLY.LCSC_MAX_PAGE_SIZE,
        }
        if in_stock_only:
            params["is_available"] = 1

        try:
            resp = self._session.get(
                SUPPLY.LCSC_API_BASE + SUPPLY.LCSC_API_SEARCH,
                params=params, headers=auth_headers,
                timeout=SUPPLY.LCSC_API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_search_response(data, keyword)
        except requests.RequestException as e:
            raise SupplyAPIError(f"LCSC API 搜索失败: {e}") from e

    def get_detail(self, lcsc_part: str) -> Optional[ComponentInfo]:
        """按 LCSC 编号获取商品详情。"""
        if not self.is_configured:
            raise SupplyAuthError("LCSC API Key / Secret 未配置")

        auth_headers = self._sign()
        try:
            resp = self._session.get(
                SUPPLY.LCSC_API_BASE + SUPPLY.LCSC_API_DETAIL,
                params={"product_code": lcsc_part},
                headers=auth_headers,
                timeout=SUPPLY.LCSC_API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_detail_response(data)
        except requests.RequestException as e:
            raise SupplyAPIError(f"LCSC API 查详情失败: {e}") from e

    # ── Auth ──

    def _sign(self) -> dict[str, str]:
        """生成 LCSC OpenAPI 签名头。"""
        nonce = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        ts = str(int(time.time() * 1000))
        sign_str = f"api_key={self.api_key}&nonce={nonce}&timestamp={ts}"
        signature = hashlib.md5(
            (sign_str + self.api_secret).encode("utf-8")
        ).hexdigest()
        return {
            "api_key": self.api_key,
            "nonce": nonce,
            "timestamp": ts,
            "sign": signature,
        }

    # ── Parsers ──

    def _parse_search_response(self, data: dict, keyword: str) -> SearchResult:
        result = data.get("result", data)
        items_raw = result.get("list", result.get("items", []))
        items = [self._parse_item(raw) for raw in items_raw]
        total = result.get("total", result.get("total_count", len(items)))
        return SearchResult(keyword=keyword, total=total, items=items)

    def _parse_detail_response(self, data: dict) -> Optional[ComponentInfo]:
        item = data.get("result", data)
        if not item:
            return None
        return self._parse_item(item)

    @staticmethod
    def _parse_item(raw: dict) -> ComponentInfo:
        return ComponentInfo(
            lcsc_part=raw.get("product_code", raw.get("lcsc_part", "")),
            mfr_part=raw.get("mfr_part", raw.get("mfr_part_number", "")),
            manufacturer=raw.get("brand_name", raw.get("manufacturer", "")),
            package=raw.get("package", raw.get("encapsulation", "")),
            description=raw.get("describe", raw.get("description", "")),
            category=raw.get("catalog_name", raw.get("category", "")),
            stock=int(raw.get("stock_number", raw.get("stock", 0)) or 0),
            stock_text=raw.get("stock", raw.get("availability", "")),
            min_price=float(raw.get("min_price", raw.get("price", 0)) or 0),
            datasheet_url=raw.get("pdf_url", raw.get("datasheet", "")),
            image_url=raw.get("product_image", raw.get("image", "")),
            availability="In Stock" if int(raw.get("stock_number", raw.get("stock", 0)) or 0) > 0 else "Check",
        )


# ══════════════════════════════════════════════════════
#  JlcSearch public API client (fallback channel)
# ══════════════════════════════════════════════════════

class JlcSearchClient:
    """JlcSearch 公开 API — 无需认证，作为 fallback。"""

    def search(self, keyword: str) -> SearchResult:
        try:
            resp = requests.get(
                f"{SUPPLY.JLCSEARCH_API}/search",
                params={"q": keyword},
                timeout=SUPPLY.JLCSEARCH_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            items = [
                ComponentInfo(
                    lcsc_part=raw.get("lcsc", raw.get("lcsc_part", "")),
                    mfr_part=raw.get("mfr", raw.get("mfr_part", "")),
                    manufacturer=raw.get("brand", raw.get("manufacturer", "")),
                    package=raw.get("package", ""),
                    description=raw.get("description", ""),
                    stock=int(raw.get("stock", 0) or 0),
                    min_price=float(raw.get("price", 0) or 0),
                )
                for raw in (data if isinstance(data, list) else data.get("results", data.get("items", [])))
            ]
            return SearchResult(keyword=keyword, total=len(items), items=items)
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            raise SupplyAPIError(f"JlcSearch 查询失败: {e}") from e


# ══════════════════════════════════════════════════════
#  Unified client — multi-channel strategy
# ══════════════════════════════════════════════════════

class LcscSearchClient:
    """立创商城统一查询客户端 — 三级通道策略。

    1. LCSC 官方 OpenAPI（需 Key，精确库存/价格）
    2. JlcSearch 公开 API（无需 Key，快速查询）
    3. 本地磁盘缓存（离线可用）
    """

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self._official = LCSCClient(api_key, api_secret)
        self._public = JlcSearchClient()
        self._cache: dict[str, tuple[float, SearchResult]] = {}
        self._cache_dir = SETTINGS_DIR / SUPPLY.CACHE_DIR_NAME
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def search_by_part(self, part: str, package: str = "") -> SearchResult:
        """按型号搜索（优先官方 API，fallback 到公开 API）。"""
        keyword = f"{part} {package}".strip()
        # 1. 内存缓存
        cached = self._cache_get(part)
        if cached:
            return cached
        # 2. 官方 API
        if self._official.is_configured:
            try:
                result = self._official.search(keyword)
                self._cache_set(part, result)
                return result
            except SupplyAPIError:
                logger.debug("Official API failed, falling back to public", exc_info=True)
        # 3. 公开 API
        result = self._public.search(keyword)
        self._cache_set(part, result)
        return result

    def search_by_lcsc_id(self, lcsc_id: str) -> Optional[ComponentInfo]:
        """按 LCSC 编号精确查询。"""
        cached = self._cache_get(lcsc_id)
        if cached and cached.items:
            return cached.items[0]
        if self._official.is_configured:
            try:
                info = self._official.get_detail(lcsc_id)
                if info:
                    self._cache_set(lcsc_id, SearchResult(lcsc_id, 1, [info]))
                return info
            except SupplyAPIError:
                logger.debug("Official detail failed", exc_info=True)
        # Fallback: use public search with LCSC ID
        result = self._public.search(lcsc_id)
        if result and result.items:
            self._cache_set(lcsc_id, result)
            return result.items[0]
        return None

    def batch_search(
        self, queries: list[dict]
    ) -> dict[str, list[ComponentInfo]]:
        """批量搜索。每项 {"part": "xxx", "package": "yyy"} → {part: [results]}"""
        out: dict[str, list[ComponentInfo]] = {}
        for q in queries:
            part = q.get("part", "")
            if not part:
                continue
            try:
                result = self.search_by_part(part, q.get("package", ""))
                out[part] = result.items
            except SupplyAPIError:
                out[part] = []
        return out

    def is_available(self, part: str) -> Optional[ComponentInfo]:
        """快速检查物料是否有货。返回第一个有货的结果，都没有则返回 None。"""
        result = self.search_by_part(part)
        for item in result.items:
            if item.in_stock:
                return item
        return result.items[0] if result.items else None

    # ── Cache ──

    def _cache_key(self, part: str) -> str:
        return hashlib.md5(part.lower().encode()).hexdigest()

    def _cache_get(self, part: str) -> Optional[SearchResult]:
        if part in self._cache:
            ts, result = self._cache[part]
            if time.time() - ts < SUPPLY.CACHE_TTL_HOURS * 3600:
                return result
            del self._cache[part]
        # Disk cache
        disk = self._cache_dir / f"{self._cache_key(part)}.json"
        if disk.exists():
            try:
                with open(disk, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if time.time() - data["ts"] < SUPPLY.CACHE_TTL_HOURS * 3600:
                    items = [ComponentInfo(**i) for i in data["items"]]
                    result = SearchResult(data["keyword"], data["total"], items)
                    self._cache[part] = (data["ts"], result)
                    return result
            except (json.JSONDecodeError, KeyError, TypeError):
                disk.unlink(missing_ok=True)
        return None

    def _cache_set(self, part: str, result: SearchResult):
        self._cache[part] = (time.time(), result)
        disk = self._cache_dir / f"{self._cache_key(part)}.json"
        try:
            with open(disk, "w", encoding="utf-8") as f:
                json.dump({
                    "ts": time.time(),
                    "keyword": result.keyword,
                    "total": result.total,
                    "items": [item.__dict__ for item in result.items],
                }, f, ensure_ascii=False)
        except OSError:
            pass
