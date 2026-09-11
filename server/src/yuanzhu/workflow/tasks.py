"""工作流异步任务表：run-async 提交 → 后台执行 → status 轮询真实进度"""
import uuid
from typing import Any, Callable, Dict, Optional

# 全局任务表（v0.1.4 单进程内存——够用；多进程部署时换 Redis）
_TASKS: Dict[str, Dict[str, Any]] = {}


def create_task() -> str:
    task_id = uuid.uuid4().hex[:12]
    _TASKS[task_id] = {
        "done": False, "status": "running", "error": None,
        "done_steps": [],        # 已完成步骤 id（真实进度）
        "result": None,
    }
    return task_id


def update_task(task_id: str, **fields) -> None:
    if task_id in _TASKS:
        _TASKS[task_id].update(fields)


def add_step_done(task_id: str, step_id: str) -> None:
    if task_id in _TASKS:
        _TASKS[task_id]["done_steps"].append(step_id)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    return _TASKS.get(task_id)
