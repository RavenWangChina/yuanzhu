"""v0.2.1 MCP 工具注解（M8ven 审计发现）：每个工具必须声明四个 hint（显式布尔）

OpenAI 目录拒收缺注解的工具；M8ven 信任分也计入。
"""
import pytest

from yuanzhu.mcp.tools import APPROVAL_TOOLS, MCPToolGenerator

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def _assert_hints(tool: dict, name: str):
    ann = tool.get("annotations")
    assert isinstance(ann, dict), f"{name} 缺 annotations"
    for h in HINTS:
        v = ann.get(h, "MISSING")
        assert isinstance(v, bool), f"{name}.{h} 非布尔: {v!r}"


async def test_approval_tools_have_all_hints():
    """审批三件套：每工具四 hint 显式布尔"""
    for t in APPROVAL_TOOLS:
        _assert_hints(t, t["name"])


async def test_query_tool_hints_readonly(db_session, sample_object_type):
    tool = await MCPToolGenerator(db_session).generate_query_tool(sample_object_type.id)
    _assert_hints(tool, tool["name"])
    ann = tool["annotations"]
    assert ann["readOnlyHint"] is True and ann["destructiveHint"] is False
    assert ann["idempotentHint"] is True and ann["openWorldHint"] is False


async def test_action_tool_hints_write(db_session, sample_action_type):
    tool = await MCPToolGenerator(db_session).generate_action_tool(sample_action_type.id)
    _assert_hints(tool, tool["name"])
    ann = tool["annotations"]
    assert ann["readOnlyHint"] is False
    # 元铸工坊动作全是 set/create_object（staged 可 revert），无破坏性删除——false
    assert ann["destructiveHint"] is False
    assert ann["openWorldHint"] is False


async def test_list_tools_all_annotated(db_session, sample_object_type, sample_action_type):
    """全量工具清单：无一漏注"""
    tools = await MCPToolGenerator(db_session).list_tools()
    assert tools
    for t in tools:
        _assert_hints(t, t["name"])
