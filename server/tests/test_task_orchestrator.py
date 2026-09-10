"""任务编排测试（ADR-003：创建→排队→分发→状态机 pending→dispatched→running→done/failed）"""
import pytest

from yuanzhu.task.orchestrator import TaskOrchestrator
from yuanzhu.task.models import TaskCreate, TaskStatusUpdate
from yuanzhu.node.store import NodeStore
from yuanzhu.node.models import NodeCreate


async def test_create_task(db_session):
    orch = TaskOrchestrator(db_session)
    task = await orch.create(TaskCreate(
        template_id=None, params={"input": "data"}, created_by="tester",
    ))
    assert task.id is not None
    assert task.status == "pending"
    assert task.params_json == {"input": "data"}


async def test_dispatch_to_online_node(db_session):
    orch = TaskOrchestrator(db_session)
    nodes = NodeStore(db_session)
    node = await nodes.register(NodeCreate(name="worker-1", token="t1"))

    task = await orch.create(TaskCreate(params={}, created_by="t"))
    dispatched = await orch.dispatch(task.id, node.id)
    assert dispatched.status == "dispatched"
    assert dispatched.assigned_node_id == node.id


async def test_dispatch_to_offline_node_rejected(db_session):
    orch = TaskOrchestrator(db_session)
    nodes = NodeStore(db_session)
    node = await nodes.register(NodeCreate(name="dead", token="t2"))
    await nodes.update_status(node.id, "offline")

    task = await orch.create(TaskCreate(params={}))
    with pytest.raises(ValueError, match="不在线"):
        await orch.dispatch(task.id, node.id)


async def test_pull_marks_running(db_session):
    """节点 pull：分派给它的任务被拉走并标记 running"""
    orch = TaskOrchestrator(db_session)
    nodes = NodeStore(db_session)
    node = await nodes.register(NodeCreate(name="worker-2", token="t3"))

    for i in range(3):
        t = await orch.create(TaskCreate(params={"i": i}))
        await orch.dispatch(t.id, node.id)

    pulled = await orch.pull(node.id)
    assert len(pulled) == 3
    assert all(t.status == "running" for t in pulled)


async def test_state_machine_transitions(db_session):
    from yuanzhu.task.state_machine import TaskStateMachine
    sm = TaskStateMachine(db_session)
    orch = TaskOrchestrator(db_session)

    task = await orch.create(TaskCreate(params={}))
    t = await sm.transition(task.id, "dispatched")
    assert t.status == "dispatched"
    t = await sm.transition(task.id, "running")
    assert t.status == "running"
    t = await sm.transition(task.id, "done")
    assert t.status == "done"
    assert t.completed_at is not None

    # 终态不可再转
    with pytest.raises(ValueError, match="非法"):
        await sm.transition(task.id, "running")


async def test_illegal_transition(db_session):
    from yuanzhu.task.state_machine import TaskStateMachine
    sm = TaskStateMachine(db_session)
    orch = TaskOrchestrator(db_session)
    task = await orch.create(TaskCreate(params={}))

    with pytest.raises(ValueError, match="非法"):
        await sm.transition(task.id, "done")  # pending 不能直接 done


async def test_report_result(db_session):
    """任务完成回报：结果落库 + 终态"""
    orch = TaskOrchestrator(db_session)
    nodes = NodeStore(db_session)
    node = await nodes.register(NodeCreate(name="w", token="t4"))
    task = await orch.create(TaskCreate(params={}))
    await orch.dispatch(task.id, node.id)
    await orch.pull(node.id)

    done = await orch.report(
        task.id,
        TaskStatusUpdate(status="done", result={"output": "报告产出"}, exec_log={"steps": 5}),
    )
    assert done.status == "done"
    assert done.result_json["output"] == "报告产出"
    assert done.exec_log_json["steps"] == 5


async def test_list_tasks_filter(db_session):
    orch = TaskOrchestrator(db_session)
    nodes = NodeStore(db_session)
    node = await nodes.register(NodeCreate(name="w5", token="t5"))
    t1 = await orch.create(TaskCreate(params={}, created_by="alice"))
    t2 = await orch.create(TaskCreate(params={}, created_by="bob"))
    await orch.dispatch(t2.id, node.id)

    mine = await orch.list(created_by="alice")
    assert all(t.created_by == "alice" for t in mine)
    node_tasks = await orch.list(node_id=node.id)
    assert any(t.id == t2.id for t in node_tasks)
