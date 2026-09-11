"""节点 / 任务 / 模板 REST API（dsh-edge 与 Web 控制台的前置接口，ADR-003）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel
from pathlib import Path

from yuanzhu.db.database import get_db
from yuanzhu.node.store import NodeStore
from yuanzhu.node.models import NodeCreate, NodeHeartbeat, NodeResponse
from yuanzhu.task.orchestrator import TaskOrchestrator
from yuanzhu.task.models import TaskCreate, TaskStatusUpdate, TaskResponse
from yuanzhu.template.store import TemplateStore

router = APIRouter(prefix="/api", tags=["core"])


# ---------- 节点 ----------

@router.post("/nodes/register", response_model=NodeResponse)
async def register_node(body: NodeCreate, db: AsyncSession = Depends(get_db)):
    return await NodeStore(db).register(body)


@router.post("/nodes/{node_id}/heartbeat", response_model=NodeResponse)
async def node_heartbeat(node_id: int, body: NodeHeartbeat, db: AsyncSession = Depends(get_db)):
    try:
        return await NodeStore(db).heartbeat(node_id, body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/nodes", response_model=list[NodeResponse])
async def list_nodes(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    return await NodeStore(db).list(status=status)


# ---------- 任务 ----------

@router.post("/tasks", response_model=TaskResponse)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    return await TaskOrchestrator(db).create(body)


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    node_id: Optional[int] = None,
    created_by: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await TaskOrchestrator(db).list(status=status, node_id=node_id, created_by=created_by)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await TaskOrchestrator(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks/{task_id}/dispatch/{node_id}", response_model=TaskResponse)
async def dispatch_task(task_id: int, node_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await TaskOrchestrator(db).dispatch(task_id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/report", response_model=TaskResponse)
async def report_task(task_id: int, body: TaskStatusUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await TaskOrchestrator(db).report(task_id, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/{node_id}/tasks/pull", response_model=list[TaskResponse])
async def pull_tasks(node_id: int, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """dsh-edge 拉任务（pull 模式）"""
    return await TaskOrchestrator(db).pull(node_id, limit=limit)


# ---------- 模板 ----------

class TemplateRegisterRequest(BaseModel):
    path: str  # v0.1 本地目录注册；zip 上传留后续里程碑


# 模板注册根白名单（I3 防注入；v0.2：包内内置模板 + 用户目录 forge 产物）
from pathlib import Path as _PP
_TEMPLATE_BUILTIN = _PP(__file__).resolve().parents[1] / "templates"          # src/yuanzhu/templates
_TEMPLATE_USER = _PP.home() / ".yuanzhu" / "templates"
TEMPLATE_ROOTS = [_TEMPLATE_BUILTIN, _TEMPLATE_USER]


@router.post("/templates/register")
async def register_template(body: TemplateRegisterRequest, db: AsyncSession = Depends(get_db)):
    tpl_dir = Path(body.path).resolve()
    if not tpl_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"模板目录不存在: {body.path}")
    if not any(tpl_dir.is_relative_to(root.resolve()) for root in TEMPLATE_ROOTS if root.is_dir()):
        raise HTTPException(
            status_code=400,
            detail=f"模板目录必须在服务端 templates/ 白名单根之下（收到: {body.path}）",
        )
    try:
        return await TemplateStore(db).register_dir(tpl_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/metaflow/suggest-workflow")
async def suggest_workflow(body: dict, db: AsyncSession = Depends(get_db)):
    """T4 重复模式检测：分析近期问答历史，发现例行公事模式 → 建议铸工作流。

    返回 {suggested, reason, description}——description 可直接喂 /api/templates/forge。
    """
    from sqlalchemy import select as _sel
    from yuanzhu.db.models import Object, ObjectType
    # 取 metaflow 域已采纳的 Answer（问答历史）
    at = (await db.execute(_sel(ObjectType).where(
        ObjectType.domain == "metaflow", ObjectType.name == "Answer"))).scalar_one_or_none()
    if not at:
        return {"suggested": False, "reason": "还没有问答历史"}
    objs = (await db.execute(
        _sel(Object).where(Object.type_id == at.id).order_by(Object.created_at.desc()).limit(20)
    )).scalars().all()
    history = [
        {"question": (o.properties or {}).get("question", ""),
         "adopted": bool((o.properties or {}).get("adopted_by"))}
        for o in objs if (o.properties or {}).get("question")
    ]
    adopted = [h for h in history if h["adopted"]]
    if len(history) < 3:
        return {"suggested": False, "reason": f"问答历史不足（{len(history)}/3）——多问几次我才能发现你的例行公事"}

    import json as _json
    from yuanzhu.workflow.engine import call_model
    prompt = (
        "你是工作模式分析师。分析用户的问答历史（按时间倒序），判断是否存在**例行公事模式**"
        "（同类问题反复出现≥3次，如周报汇总/数据整理/例行检查）。\n\n"
        "严格按 JSON 输出：\n"
        '{"suggested": true/false,\n'
        ' "reason": "中文理由（给用户看，提具体问题主题和次数）",\n'
        ' "description": "如果建议，生成一段第一人称的工作描述（可直接用于铸工作流模板），'
        '如：我每周五需要收集各小组的工作进展……"}\n'
        "不建议就 suggested:false，description 留空。只输出 JSON。\n\n"
        f"问答历史：{_json.dumps(history, ensure_ascii=False)}"
    )
    try:
        content = await call_model("glm-5.1", prompt, session=db, caller="suggest-workflow")
        start, end = content.find("{"), content.rfind("}")
        result = _json.loads(content[start:end + 1])
        return {"suggested": bool(result.get("suggested")),
                "reason": result.get("reason", ""),
                "description": result.get("description", "")}
    except Exception as e:
        return {"suggested": False, "reason": f"分析失败: {e}"}


class ForgeRequest(BaseModel):
    description: str


@router.post("/templates/forge")
async def forge_template_endpoint(body: ForgeRequest, db: AsyncSession = Depends(get_db)):
    """一句话铸模板：AI 生成四段式 → evals 守门 → 全过自动上架"""
    if len(body.description.strip()) < 6:
        raise HTTPException(status_code=400, detail="描述太短，说说你要处理的日常工作（谁/做什么/产出什么）")
    from yuanzhu.template.forge import forge_template
    try:
        return await forge_template(db, body.description.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class ReloadRequest(BaseModel):
    name: str


@router.post("/templates/reload")
async def reload_template_endpoint(body: ReloadRequest, db: AsyncSession = Depends(get_db)):
    """草稿转正：人工修正目录后重跑评测守门"""
    from yuanzhu.template.forge import reload_template
    try:
        return await reload_template(db, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates")
async def list_templates(domain: Optional[str] = None, status: Optional[str] = None,
                         db: AsyncSession = Depends(get_db)):
    return await TemplateStore(db).list(domain=domain, status=status)


# ---------- 用量与审计 ----------

@router.get("/usage")
async def usage_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """模型用量汇总（按模型分组：调用数/token/估费）+ 最近明细"""
    from datetime import timedelta
    from sqlalchemy import func as sa_func, select as sa_select
    from yuanzhu.db.models import ModelUsage, utcnow

    cutoff = utcnow() - timedelta(days=days)
    grouped = await db.execute(
        sa_select(
            ModelUsage.model,
            sa_func.count(ModelUsage.id),
            sa_func.sum(ModelUsage.prompt_tokens),
            sa_func.sum(ModelUsage.completion_tokens),
            sa_func.sum(ModelUsage.estimated_cost),
        ).where(ModelUsage.created_at >= cutoff).group_by(ModelUsage.model)
    )
    summary = [
        {
            "model": row[0], "calls": row[1],
            "prompt_tokens": row[2] or 0, "completion_tokens": row[3] or 0,
            "estimated_cost": row[4] or 0.0,
        }
        for row in grouped.all()
    ]

    recent = await db.execute(
        sa_select(ModelUsage).where(ModelUsage.created_at >= cutoff)
        .order_by(ModelUsage.created_at.desc()).limit(50)
    )
    details = [
        {
            "id": u.id, "model": u.model, "task_id": u.task_id, "caller": u.caller,
            "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
            "estimated_cost": u.estimated_cost, "created_at": u.created_at.isoformat(),
        }
        for u in recent.scalars().all()
    ]
    return {"days": days, "summary": summary, "recent": details}


# ---------- 工作流触发（H2：模板市场「使用」按钮的后端） ----------

class WorkflowRunRequest(BaseModel):
    domain: str
    workflow: str
    params: dict = {}
    run_by: str = "web-user"


@router.post("/workflows/run")
async def run_workflow(req: WorkflowRunRequest, db: AsyncSession = Depends(get_db)):
    """触发工作流（单机模式进程内执行；ai_step 走网关、action_step 走 staged）"""
    from yuanzhu.workflow.engine import WorkflowEngine
    try:
        return await WorkflowEngine(db).run(
            domain=req.domain, workflow_name=req.workflow,
            params=req.params, run_by=req.run_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
