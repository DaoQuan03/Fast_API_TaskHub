from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, enable_sqlite_foreign_keys
from app.main import app
import app.models  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
enable_sqlite_foreign_keys(test_engine)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_test_db():
    import asyncio

    async def _reset():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_create_task_success(client: TestClient):
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "  Viết unit test cho Task  ",
            "priority": "HIGH",
            "due_date": future_date,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Viết unit test cho Task"
    assert data["status"] == "TODO"
    assert data["priority"] == "HIGH"
    assert data["created_by"] is None
    assert "created_at" in data


def test_create_task_validation_422(client: TestClient):
    res_whitespace = client.post("/api/v1/tasks", json={"title": "     "})
    assert res_whitespace.status_code == 422

    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    res_past = client.post(
        "/api/v1/tasks",
        json={"title": "Valid title", "due_date": past_date},
    )
    assert res_past.status_code == 422


def test_list_tasks_pagination_and_sorting(client: TestClient):
    client.post("/api/v1/tasks", json={"title": "Task 1"})
    client.post("/api/v1/tasks", json={"title": "Task 2"})
    client.post("/api/v1/tasks", json={"title": "Task 3"})

    response = client.get("/api/v1/tasks?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert [item["id"] for item in data["items"]] == [1, 2]


def test_get_task_success_and_404(client: TestClient):
    create_res = client.post("/api/v1/tasks", json={"title": "Task A"})
    task_id = create_res.json()["id"]

    res = client.get(f"/api/v1/tasks/{task_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Task A"

    res_404 = client.get("/api/v1/tasks/999")
    assert res_404.status_code == 404
    assert res_404.json()["detail"] == "Task with ID 999 not found"


def test_update_task_success_404_and_422(client: TestClient):
    create_res = client.post("/api/v1/tasks", json={"title": "Old Title"})
    task_id = create_res.json()["id"]

    res_ok = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "  New Title  ", "status": "IN_PROGRESS"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["title"] == "New Title"
    assert res_ok.json()["status"] == "IN_PROGRESS"

    for field in ("title", "status", "priority"):
        res_null = client.patch(f"/api/v1/tasks/{task_id}", json={field: None})
        assert res_null.status_code == 422

    res_404 = client.patch("/api/v1/tasks/999", json={"title": "Valid"})
    assert res_404.status_code == 404


def test_delete_task_success_and_404(client: TestClient):
    create_res = client.post("/api/v1/tasks", json={"title": "To Delete"})
    task_id = create_res.json()["id"]

    res_del = client.delete(f"/api/v1/tasks/{task_id}")
    assert res_del.status_code == 204

    res_404 = client.delete(f"/api/v1/tasks/{task_id}")
    assert res_404.status_code == 404
