"""v0.2.0 首启检测：GET /api/first-run——库空判定给前端引导层"""


async def test_first_run_true_on_empty_db(db_session):
    from yuanzhu.main import app
    from yuanzhu.db.database import get_db
    from httpx import AsyncClient, ASGITransport

    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/first-run")
    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json() == {"first_run": True}


async def test_first_run_false_when_objects_exist(db_session):
    from yuanzhu.main import app
    from yuanzhu.db.database import get_db
    from yuanzhu.ontology.object_store import ObjectStore
    from yuanzhu.models.object import ObjectTypeCreate, ObjectCreate
    from httpx import AsyncClient, ASGITransport

    at = await ObjectStore(db_session).create_type(ObjectTypeCreate(
        name="Task", domain="probe", title_key="title"))
    await ObjectStore(db_session).create_object(ObjectCreate(
        type_id=at.id, properties={"title": "已有数据"}))
    await db_session.flush()

    async def override():
        yield db_session
    app.dependency_overrides[get_db] = override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/first-run")
    app.dependency_overrides.clear()
    assert r.json() == {"first_run": False}
