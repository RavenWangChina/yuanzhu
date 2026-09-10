"""SubmissionCriteriaValidator：运行时语义校验（DMLA 分层——Schema 管格式，criteria 管语义）

criteria 结构（spec 3.1）：
    {
      "object_ref": "params.object_id",      # 参数中的对象引用路径
      "check": {"properties.status": "Open"} # 对该对象断言：路径 → 期望值
    }
"""
from typing import Any, Dict

from yuanzhu.ontology.object_store import ObjectStore


def _dig(data: Dict[str, Any], path: str) -> Any:
    """按点分路径取值：params.object_id → params["object_id"]"""
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


class SubmissionCriteriaError(ValueError):
    """语义校验不通过（对象状态不满足动作前置条件）"""


async def validate_submission_criteria(
    criteria: Dict[str, Any], params: Dict[str, Any], object_store: ObjectStore
) -> None:
    """校验动作参数引用的对象是否满足前置状态条件"""
    if not criteria:
        return

    object_ref = criteria.get("object_ref")
    check = criteria.get("check", {})
    if not object_ref or not check:
        return

    # DSL 写法 "params.object_id"，params 本身就是根——剥前缀
    if object_ref.startswith("params."):
        object_ref = object_ref[len("params."):]
    obj_id = _dig(params, object_ref)
    obj = await object_store.get_object(int(obj_id))
    if not obj:
        raise SubmissionCriteriaError(f"submission_criteria 校验失败：对象不存在 {obj_id}")

    for check_path, expected in check.items():
        # check 路径相对对象根：properties.status → obj.properties_json["status"]
        node: Any = obj
        try:
            if check_path.startswith("properties."):
                node = _dig(obj.properties or {}, check_path[len("properties."):])
            else:
                node = _dig({"id": obj.id, "title": obj.title}, check_path)
        except KeyError:
            raise SubmissionCriteriaError(
                f"submission_criteria 校验失败：对象 {obj_id} 缺少路径 {check_path}"
            )
        if node != expected:
            raise SubmissionCriteriaError(
                f"submission_criteria 校验失败：对象 {obj_id} 的 {check_path}={node!r}，"
                f"要求 {expected!r}（状态不满足动作前置条件）"
            )
