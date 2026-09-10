"""节点管理模块测试（ADR-003：注册/心跳/在线状态/能力标签）"""
import pytest

from yuanzhu.node.store import NodeStore
from yuanzhu.node.models import NodeCreate, NodeHeartbeat


async def test_register_node(db_session):
    store = NodeStore(db_session)
    node = await store.register(NodeCreate(
        name="test-node-1",
        token="node-token-123",
        capabilities={"os": "windows", "dsh": True, "gpu": False},
    ))
    assert node.id is not None
    assert node.status == "online"
    assert node.capabilities["os"] == "windows"
    assert node.last_heartbeat is not None


async def test_register_upsert(db_session):
    """同名节点重复注册 = 更新（重装场景）"""
    store = NodeStore(db_session)
    n1 = await store.register(NodeCreate(name="node-1", token="t1"))
    n2 = await store.register(NodeCreate(
        name="node-1", token="t2", capabilities={"dsh": True},
    ))
    assert n2.id == n1.id
    assert n2.token == "t2"
    assert n2.capabilities == {"dsh": True}


async def test_heartbeat_updates(db_session):
    store = NodeStore(db_session)
    node = await store.register(NodeCreate(name="node-2", token="t"))
    updated = await store.heartbeat(node.id, NodeHeartbeat(
        status="busy",
        current_task_id=42,
        resource_usage={"cpu": 45.2, "memory": 60.5},
    ))
    assert updated.status == "busy"
    assert updated.current_task_id == 42
    assert updated.resource_usage["cpu"] == 45.2


async def test_heartbeat_unknown_node(db_session):
    store = NodeStore(db_session)
    with pytest.raises(ValueError, match="不存在"):
        await store.heartbeat(9999, NodeHeartbeat())


async def test_list_by_status(db_session):
    store = NodeStore(db_session)
    for i in range(3):
        await store.register(NodeCreate(name=f"n{i}", token=f"t{i}"))
    await store.update_status(2, "offline")

    online = await store.list(status="online")
    assert {n.name for n in online} == {"n0", "n2"}
    all_nodes = await store.list()
    assert len(all_nodes) == 3


async def test_get_by_name(db_session):
    store = NodeStore(db_session)
    await store.register(NodeCreate(name="solo", token="tk"))
    found = await store.get_by_name("solo")
    assert found is not None and found.name == "solo"
    assert await store.get_by_name("ghost") is None


async def test_mark_stale_offline(db_session):
    """心跳超时的节点被标离线（健康检查的底层能力）"""
    store = NodeStore(db_session)
    node = await store.register(NodeCreate(name="stale-node", token="t"))
    # 模拟心跳过期：last_heartbeat 置为很久以前
    from datetime import datetime, timezone, timedelta
    node.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=300)
    await db_session.flush()

    count = await store.mark_stale_offline(timeout_seconds=60)
    assert count == 1
    assert (await store.get(node.id)).status == "offline"
