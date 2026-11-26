from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


def test_task_endpoints_require_authentication_401(client: TestClient):
    assert client.post("/api/v1/tasks", json={"title": "Anon Task"}).status_code == 401
    assert client.get("/api/v1/tasks").status_code == 401
    assert client.get("/api/v1/tasks/1").status_code == 401
    assert client.patch("/api/v1/tasks/1", json={"title": "Anon"}).status_code == 401
    assert client.delete("/api/v1/tasks/1").status_code == 401


def test_create_task_success(client: TestClient, auth_headers: dict[str, str]):
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    response = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
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
    assert data["created_by"] == 1
    assert "created_at" in data


def test_create_task_validation_422(client: TestClient, auth_headers: dict[str, str]):
    res_whitespace = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "     "},
    )
    assert res_whitespace.status_code == 422

    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    res_past = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Valid title", "due_date": past_date},
    )
    assert res_past.status_code == 422


def test_list_tasks_pagination_and_sorting(
    client: TestClient,
    auth_headers: dict[str, str],
):
    client.post("/api/v1/tasks", headers=auth_headers, json={"title": "Task 1"})
    client.post("/api/v1/tasks", headers=auth_headers, json={"title": "Task 2"})
    client.post("/api/v1/tasks", headers=auth_headers, json={"title": "Task 3"})

    response = client.get("/api/v1/tasks?page=1&limit=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert [item["id"] for item in data["items"]] == [1, 2]


def test_get_task_success_and_404(client: TestClient, auth_headers: dict[str, str]):
    create_res = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Task A"},
    )
    task_id = create_res.json()["id"]

    res = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["title"] == "Task A"

    res_404 = client.get("/api/v1/tasks/999", headers=auth_headers)
    assert res_404.status_code == 404
    assert res_404.json()["detail"] == "Task with ID 999 not found"


def test_update_task_success_404_and_422(
    client: TestClient,
    auth_headers: dict[str, str],
):
    create_res = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Old Title"},
    )
    task_id = create_res.json()["id"]

    res_ok = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=auth_headers,
        json={"title": "  New Title  ", "status": "IN_PROGRESS"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["title"] == "New Title"
    assert res_ok.json()["status"] == "IN_PROGRESS"

    for field in ("title", "status", "priority"):
        res_null = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=auth_headers,
            json={field: None},
        )
        assert res_null.status_code == 422

    res_404 = client.patch(
        "/api/v1/tasks/999",
        headers=auth_headers,
        json={"title": "Valid"},
    )
    assert res_404.status_code == 404


def test_delete_task_success_and_404(client: TestClient, auth_headers: dict[str, str]):
    create_res = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "To Delete"},
    )
    task_id = create_res.json()["id"]

    res_del = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert res_del.status_code == 204

    res_404 = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert res_404.status_code == 404
