"""
AI Verification Map 生成器 — 将 DRC 违规、AI 变更、多智能体审查数据
渲染为交互式可视化 HTML 仪表盘。

与 ibom.html 不同: ibom.html 展示"板子长什么样",
verification_map.html 展示 "问题在哪里、AI 发现了什么、AI 建议安全吗"。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from .shared import prepare_component_data, calculate_board_stats

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class VerificationMapConfig:
    """AI Verification Map 生成配置"""

    title: str = "AI Verification Map"
    dark_mode: bool = False
    default_layer: str = "all"               # "all" / "Top" / "Bottom"
    board_color: str = "#1a1a2e"
    language: str = "zh-CN"
    show_drc_heatmap: bool = True
    show_ai_changes: bool = True
    show_agent_findings: bool = True
    show_before_after: bool = False
    heatmap_radius: int = 18                 # 热力图光斑半径 (px)
    heatmap_opacity: float = 0.65


# ═══════════════════════════════════════════════════════════════
#  Generator
# ═══════════════════════════════════════════════════════════════

class VerificationMapGenerator:
    """AI 验证可视化仪表盘生成器。

    输入: BOM + 坐标 + 实验数据 (DRC / 闭环验证 / 多智能体 / 缺陷注入)
    输出: 单页 HTML 交互式仪表盘
    """

    def __init__(self, config: Optional[VerificationMapConfig] = None):
        self.config = config or VerificationMapConfig()

        template_dir = Path(__file__).parent / "templates"
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

    def generate(
        self,
        bom_items: list,
        positions: dict,
        overlay_data: dict,
        output_path: Optional[str] = None,
    ) -> str:
        """生成 AI Verification Map HTML。

        Args:
            bom_items:  BOM 物料列表
            positions:  元件坐标 {"R1": {"x":..., "y":..., ...}, ...}
            overlay_data: AI 验证叠加数据 (由 _prepare_overlay_data 构建)
            output_path: 输出文件路径 (可选)

        Returns:
            HTML 字符串
        """
        components = prepare_component_data(bom_items, positions)
        board_stats = calculate_board_stats(positions)

        template = self._env.get_template("verification_map.html")
        html = template.render(
            config=self.config,
            components=components,
            board_stats=board_stats,
            components_json=json.dumps(components, ensure_ascii=False),
            overlay_json=json.dumps(overlay_data, ensure_ascii=False),
        )

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding="utf-8")
            logger.info(f"AI Verification Map 已生成: {output_path}")

        return html

    # ═══════════════════════════════════════════════════════════
    #  Overlay Data Preparation
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _prepare_overlay_data(
        drc_results: Optional[dict] = None,
        verify_results: Optional[list[dict]] = None,
        ma_results: Optional[list[dict]] = None,
        defect_results: Optional[list[dict]] = None,
    ) -> dict:
        """将实验数据转换为前端 overlay JSON。

        各输入参数均为从 results.json 加载的字典/列表。

        Returns:
            {
                "drc_heatmap": {ref: {count, max_severity, violations: [...]}, ...},
                "ai_changes": [{ref, safety, design, changes: [...], ...}, ...],
                "agent_findings": [{ref, mentions, agents, ...}, ...],
                "defect_results": [...] (直接透传),
                "stats": {total_errors, total_warnings, total_infos,
                          converged_count, total_verify, avg_score, ...}
            }
        """
        overlay: dict = {
            "drc_heatmap": {},
            "ai_changes": [],
            "agent_findings": [],
            "defect_results": defect_results or [],
            "stats": {},
        }

        # ── DRC Heatmap ──
        if drc_results:
            by_component = drc_results.get("violations_by_component", {})
            for ref, violations in by_component.items():
                if ref == "__board__":
                    continue  # 板级违规不在热力图上显示
                severities = [v.get("severity", "info") for v in violations]
                max_sev = "error" if "error" in severities else (
                    "warning" if "warning" in severities else "info"
                )
                overlay["drc_heatmap"][ref] = {
                    "count": len(violations),
                    "max_severity": max_sev,
                    "violations": violations,
                }

            overlay["stats"]["total_errors"] = drc_results.get("errors", 0)
            overlay["stats"]["total_warnings"] = drc_results.get("warnings", 0)
            overlay["stats"]["total_infos"] = drc_results.get("infos", 0)
            overlay["stats"]["total_violations"] = drc_results.get("total_violations", 0)

            # Board-level violations
            board_violations = drc_results.get("violations_by_component", {}).get("__board__", [])
            overlay["board_violations"] = board_violations

        # ── AI Changes ──
        if verify_results:
            for vr in verify_results:
                if vr.get("error"):
                    continue
                changes = vr.get("applied_changes", [])
                if not changes:
                    # Pure analysis — still report per-design
                    overlay["ai_changes"].append({
                        "design": vr.get("design", ""),
                        "provider": vr.get("provider", ""),
                        "category": vr.get("suggestion_category", "general"),
                        "safety": _classify_safety(vr),
                        "converged": vr.get("converged", True),
                        "changes": [],
                        "refs": [],
                        "new_violations": vr.get("new_violations_introduced", 0),
                        "correction_rounds": vr.get("correction_rounds", 0),
                        "desc": vr.get("suggestion_desc", ""),
                    })
                    continue

                refs = list(set(c.get("reference", "") for c in changes if c.get("reference")))
                overlay["ai_changes"].append({
                    "design": vr.get("design", ""),
                    "provider": vr.get("provider", ""),
                    "category": vr.get("suggestion_category", "general"),
                    "safety": _classify_safety(vr),
                    "converged": vr.get("converged", False),
                    "changes": changes,
                    "refs": refs,
                    "new_violations": vr.get("new_violations_introduced", 0),
                    "correction_rounds": vr.get("correction_rounds", 0),
                    "desc": vr.get("suggestion_desc", ""),
                })

            # Stats
            bom_changes = [r for r in verify_results
                          if not r.get("error") and r.get("suggested_changes_count", 0) > 0]
            overlay["stats"]["converged_count"] = sum(1 for r in bom_changes if r.get("converged"))
            overlay["stats"]["total_verify"] = len(verify_results)
            overlay["stats"]["bom_change_count"] = len(bom_changes)

        # ── Agent Findings ──
        if ma_results:
            # Build per-component mention map from multi-agent findings
            # Each agent finding references a component or area
            ref_mentions: dict[str, dict] = {}
            for mr in ma_results:
                if mr.get("error"):
                    continue
                # Extract component references from agent findings text
                radar = mr.get("radar_scores", {})
                for dim, score in radar.items():
                    # Multi-agent dimensions map to board-level concerns
                    pass

                # Try to extract ref mentions from consensus preview
                consensus = mr.get("consensus_preview", "")
                if consensus:
                    import re
                    mentioned_refs = re.findall(r'[A-Z]+\d+', consensus)
                    for ref in mentioned_refs:
                        if ref not in ref_mentions:
                            ref_mentions[ref] = {"ref": ref, "mentions": 0, "agents": set()}
                        ref_mentions[ref]["mentions"] += 1

            overlay["agent_findings"] = [
                {"ref": v["ref"], "mentions": v["mentions"],
                 "agents": sorted(v["agents"])}
                for v in ref_mentions.values()
            ]

            # Stats
            scores = [r.get("overall_score", 0) for r in ma_results if not r.get("error")]
            overlay["stats"]["avg_score"] = round(sum(scores) / len(scores), 1) if scores else 0
            overlay["stats"]["total_ma_reviews"] = len(ma_results)
            overlay["stats"]["ma_results"] = [
                {"design": r.get("design", ""), "score": r.get("overall_score", 0),
                 "grade": r.get("overall_grade", "N/A"),
                 "critical": r.get("critical_count", 0),
                 "findings": r.get("total_findings", 0)}
                for r in ma_results if not r.get("error")
            ]

        return overlay


def _classify_safety(vr: dict) -> str:
    """根据验证结果分类 AI 建议的安全性。

    Returns:
        "safe" | "warning" | "dangerous" | "analysis"
    """
    if vr.get("suggested_changes_count", 0) == 0:
        return "analysis"
    if vr.get("converged") and vr.get("new_violations_introduced", 0) == 0:
        return "safe"
    if vr.get("converged"):
        return "warning"
    return "dangerous"
