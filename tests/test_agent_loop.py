"""Agent Loop (Function Calling) 单元测试 — mock LLM API 响应"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.agent.llm_client import LLMClient
from src.agent.tools import ToolRegistry, ToolDef
from src.core.controller import AppController, CommandContext
from src.bom.parser import BOMItem


# ══════════════════════════════════════════════════════
#  Helpers — build mock API responses
# ══════════════════════════════════════════════════════


def _make_tool_response(tool_calls: list[dict]) -> dict:
    """构建含 tool_calls 的 API 响应"""
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            }
        }]
    }


def _make_text_response(content: str) -> dict:
    """构建纯文本的 API 响应"""
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": content,
            }
        }]
    }


def _tc(id_: str, name: str, arguments: dict) -> dict:
    """快捷构建 tool_call 对象"""
    return {
        "id": id_,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        }
    }


# ══════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════


@pytest.fixture
def tool_executor():
    """模拟工具执行器：返回工具名 + 参数摘要"""
    def _execute(name: str, args: dict) -> str:
        if name == "fail_tool":
            raise RuntimeError("Simulated tool failure")
        return f"[执行 {name}] 参数={json.dumps(args, ensure_ascii=False)}"
    return _execute


@pytest.fixture
def client(tool_executor):
    """创建带 tool_executor 的 LLMClient"""
    return LLMClient(
        api_key="test-key",
        base_url="https://test.api/v1",
        model="test-model",
        provider="deepseek",
        tool_executor=tool_executor,
    )


@pytest.fixture
def controller():
    """创建无 AI 的 controller（仅本地模式）"""
    return AppController(api_key="")


@pytest.fixture
def controller_with_data(controller):
    """加载了 BOM 数据的 controller"""
    controller.context.bom_items = [
        BOMItem(reference="R1,R2,R3", value="10kΩ", package="0603",
                part_number="C25804", description="贴片电阻", quantity=3),
        BOMItem(reference="C1,C2", value="100nF", package="0603",
                part_number="C1588", description="贴片电容", quantity=2),
    ]
    return controller


# ══════════════════════════════════════════════════════
#  Tests: chat_with_tools basic behavior
# ══════════════════════════════════════════════════════


class TestChatWithTools:
    """LLMClient.chat_with_tools 核心行为"""

    def test_single_tool_call_then_text(self, client):
        """一轮工具调用后 LLM 返回文本"""
        responses = [
            _make_tool_response([_tc("call_1", "merge_bom", {})]),
            _make_text_response("已合并 BOM，共 3 组元件。"),
        ]
        with patch.object(client, "_post", side_effect=responses):
            result = client.chat_with_tools(
                "合并BOM",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="你是 PCB 助手",
            )
        assert "合并 BOM" in result or "3 组" in result
        # 验证历史被记录
        assert len(client._history) == 2  # user + assistant

    def test_multi_tool_call(self, client):
        """两轮工具调用后 LLM 返回文本"""
        responses = [
            _make_tool_response([_tc("c1", "merge_bom", {})]),
            _make_tool_response([_tc("c2", "check_duplicates", {})]),
            _make_text_response("BOM 已合并并完成查重，无重复位号。"),
        ]
        with patch.object(client, "_post", side_effect=responses):
            result = client.chat_with_tools(
                "合并BOM并查重",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="你是 PCB 助手",
            )
        assert "合并" in result or "查重" in result

    def test_no_tool_needed(self, client):
        """LLM 直接返回文本，不调用工具"""
        responses = [
            _make_text_response("你好！有什么可以帮你的？"),
        ]
        with patch.object(client, "_post", side_effect=responses):
            tokens = []
            result = client.chat_with_tools(
                "你好",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="你是 PCB 助手",
                on_token=lambda t: tokens.append(t),
            )
        assert "你好" in result
        assert len(tokens) > 0  # on_token 被调用

    def test_max_iterations_guard(self, client):
        """达到 max_iterations 后终止"""
        # 每轮都返回 tool_calls，永不返回文本
        responses = [
            _make_tool_response([_tc(f"c{i}", "merge_bom", {})])
            for i in range(10)  # 远超 max_iterations
        ]
        with patch.object(client, "_post", side_effect=responses):
            result = client.chat_with_tools(
                "无限循环测试",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="测试",
                max_iterations=3,
            )
        assert "最大操作步数" in result or "已完成的操作" in result

    def test_tool_execution_error(self, client):
        """工具执行失败 → LLM 收到错误信息，可继续推理"""
        responses = [
            _make_tool_response([_tc("c1", "fail_tool", {})]),
            _make_text_response("工具调用失败，请检查后重试。"),
        ]
        with patch.object(client, "_post", side_effect=responses):
            result = client.chat_with_tools(
                "触发失败工具",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="测试",
                max_iterations=5,
            )
        assert "失败" in result or "重试" in result

    def test_history_preserved(self, client):
        """多轮对话时 use_history=True 附带历史"""
        # 第一轮
        responses_1 = [
            _make_text_response("第一轮回复"),
        ]
        with patch.object(client, "_post", side_effect=responses_1):
            client.chat_with_tools(
                "第一个问题",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="测试",
            )
        # 第二轮 — 传入的 messages 应包含第一轮历史
        responses_2 = [
            _make_text_response("第二轮回复"),
        ]
        with patch.object(client, "_post", side_effect=responses_2) as mock_post:
            client.chat_with_tools(
                "第二个问题",
                functions=ToolRegistry.get_function_definitions(),
                system_prompt="测试",
                use_history=True,
            )
            # 验证发送的 messages 包含历史
            call_args = mock_post.call_args[0][0]
            sent_messages = call_args["messages"]
            # 应有 system, user(第一个问题), assistant(第一轮回复), user(第二个问题)
            assert len(sent_messages) >= 4
            roles = [m["role"] for m in sent_messages]
            assert roles.count("user") >= 2
            assert "assistant" in roles

    def test_raises_without_tool_executor(self):
        """没有 tool_executor 时抛 RuntimeError"""
        bare_client = LLMClient(
            api_key="test-key",
            base_url="https://test.api/v1",
            model="test-model",
            provider="deepseek",
            # tool_executor 未设置
        )
        with pytest.raises(RuntimeError, match="tool_executor"):
            bare_client.chat_with_tools(
                "测试",
                functions=ToolRegistry.get_function_definitions(),
            )


# ══════════════════════════════════════════════════════
#  Tests: _build_tool_payload
# ══════════════════════════════════════════════════════


class TestBuildToolPayload:
    """_build_tool_payload 方法"""

    def test_basic_payload(self, client):
        messages = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "合并BOM"},
        ]
        functions = ToolRegistry.get_function_definitions()
        payload = client._build_tool_payload(messages, functions)

        assert payload["model"] == client.model
        assert payload["messages"] == messages
        assert payload["stream"] is False
        assert payload["tool_choice"] == "auto"
        assert "tools" in payload
        assert len(payload["tools"]) == len(functions)
        # 每条 tool 格式正确
        for tool in payload["tools"]:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]


# ══════════════════════════════════════════════════════
#  Tests: Controller.agent_loop integration
# ══════════════════════════════════════════════════════


class TestControllerAgentLoop:
    """Controller.agent_loop 集成测试"""

    def test_no_agent_available(self, controller):
        """未配置 API Key → 返回提示"""
        result = controller.agent_loop("合并BOM")
        assert "需要配置" in result or "API" in result

    def test_agent_loop_calls_chat_with_tools(self, controller_with_data):
        """agent_loop 正确委托给会话客户端的 chat_with_tools"""
        shared = MagicMock()           # is_agent_available 只看非 None
        shared.get_history.return_value = []
        controller_with_data.agent = shared

        session_client = MagicMock()
        session_client.get_history.return_value = []
        session_client.chat_with_tools.return_value = "Agent 完成：BOM 已合并。"
        # 会话租借按当前配置克隆客户端 —— 在工厂缝合点换桩
        controller_with_data._create_llm_client = lambda *a, **k: session_client

        tokens = []
        result = controller_with_data.agent_loop(
            "合并BOM并检查健康",
            on_token=lambda t: tokens.append(t),
        )

        assert "BOM" in result
        session_client.chat_with_tools.assert_called_once()
        call_kwargs = session_client.chat_with_tools.call_args[1]
        assert call_kwargs["user_message"] == "合并BOM并检查健康"
        assert len(call_kwargs["functions"]) > 0  # 传入了 function definitions
        assert call_kwargs["on_token"] is not None
        assert call_kwargs["max_iterations"] == 5  # 默认值
        assert controller_with_data._conversation_active is True

    def test_agent_loop_does_not_mutate_shared_agent(self, controller_with_data):
        """2026-10-07 回归：agent_loop 不得改写共享 self.agent 的 tool_executor。

        旧实现 self.agent.tool_executor = _executor —— 并发 agent_loop /
        流式对话 / 多智能体审查共用一个客户端，后到者覆盖前者的包装。
        """
        sentinel = lambda name, args: "ok"
        shared = MagicMock()
        shared.tool_executor = sentinel
        shared.get_history.return_value = []
        controller_with_data.agent = shared

        seen = []
        created = {}

        def fake_factory(*args, **kwargs):
            client = MagicMock()
            client.get_history.return_value = []
            client.chat_with_tools.return_value = "完成"
            created["executor"] = kwargs.get("tool_executor")
            return client

        controller_with_data._create_llm_client = fake_factory
        controller_with_data.agent_loop("测试", on_tool_call=lambda n, a: seen.append(n))

        # 共享客户端保持原样；执行器只进会话客户端
        assert shared.tool_executor is sentinel
        assert created["executor"] is not None
        assert created["executor"]("check_rule", {}) == controller_with_data._dispatch_operation("check_rule", {})
        assert seen == ["check_rule"]


# ══════════════════════════════════════════════════════
#  Tests: 会话级客户端租借（_llm_session）
# ══════════════════════════════════════════════════════


class TestLLMSession:
    """controller._llm_session — 会话级租借的隔离与合并语义"""

    def _controller_with_shared(self, controller):
        controller.agent = MagicMock()
        controller.agent.api_key = "sk-test"
        controller.agent.base_url = ""
        controller.agent.model = "test-model"
        controller.agent.provider_name = "deepseek"
        controller.agent.get_history.return_value = []
        return controller.agent

    def test_sessions_are_private_clients(self, controller):
        shared = self._controller_with_shared(controller)
        with controller._llm_session() as s1, controller._llm_session() as s2:
            assert s1 is not s2 and s1 is not shared
            # 各会话继承共享历史快照
            assert s1.get_history() == shared.get_history()

    def test_turns_merge_back_on_exit(self, controller):
        self._controller_with_shared(controller)
        turn = {"role": "user", "content": "新轮次"}
        with controller._llm_session() as session:
            session.extend_history([turn])
        controller.agent.extend_history.assert_called_once_with([turn])

    def test_merge_skipped_when_history_cleared_mid_session(self, controller):
        """租借期间用户清空对话/切助手 → 该会话轮次作废，不回流"""
        self._controller_with_shared(controller)
        with controller._llm_session() as session:
            session.extend_history([{"role": "user", "content": "迟到的轮次"}])
            controller.clear_conversation()
        assert controller.agent.get_history() == []

    def test_review_session_does_not_merge_back(self, controller):
        """审查轮次不进对话历史（五个 Agent 并发，回流只会污染上下文）"""
        self._controller_with_shared(controller)
        with controller._llm_session(merge_history=False) as session:
            session.extend_history([{"role": "user", "content": "审查提示词"}])
        controller.agent.extend_history.assert_not_called()

    def test_tool_executor_lands_on_session_client(self, controller):
        """自定义 tool_executor 只配到会话客户端"""
        self._controller_with_shared(controller)
        created = {}

        def fake_factory(*args, **kwargs):
            client = MagicMock()
            client.get_history.return_value = []
            created["executor"] = kwargs.get("tool_executor")
            return client

        controller._create_llm_client = fake_factory
        marker = lambda name, args: "ok"
        with controller._llm_session(tool_executor=marker):
            pass
        assert created["executor"] is marker

    def test_no_agent_yields_none(self, controller):
        """未配置 LLM（self.agent 为 None）→ 租借产出 None，调用方自行兜底"""
        with controller._llm_session() as session:
            assert session is None


# ══════════════════════════════════════════════════════
#  Tests: function definitions match dispatch
# ══════════════════════════════════════════════════════


class TestFunctionDispatchAlignment:
    """确保 function definitions 的名字与 controller dispatch map 一致"""

    def test_all_function_names_dispatchable(self, controller_with_data):
        """每个 function name 都能在 dispatch map 中找到 handler"""
        funcs = ToolRegistry.get_function_definitions()
        dispatch = controller_with_data._build_dispatch_map()

        for f in funcs:
            name = f["function"]["name"]
            assert name in dispatch, (
                f"Function '{name}' not in dispatch map. "
                f"Available: {list(dispatch.keys())}"
            )

    def test_special_handlers_resolvable(self, controller_with_data):
        """特殊 handler (_filter_input, _pcb_analysis_cmd 等) 可在 dispatch map 中找到"""
        dispatch = controller_with_data._build_dispatch_map()
        for name in ["filter_components", "pcb_analysis"]:
            assert name in dispatch, f"'{name}' missing from dispatch map"
