"""
PCB 设计质量评分引擎 — 6 维度量化评分 + 雷达图数据

将设计规则检查结果映射到 6 个专业维度，
每个维度独立评分 (0-100)，基于违规的严重度和数量加权扣分。

使用方式:
    from src.core.design_scorer import DesignScorer
    scorer = DesignScorer()
    result = scorer.score(violations, bom_items)
    # → {dimensions: {...}, radar_data: [...], overall: 72.5, suggestions: [...]}
"""

import logging
import math
from dataclasses import dataclass, field
from collections import defaultdict

from ..rules.checker import RuleViolation, RuleSeverity

logger = logging.getLogger(__name__)

# ── 维度定义 ──
DIMENSIONS = {
    "power": {
        "label": "电源完整性",
        "en_label": "Power Integrity",
        "color": "#e74c3c",
        "description": "电源滤波、去耦、载流与PDN设计质量",
    },
    "signal": {
        "label": "信号完整性",
        "en_label": "Signal Integrity",
        "color": "#3498db",
        "description": "信号质量、时序、阻抗与串扰控制",
    },
    "thermal": {
        "label": "热管理",
        "en_label": "Thermal",
        "color": "#e67e22",
        "description": "散热设计、功率器件布局与温度裕量",
    },
    "emc": {
        "label": "电磁兼容",
        "en_label": "EMC",
        "color": "#9b59b6",
        "description": "ESD保护、EMI滤波与电磁辐射控制",
    },
    "dfm": {
        "label": "可制造性",
        "en_label": "DFM",
        "color": "#2ecc71",
        "description": "封装一致性、丝印、测试点与装配工艺",
    },
    "cost": {
        "label": "成本优化",
        "en_label": "Cost",
        "color": "#1abc9c",
        "description": "元件选型经济性、非标值与过度设计",
    },
}

# ── 规则→维度映射表 ──
# 每条规则的 rule_name 关键词 → 所属维度 + 权重
RULE_DIMENSION_MAP: dict[str, tuple[str, float]] = {
    # 电源完整性 (power)
    "去耦电容": ("power", 1.5),
    "电源滤波": ("power", 1.2),
    "电源轨去耦": ("power", 1.5),
    "电源线宽": ("power", 2.0),
    "DC-DC 反馈": ("power", 2.0),
    "电容耐压降额": ("power", 1.5),
    "多电源引脚去耦": ("power", 1.5),
    "开关电源布局": ("power", 1.5),
    "磁珠隔离": ("power", 1.0),
    "去耦电容距离": ("power", 1.5),
    "电池电压分压器": ("power", 1.0),
    "电源极性保护": ("power", 1.0),
    # 信号完整性 (signal)
    "晶振负载电容": ("signal", 1.5),
    "晶振频率匹配": ("signal", 1.5),
    "晶振布局": ("signal", 1.5),
    "I2C 上拉电阻": ("signal", 1.0),
    "信号线宽": ("signal", 1.5),
    "走线锐角": ("signal", 1.0),
    "过孔密度": ("signal", 1.0),
    "差分对间距": ("signal", 1.5),
    "差分对等长": ("signal", 2.0),
    "时钟信号包地": ("signal", 1.5),
    "3W 串扰间距": ("signal", 1.5),
    "环路面积": ("signal", 1.5),
    "ADC 输入滤波": ("signal", 1.2),
    "运放反馈网络": ("signal", 1.2),
    "光耦输入限流": ("signal", 1.0),
    "悬空引脚": ("signal", 1.0),
    "复位电路": ("signal", 1.0),
    # 热管理 (thermal)
    "热焊盘": ("thermal", 1.5),
    "温度敏感元件布局": ("thermal", 1.5),
    "电阻功率降额": ("thermal", 1.0),
    "元件高度分区": ("thermal", 0.5),
    # EMC
    "ESD 保护": ("emc", 1.5),
    "EMI 滤波": ("emc", 1.5),
    "EMI 滤波器布局": ("emc", 1.5),
    "天线净空区": ("emc", 1.0),
    "铜皮连接": ("emc", 0.5),
    "模数分离": ("emc", 1.5),
    "LED 限流": ("emc", 0.5),  # LED PWM 可能产生 EMI
    "MOSFET 栅极电阻": ("emc", 1.0),
    "继电器续流二极管": ("emc", 1.0),
    # DFM (可制造性)
    "封装一致性": ("dfm", 1.5),
    "位号连续性": ("dfm", 0.5),
    "板边间距": ("dfm", 1.0),
    "丝印可读性": ("dfm", 0.5),
    "测试点覆盖": ("dfm", 1.0),
    "安装孔禁区": ("dfm", 1.0),
    "连接器边沿布局": ("dfm", 1.0),
    "调试接口": ("dfm", 0.5),
    # 成本优化 (cost)
    "参数范围": ("cost", 1.0),
    "封装一致性": ("cost", 0.5),  # 多封装增加采购成本
}

# 严重度→扣分基数
SEVERITY_PENALTY = {
    RuleSeverity.ERROR: 20,
    RuleSeverity.WARNING: 8,
    RuleSeverity.INFO: 2,
}


@dataclass
class DimensionScore:
    """单个维度的评分详情"""
    dimension: str
    label: str
    score: float  # 0-100
    color: str
    violation_count: int
    max_severity: str  # "error" | "warning" | "info" | "clean"
    top_issues: list[dict] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class DesignScoreReport:
    """设计质量评分报告"""
    dimensions: dict[str, DimensionScore]  # key → DimensionScore
    radar_data: list[dict]  # [{dimension, label, score, color}, ...]
    overall: float  # 综合评分 0-100
    total_violations: int
    grade: str  # A+/A/B/C/D/F
    suggestions: list[str]  # 改进建议（按优先级排序）
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "dimensions": {k: {
                "dimension": v.dimension,
                "label": v.label,
                "score": v.score,
                "color": v.color,
                "violation_count": v.violation_count,
                "max_severity": v.max_severity,
                "top_issues": v.top_issues,
                "suggestion": v.suggestion,
            } for k, v in self.dimensions.items()},
            "radar_data": self.radar_data,
            "overall": self.overall,
            "total_violations": self.total_violations,
            "grade": self.grade,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp,
        }


class DesignScorer:
    """PCB 设计质量评分引擎

    将 DesignRuleChecker 的输出（RuleViolation 列表）
    映射到 6 个专业维度，量化评分并生成改进建议。
    """

    def score(
        self,
        violations: list[RuleViolation],
        bom_items: list = None,
        positions: dict = None,
    ) -> DesignScoreReport:
        """对设计质量进行 6 维度评分

        Args:
            violations: DesignRuleChecker.check_all() 的返回结果
            bom_items: BOM 元件列表（可选，用于成本维度补充分析）
            positions: 元件坐标（可选）

        Returns:
            DesignScoreReport 包含各维度评分和雷达图数据
        """
        bom_items = bom_items or []

        # Step 1: 将违规按维度分组
        dim_violations: dict[str, list[RuleViolation]] = defaultdict(list)
        unmatched = 0
        for v in violations:
            matched = False
            for kw, (dim, weight) in RULE_DIMENSION_MAP.items():
                if kw in v.rule_name:
                    # 附加权重到违规对象上（动态属性）
                    v._weight = weight
                    dim_violations[dim].append(v)
                    matched = True
                    break
            if not matched:
                unmatched += 1

        if unmatched:
            logger.debug("Unmatched violations (default to DFM): %d", unmatched)

        # Step 2: 计算每个维度的评分
        dim_scores: dict[str, DimensionScore] = {}
        for dim_key, dim_info in DIMENSIONS.items():
            dv = dim_violations.get(dim_key, [])
            score, top_issues, max_sev = self._calc_dimension_score(dv)
            dim_scores[dim_key] = DimensionScore(
                dimension=dim_key,
                label=dim_info["label"],
                score=score,
                color=dim_info["color"],
                violation_count=len(dv),
                max_severity=max_sev,
                top_issues=top_issues[:3],
                suggestion=self._gen_dim_suggestion(dim_key, score, dv),
            )

        # Step 3: 计算综合评分（加权平均）
        weights = {"power": 1.2, "signal": 1.2, "thermal": 1.0,
                    "emc": 1.0, "dfm": 0.8, "cost": 0.6}
        total_w = sum(weights.values())
        overall = sum(
            dim_scores[k].score * weights.get(k, 1.0)
            for k in dim_scores
        ) / total_w

        # Step 4: 确定等级
        grade = self._assign_grade(overall)

        # Step 5: 生成改进建议
        suggestions = self._gen_suggestions(dim_scores, dim_violations)

        # Step 6: 生成雷达图数据
        radar_data = [
            {"dimension": k, "label": v.label, "score": v.score, "color": v.color}
            for k, v in dim_scores.items()
        ]

        return DesignScoreReport(
            dimensions=dim_scores,
            radar_data=radar_data,
            overall=round(overall, 1),
            total_violations=len(violations),
            grade=grade,
            suggestions=suggestions,
        )

    def _calc_dimension_score(
        self, violations: list[RuleViolation]
    ) -> tuple[float, list[dict], str]:
        """计算单个维度的评分

        Returns:
            (score 0-100, top_issues list, max_severity string)
        """
        if not violations:
            return (100.0, [], "clean")

        total_penalty = 0.0
        max_sev = "info"

        for v in violations:
            base = SEVERITY_PENALTY.get(v.severity, 5)
            weight = getattr(v, "_weight", 1.0)
            total_penalty += base * weight

            if v.severity == RuleSeverity.ERROR:
                max_sev = "error"
            elif v.severity == RuleSeverity.WARNING and max_sev != "error":
                max_sev = "warning"
            elif v.severity == RuleSeverity.INFO and max_sev not in ("error", "warning"):
                max_sev = "info"

        # 平方根衰减：少量违规温和扣分，大量违规不瞬间归零。
        # 契合实际使用——评分是"健康度"而非"扣分竞赛"，
        # 修复部分违规后分数可逐步恢复，而不是被一两条重违规打穿到 0。
        score = max(0.0, 100 - 2.2 * math.sqrt(total_penalty))
        score = round(score, 1)

        # 提取最重要的违规项
        sorted_v = sorted(violations,
                         key=lambda x: SEVERITY_PENALTY.get(x.severity, 0) * getattr(x, "_weight", 1.0),
                         reverse=True)
        top_issues = [
            {
                "rule_name": v.rule_name,
                "description": v.description,
                "severity": v.severity.value,
                "location": v.location,
                "suggestion": v.suggestion,
            }
            for v in sorted_v[:5]
        ]

        return (score, top_issues, max_sev)

    def _gen_dim_suggestion(
        self, dim_key: str, score: float, violations: list[RuleViolation]
    ) -> str:
        """生成单个维度的总结建议"""
        if score >= 90:
            return f"{DIMENSIONS[dim_key]['label']}设计优秀，未发现明显问题。"
        elif score >= 75:
            return f"{DIMENSIONS[dim_key]['label']}总体良好，存在少量可优化项。"
        elif score >= 60:
            sev_count = defaultdict(int)
            for v in violations:
                sev_count[v.severity.value] += 1
            parts = [f"{DIMENSIONS[dim_key]['label']}存在改进空间:"]
            if sev_count.get("error"):
                parts.append(f"{sev_count['error']} 项严重问题需立即修复")
            if sev_count.get("warning"):
                parts.append(f"{sev_count['warning']} 项警告建议关注")
            return "；".join(parts) if len(parts) > 1 else parts[0]
        else:
            return (
                f"{DIMENSIONS[dim_key]['label']}问题较多，"
                f"建议优先处理 {len(violations)} 项违规。"
            )

    def _gen_suggestions(
        self,
        dim_scores: dict[str, DimensionScore],
        dim_violations: dict[str, list[RuleViolation]],
    ) -> list[str]:
        """生成全局改进建议（按优先级排序）"""
        suggestions = []

        # 1. 严重问题优先
        for dim_key, dv in dim_violations.items():
            errors = [v for v in dv if v.severity == RuleSeverity.ERROR]
            for e in errors[:2]:
                suggestions.append(
                    f" [{dim_scores[dim_key].label}] {e.rule_name}: {e.suggestion or e.description}"
                )

        # 2. 低分维度
        for dim_key, ds in sorted(dim_scores.items(), key=lambda x: x[1].score):
            if ds.score < 70 and ds.score > 0:
                if not any(dim_key in s for s in suggestions):
                    suggestions.append(
                        f" [{ds.label}] 该维度评分 {ds.score} 分，建议重点改进。{ds.suggestion}"
                    )

        # 3. 总体建议
        worst_dim = min(dim_scores.items(), key=lambda x: x[1].score)
        if worst_dim[1].score < 70:
            suggestions.append(
                f" 优先改进维度: {worst_dim[1].label}（当前 {worst_dim[1].score} 分），"
                f"可带来最大整体质量提升。"
            )

        if not suggestions:
            suggestions.append(" 所有维度表现良好，设计质量较高。")

        return suggestions[:8]

    @staticmethod
    def _assign_grade(score: float) -> str:
        """将 0-100 分数转换为等级"""
        if score >= 95:
            return "A+"
        elif score >= 88:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 45:
            return "D"
        else:
            return "F"


def score_design(violations: list[RuleViolation], bom_items=None, positions=None) -> dict:
    """便捷函数：快速评分并返回 dict"""
    scorer = DesignScorer()
    report = scorer.score(violations, bom_items, positions)
    return report.to_dict()
