"""ToolRegistry 单元测试 — 统一工具注册表"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.agent.tools import ToolDef, ToolRegistry, TOOLS


# ——— 注册表完整性 ———


class TestRegistryIntegrity:
    def test_has_all_tools(self):
        assert ToolRegistry.count() == 22

    def test_all_tools_have_names(self):
        for t in ToolRegistry.get_all():
            assert t.name
            assert isinstance(t.name, str)

    def test_all_tools_have_labels(self):
        for t in ToolRegistry.get_all():
            assert t.label
            assert isinstance(t.label, str)

    def test_all_tools_have_descriptions(self):
        for t in ToolRegistry.get_all():
            assert len(t.description) > 10, f"{t.name} description too short"

    def test_all_tools_have_keywords(self):
        for t in ToolRegistry.get_all():
            assert len(t.keywords) >= 3, f"{t.name} needs >= 3 keywords"

    def test_all_tools_have_intent(self):
        valid_intents = {"BOM_ANALYSIS", "BOM_HEALTH", "RULE_CHECK", "PCB_ANALYSIS",
                         "CODE_RULE_GEN", "REPORT_GEN", "COMPONENT_LOOKUP",
                         "LOCAL_ONLY", "VISUAL"}
        for t in ToolRegistry.get_all():
            assert t.intent in valid_intents, f"{t.name} intent {t.intent} not in {valid_intents}"

    def test_all_tools_have_handler(self):
        for t in ToolRegistry.get_all():
            assert t.handler, f"{t.name} missing handler"

    def test_no_duplicate_names(self):
        names = [t.name for t in ToolRegistry.get_all()]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"


# ——— 查询方法 ———


class TestQueries:
    def test_get_by_name_found(self):
        t = ToolRegistry.get_by_name("merge_bom")
        assert t is not None
        assert t.label == "合并BOM"
        assert t.intent == "BOM_ANALYSIS"

    def test_get_by_name_not_found(self):
        assert ToolRegistry.get_by_name("nonexistent") is None

    def test_get_by_intent(self):
        bom_tools = ToolRegistry.get_by_intent("BOM_ANALYSIS")
        assert len(bom_tools) >= 5  # merge, ai_merge, validate, duplicates, filter

    def test_get_by_category(self):
        pcb_tools = ToolRegistry.get_by_category("pcb")
        names = [t.name for t in pcb_tools]
        assert "check_rule" in names
        assert "pcb_analysis" in names

    def test_get_labels(self):
        labels = ToolRegistry.get_labels()
        assert labels["merge_bom"] == "合并BOM"
        assert labels["check_rule"] == "设计规则检查"

    def test_get_label(self):
        assert ToolRegistry.get_label("merge_bom") == "合并BOM"
        assert ToolRegistry.get_label("nonexistent") == "nonexistent"


# ——— 派生数据 ———


class TestDerivedData:
    def test_keyword_map_structure(self):
        km = ToolRegistry.get_keyword_map()
        assert len(km) >= 19  # all tools with keywords
        # ai_merge_bom 应在 merge_bom 之前（优先级）
        names = [name for _, name in km]
        ai_idx = names.index("ai_merge_bom")
        merge_idx = names.index("merge_bom")
        assert ai_idx < merge_idx, "ai_merge_bom must precede merge_bom"

    def test_keywords_by_intent(self):
        kw = ToolRegistry.get_keywords_by_intent("BOM_ANALYSIS")
        assert "bom" in kw or "合并" in kw
        assert len(kw) > 20

    def test_dispatch_map(self):
        dm = ToolRegistry.get_dispatch_map()
        assert dm["merge_bom"] == "merge_bom"  # handler same as name
        assert dm["validate_package"] == "validate_packages"  # handler differs
        assert dm["check_rule"] == "check_design_rules"  # handler differs

    def test_operation_descriptions(self):
        desc = ToolRegistry.get_operation_descriptions()
        assert "- merge_bom:" in desc
        assert "- check_rule:" in desc
        assert "用途：" in desc

    def test_help_text(self):
        help_text = ToolRegistry.get_help_text()
        assert "可用指令" in help_text
        assert "合并BOM" in help_text
        assert "设计规则检查" in help_text

    def test_function_definitions(self):
        funcs = ToolRegistry.get_function_definitions()
        assert len(funcs) >= 22  # all tools have function definitions
        for f in funcs:
            assert f["type"] == "function"
            assert "name" in f["function"]
            assert "description" in f["function"]

    def test_list_names(self):
        names = ToolRegistry.list_names()
        assert "merge_bom" in names
        assert "bom_health" in names
        assert "analyze_image" in names
        assert "component_lookup" in names
        assert "calc_trace_width" in names
        assert len(names) == 22


# ——— ToolDef 方法 ———


class TestToolDefMethods:
    def test_to_function_definition(self):
        t = ToolDef(
            name="test_tool", label="测试", description="测试工具",
            keywords=("测试",), intent="LOCAL_ONLY", handler="_test",
            params_schema={
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
        )
        fd = t.to_function_definition()
        assert fd["type"] == "function"
        assert fd["function"]["name"] == "test_tool"
        assert fd["function"]["description"] == "测试工具"
        assert "param1" in fd["function"]["parameters"]["properties"]
        assert "param1" in fd["function"]["parameters"]["required"]


# ——— 一致性验证 ———


class TestConsistency:
    def test_validate_package_handler(self):
        """validate_package 的 handler 指向 validate_packages（复数）"""
        t = ToolRegistry.get_by_name("validate_package")
        assert t.handler == "validate_packages"

    def test_check_rule_handler(self):
        """check_rule 的 handler 指向 check_design_rules"""
        t = ToolRegistry.get_by_name("check_rule")
        assert t.handler == "check_design_rules"

    def test_no_generic_keyword_in_rule_check(self):
        """RULE_CHECK 工具不应含 '检查' 这个过于通用的关键词"""
        t = ToolRegistry.get_by_name("check_rule")
        assert "检查" not in t.keywords, "'检查' is too generic for intent classification"

    def test_ai_merge_has_priority_over_merge(self):
        """ai_merge_bom 的 'ai合并' 比 merge_bom 的 '合并' 更具体"""
        ai_t = ToolRegistry.get_by_name("ai_merge_bom")
        merge_t = ToolRegistry.get_by_name("merge_bom")
        assert "ai合并" in ai_t.keywords
        assert "合并" in merge_t.keywords

    def test_analyze_image_registered(self):
        """analyze_image 工具已注册"""
        t = ToolRegistry.get_by_name("analyze_image")
        assert t is not None
        assert t.intent == "VISUAL"
        assert t.category == "vision"
        assert not t.requires_data  # 图片分析不需要 BOM
        assert t.handler == "_analyze_image"
        assert len(t.keywords) >= 3

    def test_analyze_image_has_params_schema(self):
        """analyze_image 需要 image_data 参数"""
        t = ToolRegistry.get_by_name("analyze_image")
        assert "image_data" in t.params_schema.get("required", [])
