"""本体层数据模型（spec 3.1：对象/链接/动作 + staged writes）

时间约定：数据库时间一律 UTC（datetime.now(timezone.utc)）。
Windows Git Bash 的 date 输出是 UTC，但权威时间源以 PowerShell 为准——
代码内不依赖 shell date，统一用 timezone aware 的 utcnow()。
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from yuanzhu.db.database import Base


def utcnow():
    """UTC 时间戳（timezone aware）"""
    return datetime.now(timezone.utc)


class ObjectType(Base):
    """对象类型定义（领域无关的元模型）"""
    __tablename__ = "object_type"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    title_key = Column(String(100), nullable=True)          # 标题属性名（用于显示）
    description = Column(Text, nullable=True)
    schema_json = Column(JSON, nullable=False)              # JSON Schema 定义属性
    exposed = Column(Boolean, default=False)                # 是否通过 MCP 暴露
    created_at = Column(DateTime, default=utcnow, nullable=False)

    objects = relationship("Object", back_populates="object_type")


class Object(Base):
    """对象实例"""
    __tablename__ = "object"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type_id = Column(Integer, ForeignKey("object_type.id"), nullable=False, index=True)
    properties_json = Column(JSON, nullable=False, default=dict)
    title = Column(String(500), nullable=True)              # 从 title_key 自动提取
    created_by = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    object_type = relationship("ObjectType", back_populates="objects")

    @property
    def properties(self) -> dict:
        """properties_json 的读别名"""
        return self.properties_json or {}


class LinkType(Base):
    """链接类型定义"""
    __tablename__ = "link_type"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    source_type_id = Column(Integer, ForeignKey("object_type.id"), nullable=False)
    target_type_id = Column(Integer, ForeignKey("object_type.id"), nullable=False)
    cardinality = Column(String(50), nullable=False, default="many")  # one | many


class Link(Base):
    """链接实例（关系）"""
    __tablename__ = "link"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type_id = Column(Integer, ForeignKey("link_type.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("object.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("object.id"), nullable=False, index=True)
    metadata_json = Column(JSON, nullable=True)


class ActionType(Base):
    """动作类型定义（写操作的一等公民，ADR-004/006）

    autonomy_level（ADR-006，读高写低）：
      L1 = 读操作/确定性转换，自动执行（跳过 staged）
      L2 = 写操作，staged 单人审（默认）
      L3 = 写操作，staged 双人审（v0.1 统一按 L2 逻辑处理，字段先行）
      L4 = 敏感写操作，需上级审（v0.1 同上）
      L5 = 不可逆操作，完全人审（v0.1 同上）

    transform_json（确定性转换规则，消除 Golden Hammer）：
      [{"set": "properties.priority", "from": "params.priority"}]
      由通用 ActionExecutor 解析执行，不硬编码动作名。
      纯确定性转换必须走 transform（不用 AI 步骤）——元流程反模式核验。
    """
    __tablename__ = "action_type"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)

    params_schema_json = Column(JSON, nullable=False, default=dict)       # 参数 JSON Schema
    submission_criteria_json = Column(JSON, nullable=True)                 # 运行时状态校验
    transform_json = Column(JSON, nullable=True)                           # 确定性转换规则
    side_effects_json = Column(JSON, nullable=True)                        # [{type: webhook|notify}]（v0.1 仅记录）

    autonomy_level = Column(Integer, default=2, nullable=False)            # L1-L5，默认 L2
    requires_staging = Column(Boolean, default=True, nullable=False)
    description_for_agent = Column(Text, nullable=True)                    # MCP 工具描述
    idempotency_key_template = Column(String(200), nullable=True)          # 如 "{object_id}-{name}"

    created_at = Column(DateTime, default=utcnow, nullable=False)

    @property
    def params_schema(self) -> dict:
        """params_schema_json 的读别名（Response DTO 用）"""
        return self.params_schema_json or {}


class ActionExec(Base):
    """动作执行记录（staged writes 状态机载体）

    状态流转：staged → approved → applied → (可 revert)
             staged → rejected（终态）
    """
    __tablename__ = "action_exec"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type_id = Column(Integer, ForeignKey("action_type.id"), nullable=False, index=True)

    idempotency_key = Column(String(200), nullable=True, unique=True, index=True)
    params_json = Column(JSON, nullable=False, default=dict)

    # staged | approved | applied | rejected | reverted
    status = Column(String(50), nullable=False, default="staged", index=True)

    staged_by = Column(String(100), nullable=True, index=True)
    staged_at = Column(DateTime, default=utcnow, nullable=False)

    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)

    applied_at = Column(DateTime, nullable=True)
    reverted_at = Column(DateTime, nullable=True)

    # 执行日志：{"before": {...原值快照}, "transform_log": [...], "errors": [...]}
    exec_log_json = Column(JSON, nullable=True)

    @property
    def params(self) -> dict:
        """params_json 的读别名（Response DTO 用）"""
        return self.params_json or {}

    @property
    def exec_log(self) -> dict:
        """exec_log_json 的读别名（Response DTO 用）"""
        return self.exec_log_json or {}
