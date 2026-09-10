"""模板注册：解析 -> 本体层注册（①②）-> Template 登记（③④）"""
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from yuanzhu.db.models import Template
from yuanzhu.template.parser import parse_template_dir
from yuanzhu.ontology.object_store import ObjectStore
from yuanzhu.ontology.link_store import LinkStore
from yuanzhu.ontology.action_store import ActionStore
from yuanzhu.models.object import ObjectTypeCreate
from yuanzhu.models.action import ActionTypeCreate
from yuanzhu.models.link import LinkTypeCreate


class TemplateStore:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.objects = ObjectStore(session)
        self.links = LinkStore(session)
        self.actions = ActionStore(session)

    async def register_dir(self, template_dir: Path, status: str = "published") -> Template:
        """注册模板目录（幂等：同名同版本 upsert）"""
        parsed = parse_template_dir(template_dir)
        manifest = parsed["manifest"]
        domain = manifest["domain"]

        for ot in parsed["object_types"]:
            await self.objects.create_type(ObjectTypeCreate(
                name=ot["name"], domain=ot["domain"],
                title_key=ot["title_key"], description=ot["description"],
                exposed=ot["exposed"],
                properties=_schema_to_dsl(ot["schema_json"]),
            ))

        for lt in parsed["link_types"]:
            await self.links.register_type_by_name(
                domain=domain, name=lt["name"],
                source_type=lt["source_type"], target_type=lt["target_type"],
                cardinality=lt["cardinality"],
            )

        for act in parsed["actions"]:
            await self.actions.register_from_dsl(act)

        tpl = await self.get_by_name_version(manifest["name"], manifest["version"])
        if not tpl:
            tpl = Template(name=manifest["name"], version=manifest["version"], domain=domain)
            self.session.add(tpl)

        tpl.domain = domain
        tpl.manifest_json = manifest
        tpl.workflows_json = parsed["workflows"]
        tpl.evals_json = parsed["evals"]
        tpl.status = status
        await self.session.flush()
        await self.session.refresh(tpl)
        return tpl

    async def get_by_name_version(self, name: str, version: str) -> Optional[Template]:
        result = await self.session.execute(
            select(Template).where(Template.name == name, Template.version == version)
        )
        return result.scalar_one_or_none()

    async def list(self, domain: Optional[str] = None, status: Optional[str] = None):
        query = select(Template)
        if domain:
            query = query.where(Template.domain == domain)
        if status:
            query = query.where(Template.status == status)
        result = await self.session.execute(query.order_by(Template.created_at.desc()))
        return list(result.scalars().all())


def _schema_to_dsl(schema_json: dict) -> dict:
    """JSON Schema -> properties 简写 DSL（_build_schema 的逆形态，供 upsert）"""
    props = {}
    for prop_name, prop_json in (schema_json.get("properties") or {}).items():
        d = {"type": prop_json.get("type", "string")}
        for key in ("enum", "default", "minimum", "maximum", "description"):
            if key in prop_json:
                d[key] = prop_json[key]
        d["required"] = prop_name in (schema_json.get("required") or [])
        props[prop_name] = d
    return props
