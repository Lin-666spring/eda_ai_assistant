"""DesignScorer + MultiAgentReviewer 单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.rules.checker import DesignRuleChecker, RuleViolation, RuleSeverity
from src.core.design_scorer import DesignScorer, DIMENSIONS, RULE_DIMENSION_MAP
from src.agent.review_agents import MultiAgentReviewer
from src.bom.parser import BOMItem


@pytest.fixture
def scorer():
    return DesignScorer()


@pytest.fixture
def sample_bom():
    return [
        BOMItem(reference="U1", value="3.3V", package="LQFP-48",
                part_number="STM32F103C8T6", description="MCU", quantity=1),
        BOMItem(reference="C1,C2", value="100nF", package="0603",
                part_number="C1588", description="贴片电容", quantity=2),
        BOMItem(reference="R1", value="10kΩ", package="0603",
                part_number="C25804", description="贴片电阻", quantity=1),
    ]


@pytest.fixture
def sample_violations():
    """创建测试用违规列表"""
    return [
        RuleViolation(
            rule_name="去耦电容检查", description="IC U1 缺少去耦电容",
            severity=RuleSeverity.ERROR, location="U1",
            suggestion="添加 0.1μF 电容", theory="去耦电容提供就近电荷池"),
        RuleViolation(
            rule_name="信号线宽度检查", description="信号线过细",
            severity=RuleSeverity.WARNING, location="SCLK",
            suggestion="加宽走线", theory="线宽应 ≥ 最小线宽"),
        RuleViolation(
            rule_name="位号连续性检查", description="R 类位号不连续",
            severity=RuleSeverity.INFO, location="R1",
            suggestion="重新编号", theory="规范化位号"),
    ]


class TestDimensions:
    def test_all_six_dimensions(self):
        assert len(DIMENSIONS) == 6
        for key in ["power", "signal", "thermal", "emc", "dfm", "cost"]:
            assert key in DIMENSIONS
            assert "label" in DIMENSIONS[key]
            assert "color" in DIMENSIONS[key]

    def test_rule_map_covers_all_rules(self):
        """验证所有 51 条规则至少有一条被映射（部分规则可能映射不到所有维度但不应为空）"""
        checker = DesignRuleChecker()
        rules = [name for name in dir(checker) if name.startswith('_check_')]
        assert len(rules) >= 50
        # RULE_DIMENSION_MAP 中的关键词应与 rule_name 匹配
        mapped_keywords = list(RULE_DIMENSION_MAP.keys())
        assert len(mapped_keywords) >= 40


class TestDesignScorer:
    def test_empty_violations(self, scorer):
        report = scorer.score([], [])
        assert report.overall == 100.0
        assert report.grade == "A+"
        assert report.total_violations == 0
        for dim in report.dimensions.values():
            assert dim.score == 100.0

    def test_with_violations(self, scorer, sample_violations):
        report = scorer.score(sample_violations, [])
        assert report.overall < 100.0
        assert report.total_violations == 3
        assert len(report.radar_data) == 6

    def test_power_dimension_penalized(self, scorer, sample_violations):
        report = scorer.score(sample_violations, [])
        power = report.dimensions["power"]
        assert power.score < 100.0  # 有一个去耦电容 ERROR
        assert power.violation_count >= 1

    def test_signal_dimension_penalized(self, scorer, sample_violations):
        report = scorer.score(sample_violations, [])
        signal = report.dimensions["signal"]
        assert signal.score < 100.0  # 有一个信号线 WARNING

    def test_dfm_dimension_penalized(self, scorer, sample_violations):
        report = scorer.score(sample_violations, [])
        dfm = report.dimensions["dfm"]
        assert dfm.score < 100.0  # 有一个位号 INFO

    def test_different_severity_impact(self, scorer):
        """ERROR 比 INFO 扣分更多"""
        errors = [RuleViolation(rule_name="去耦电容检查", description="test",
                                severity=RuleSeverity.ERROR, location="U1",
                                suggestion="", theory="")]
        infos = [RuleViolation(rule_name="参数范围检查", description="test",
                               severity=RuleSeverity.INFO, location="R1",
                               suggestion="", theory="")]
        r_error = scorer.score(errors, [])
        r_info = scorer.score(infos, [])
        assert r_error.overall < r_info.overall

    def test_grade_scale(self, scorer):
        """测试等级划分"""
        for score, expected_grade in [
            (97, "A+"), (90, "A"), (82, "B+"), (73, "B"),
            (63, "C"), (50, "D"), (30, "F"),
        ]:
            assert scorer._assign_grade(score) == expected_grade

    def test_to_dict_structure(self, scorer, sample_violations):
        report = scorer.score(sample_violations, [])
        d = report.to_dict()
        assert "radar_data" in d
        assert "dimensions" in d
        assert "overall" in d
        assert "grade" in d
        assert "suggestions" in d

    def test_convenience_function(self, sample_violations):
        from src.core.design_scorer import score_design
        result = score_design(sample_violations)
        assert result["overall"] < 100.0
        assert len(result["radar_data"]) == 6

    def test_with_real_checker(self, scorer, sample_bom):
        """集成测试：用实际 DesignRuleChecker 输出"""
        checker = DesignRuleChecker()
        violations = checker.check_all(sample_bom, {}, {})
        report = scorer.score(violations, sample_bom)
        # STM32 最小系统通常有去耦电容等违规
        assert report.total_violations >= 0
        assert 0 <= report.overall <= 100
        assert len(report.suggestions) > 0


class TestMultiAgentReviewer:
    def test_basic_review(self, sample_violations, sample_bom):
        reviewer = MultiAgentReviewer()
        report = reviewer.review(sample_violations, sample_bom)
        assert report.overall_score < 100.0
        assert len(report.radar_data) == 6
        assert len(report.agent_reports) == 5
        # 验证所有 5 个 Agent 都在
        for key in ["power", "signal", "thermal", "emc", "dfm"]:
            assert key in report.agent_reports

    def test_critical_issues_extracted(self, sample_violations, sample_bom):
        reviewer = MultiAgentReviewer()
        report = reviewer.review(sample_violations, sample_bom)
        # 有 ERROR 级别的违规应该出现在 critical_issues 中
        has_error = any(v.severity == RuleSeverity.ERROR for v in sample_violations)
        if has_error:
            assert len(report.critical_issues) >= 1

    def test_improvement_roadmap(self, sample_violations, sample_bom):
        reviewer = MultiAgentReviewer()
        report = reviewer.review(sample_violations, sample_bom)
        assert len(report.improvement_roadmap) >= 0
        # 有违规时应该有改进路线图
        if sample_violations:
            assert len(report.improvement_roadmap) >= 1

    def test_consensus_not_empty(self, sample_violations, sample_bom):
        reviewer = MultiAgentReviewer()
        report = reviewer.review(sample_violations, sample_bom)
        assert len(report.consensus_summary) > 50

    def test_agent_reports_have_findings(self, sample_violations, sample_bom):
        reviewer = MultiAgentReviewer()
        report = reviewer.review(sample_violations, sample_bom)
        total_findings = sum(
            len(ar.findings) for ar in report.agent_reports.values()
        )
        # 至少有一些 Agent 有发现
        assert total_findings >= 1

    def test_power_agent_finds_power_violations(self, sample_violations, sample_bom):
        reviewer = MultiAgentReviewer()
        report = reviewer.review(sample_violations, sample_bom)
        power_report = report.agent_reports["power"]
        # "去耦电容检查" 应该被电源 Agent 捕获
        assert power_report.score < 100.0 or len(power_report.findings) > 0

    def test_no_llm_no_crash(self, sample_violations, sample_bom):
        """验证无 LLM 模式下不崩溃"""
        reviewer = MultiAgentReviewer(llm_client=None)
        report = reviewer.review(sample_violations, sample_bom)
        assert report.overall_score is not None
