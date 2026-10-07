"""AppController 单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.core.controller import AppController, CommandContext
from src.bom.parser import BOMItem


# ——— fixtures ———

@pytest.fixture
def controller():
    """创建无 AI 的 controller（本地模式）"""
    return AppController(api_key="")


@pytest.fixture
def controller_with_data(controller):
    """加载了 BOM 数据的 controller"""
    controller.context.bom_items = [
        BOMItem(reference="R1,R2,R3", value="10kΩ", package="0603",
                part_number="C25804", description="贴片电阻", quantity=3),
        BOMItem(reference="C1,C2,C3,C6", value="100nF", package="0603",
                part_number="C1588", description="贴片电容", quantity=4),
        BOMItem(reference="U1", value="", package="LQFP-48",
                part_number="STM32F103C8T6", description="MCU", quantity=1),
        BOMItem(reference="R4,R5", value="1kΩ", package="0603",
                part_number="C21190", description="贴片电阻", quantity=2),
    ]
    return controller


# ——— _extract_json ———

class TestExtractJSON:
    def test_plain_json(self, controller):
        result = controller._extract_json('{"operation": "merge_bom", "params": {}}')
        assert result == {"operation": "merge_bom", "params": {}}

    def test_json_in_text(self, controller):
        text = '一些前言\n{"operation": "check_duplicates", "params": {"keyword": "R1"}}\n后续文字'
        result = controller._extract_json(text)
        assert result["operation"] == "check_duplicates"
        assert result["params"] == {"keyword": "R1"}

    def test_no_json(self, controller):
        assert controller._extract_json("没有 JSON 的纯文本") is None

    def test_malformed_json(self, controller):
        assert controller._extract_json('{"operation": "merge_bom", broken}') is None

    def test_nested_braces(self, controller):
        text = '{"operation": "filter", "params": {"ranges": [1, 2]}}'
        result = controller._extract_json(text)
        assert result["params"] == {"ranges": [1, 2]}

    def test_explanation_with_json(self, controller):
        text = '🤖 AI 理解: 需要合并 BOM\n{"operation": "merge_bom", "explanation": "用户要求合并", "params": {}}'
        result = controller._extract_json(text)
        assert result["explanation"] == "用户要求合并"


# ——— _match_keyword ———

class TestMatchKeyword:
    def test_chinese_merge(self, controller):
        handler = controller._match_keyword("合并 BOM")
        assert handler is not None
        assert handler.__name__ == "merge_bom"

    def test_english_merge(self, controller):
        handler = controller._match_keyword("merge")
        assert handler is not None
        assert handler.__name__ == "merge_bom"

    def test_validate(self, controller):
        handler = controller._match_keyword("校验封装")
        assert handler is not None
        assert handler.__name__ == "validate_packages"

    def test_duplicate(self, controller):
        handler = controller._match_keyword("检查重复位号")
        assert handler is not None
        assert handler.__name__ == "check_duplicates"

    def test_html(self, controller):
        handler = controller._match_keyword("生成网页")
        assert handler is not None
        assert handler.__name__ == "generate_html_bom"

    def test_design_rule(self, controller):
        handler = controller._match_keyword("设计规则检查")
        assert handler is not None
        assert handler.__name__ == "check_design_rules"

    def test_summary(self, controller):
        handler = controller._match_keyword("查看统计")
        assert handler is not None
        assert handler.__name__ == "_summary_report"

    def test_unknown_keyword(self, controller):
        assert controller._match_keyword("随机文本xyz") is None


# ——— _require_data ———

class TestRequireData:
    def test_no_data(self, controller):
        result = controller._require_data()
        assert result is not None
        assert "请先导入" in result

    def test_has_data(self, controller_with_data):
        result = controller_with_data._require_data()
        assert result is None


# ——— get_bom_summary ———

class TestGetBomSummary:
    def test_total(self, controller_with_data):
        summary = controller_with_data.get_bom_summary()
        assert summary["total"] == 4

    def test_prefix_groups(self, controller_with_data):
        summary = controller_with_data.get_bom_summary()
        assert summary["by_prefix"] == {"C": 1, "R": 2, "U": 1}

    def test_empty_data(self, controller):
        summary = controller.get_bom_summary()
        assert summary["total"] == 0
        assert summary["by_prefix"] == {}


# ——— _filter_components ———

class TestFilterComponents:
    def test_filter_by_reference(self, controller_with_data):
        result = controller_with_data._filter_components({"keyword": "R1"})
        assert "R1,R2,R3" in result
        assert "C1" not in result

    def test_filter_by_part_number(self, controller_with_data):
        result = controller_with_data._filter_components({"keyword": "C25804"})
        assert "10kΩ" in result

    def test_filter_by_package(self, controller_with_data):
        result = controller_with_data._filter_components({"keyword": "LQFP"})
        assert "STM32" in result

    def test_filter_no_match(self, controller_with_data):
        result = controller_with_data._filter_components({"keyword": "xyz123"})
        assert "未找到" in result

    def test_filter_empty_keyword(self, controller_with_data):
        result = controller_with_data._filter_components({"keyword": ""})
        assert "请指定" in result


# ——— _dispatch_operation ———

class TestDispatchOperation:
    def test_merge_bom(self, controller_with_data):
        result = controller_with_data._dispatch_operation("merge_bom", {})
        assert "合并报告" in result

    def test_validate_package(self, controller_with_data):
        result = controller_with_data._dispatch_operation("validate_package", {})
        assert "校验报告" in result

    def test_check_duplicates(self, controller_with_data):
        result = controller_with_data._dispatch_operation("check_duplicates", {})
        assert "无重复" in result

    def test_check_rule(self, controller_with_data):
        result = controller_with_data._dispatch_operation("check_rule", {})
        assert "设计规则检查" in result

    def test_unknown_operation(self, controller_with_data):
        result = controller_with_data._dispatch_operation("unknown_op", {})
        assert "无法识别" in result


# ——— _local_fallback ———

class TestLocalFallback:
    def test_valid_command(self, controller_with_data):
        result = controller_with_data._local_fallback("合并 BOM")
        assert "合并报告" in result

    def test_invalid_command(self, controller_with_data):
        result = controller_with_data._local_fallback("瞎写的内容")
        assert "无法识别指令" in result


# ——— process_input ———

class TestProcessInput:
    def test_no_data_blocks(self, controller):
        result = controller.process_input("合并 BOM")
        assert "请先导入" in result

    def test_local_fallback_works(self, controller_with_data):
        result = controller_with_data.process_input("统计概览")
        assert "BOM 元件统计" in result

    def test_process_input_unknown(self, controller_with_data):
        result = controller_with_data.process_input("xyz")
        assert "无法识别指令" in result


# ——— is_agent_available ———

class TestAgentStatus:
    def test_no_agent_without_key(self, controller):
        assert not controller.is_agent_available()

    def test_agent_created_with_key(self):
        c = AppController(api_key="sk-test-key-123456")
        # 即使有 key，网络不可达时 agent 仍然创建（仅 token 校验）
        assert c.is_agent_available()


# ——— char_ngram_similarity (new) ———


class TestCharNgramSimilarity:
    def test_identical_strings(self, controller):
        score = controller._char_ngram_similarity("合并BOM", "合并BOM")
        assert score == pytest.approx(1.0)

    def test_empty_string(self, controller):
        assert controller._char_ngram_similarity("", "") == 0.0

    def test_short_string(self, controller):
        assert controller._char_ngram_similarity("合", "合并", n=2) == 0.0

    def test_similar_chinese_bigrams(self, controller):
        score = controller._char_ngram_similarity("合饼BOM", "合并BOM", n=2)
        assert score > 0.2  # "BO"和"OM"重叠

    def test_different_strings(self, controller):
        score = controller._char_ngram_similarity("你好", "pcb布局")
        assert score < 0.3


# ——— _get_closest_commands (new) ———


class TestGetClosestCommands:
    def test_returns_ranked_suggestions(self, controller):
        suggestions = controller._get_closest_commands("合并BOM")
        assert len(suggestions) > 0
        # "合并" 应排最高
        assert suggestions[0][0] == "merge_bom"

    def test_empty_for_gibberish(self, controller):
        suggestions = controller._get_closest_commands("xyz123abc")
        assert len(suggestions) == 0


# ——— _method_label (new) ———


class TestMethodLabel:
    def test_known_method(self, controller):
        assert controller._method_label("merge_bom") == "合并BOM"
        assert controller._method_label("check_design_rules") == "设计规则检查"

    def test_unknown_falls_back(self, controller):
        assert controller._method_label("nonexistent") == "nonexistent"


# ——— _generate_drc_rule（2026-10-06 回归：context.conversation_history 不存在，
#      聊天/Agent Loop 触发必然 AttributeError）———

class _FakeLLM:
    """最小 LLM 客户端替身：记录 chat 调用，返回固定的规则代码。"""

    def __init__(self, reply: str = "", history: list | None = None):
        self._reply = reply
        self._history = history or []
        self.chat_calls: list[str] = []

    def chat(self, prompt, **kwargs):
        self.chat_calls.append(prompt)
        return self._reply

    def get_history(self):
        return list(self._history)

    def clear_history(self):
        self._history.clear()


class TestGenerateDrcRule:
    _CODE = 'def _check_led_limit(self, bom_items, positions, netlist):\n    """规则名称：LED 限流"""\n    return []'

    def test_dispatch_with_param_no_crash(self, controller):
        fake = _FakeLLM(reply=f"```python\n{self._CODE}\n```")
        controller.agent = fake
        result = controller._dispatch_operation(
            "generate_drc_rule", {"rule_description": "检查LED限流电阻"}
        )
        assert "python" in result
        assert "_check_led_limit" in result

    def test_falls_back_to_agent_history(self, controller):
        fake = _FakeLLM(
            reply=f"```python\n{self._CODE}\n```",
            history=[
                {"role": "user", "content": "帮我生成一个检查LED限流的规则"},
                {"role": "assistant", "content": "好的"},
            ],
        )
        controller.agent = fake
        # 不传参数 → 应回落读历史里最后一条用户消息
        result = controller._dispatch_operation("generate_drc_rule", {})
        assert "python" in result
        assert "检查LED限流" in fake.chat_calls[0]

    def test_no_desc_no_history_returns_guidance(self, controller):
        fake = _FakeLLM(reply=self._CODE, history=[])
        controller.agent = fake
        result = controller._dispatch_operation("generate_drc_rule", {})
        assert "请先描述" in result
        assert fake.chat_calls == []   # 未调 LLM

    def test_no_llm_returns_guard(self, controller):
        controller.agent = None
        result = controller._dispatch_operation(
            "generate_drc_rule", {"rule_description": "x"}
        )
        assert "API Key" in result or "AI 模型" in result


# ——— default_output_dir（2026-10-07 回归：endpoints.py 曾用 Path.cwd()
#      反推输出目录，与 controller 的落盘目录漂移，path 恒为空串）———

class TestDefaultOutputDir:
    def test_generate_html_bom_writes_into_default_output_dir(self, controller_with_data, monkeypatch):
        from src.core import controller as ctrl_mod

        captured = {}

        def fake_generate(self, bom_items, positions, output_path):
            captured["path"] = Path(output_path)

        monkeypatch.setattr(ctrl_mod.HTMLBOMGenerator, "generate", fake_generate)
        controller_with_data.generate_html_bom()

        assert captured["path"].parent == ctrl_mod.default_output_dir()
        assert captured["path"].name == "ibom.html"

    def test_export_bom_csv_writes_into_default_output_dir(self, controller_with_data, monkeypatch):
        from src.core import controller as ctrl_mod

        captured = {}

        def fake_open(file, *a, **k):
            captured["path"] = Path(file)
            import io
            return io.StringIO()

        # load_bom 前置校验已过，直接拦截 open 截获落盘路径
        monkeypatch.setattr("builtins.open", fake_open)
        controller_with_data.context.bom_file = "demo.csv"
        controller_with_data.export_bom_csv()

        assert captured["path"].parent == ctrl_mod.default_output_dir()

    def test_frozen_output_dir_goes_to_app_home(self, monkeypatch, tmp_path):
        """打包版（sys.frozen）：_MEIPASS 是解包临时目录、退出即清空，
        导出文件必须落到 EDA_AI_HOME（app_home()）/output。"""
        from src.core import controller as ctrl_mod

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("EDA_AI_HOME", str(tmp_path))
        assert ctrl_mod.default_output_dir() == tmp_path / "output"

    def test_dev_output_dir_anchors_at_repo_root(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        from src.core import controller as ctrl_mod

        assert ctrl_mod.default_output_dir() == PROJECT_ROOT / "output"


# ——— reconfigure_llm 回写 config.llm（2026-10-07 回归：config.llm 是
#      导入时读一次 settings.json 的缓存，reconfigure 原来只换 controller.agent
#      → get_llm_config（Eel）/ GET /llm/config（REST）永远显示启动时的旧配置，
#      改完设置不重启就不刷新）———

class TestReconfigureSyncsGlobalConfig:
    def test_with_key_mirrors_effective_client(self, controller):
        from src.config import config

        controller.reconfigure_llm("deepseek", "sk-test-sync",
                                   "https://example.com/v1", "m-sync")
        assert config.llm.api_key == "sk-test-sync"
        assert config.llm.provider == "deepseek"
        assert config.llm.base_url == "https://example.com/v1"
        assert config.llm.model == "m-sync"
        assert config.llm.is_configured is True

    def test_with_key_empty_url_model_resolved_from_preset(self, controller):
        from src.config import config

        controller.reconfigure_llm("deepseek", "sk-test-sync", "", "")
        # 客户端按预设解析 —— config.llm 必须与客户端实际生效值一致
        assert config.llm.base_url == "https://api.deepseek.com/v1"
        assert config.llm.model == "deepseek-flash"

    def test_without_key_resets_and_falls_back_to_preset(self, controller):
        from src.config import config

        controller.reconfigure_llm("deepseek", "", "", "")
        assert config.llm.api_key == ""
        assert config.llm.is_configured is False
        assert config.llm.provider == "deepseek"
        assert config.llm.base_url == "https://api.deepseek.com/v1"

    def test_claude_mirror_matches_preset_messages_url(self, controller):
        from src.config import config

        controller.reconfigure_llm("claude", "sk-cl", "", "")
        # AnthropicClient 会补 /messages 后缀；预设本身就是该 URL，两边必须相等
        assert config.llm.base_url == "https://api.anthropic.com/v1/messages"
        assert config.llm.provider == "claude"
