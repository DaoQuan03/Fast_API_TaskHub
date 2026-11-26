from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


def _register_and_headers(
    client: TestClient,
    email: str,
) -> tuple[int, dict[str, str]]:
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Test User",
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201
    uid = reg.json()["id"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return uid, {"Authorization": f"Bearer {login.json()['access_token']}"}


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


def test_list_tasks_filtering_pagination_and_sorting(
    client: TestClient,
    auth_headers: dict[str, str],
):
    r1 = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Task 1", "priority": "LOW"},
    )
    t1_id = r1.json()["id"]
    client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Task 2", "priority": "HIGH"},
    )
    client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Task 3", "priority": "URGENT"},
    )
    client.patch(
        f"/api/v1/tasks/{t1_id}",
        headers=auth_headers,
        json={"status": "IN_PROGRESS"},
    )

    response = client.get("/api/v1/tasks?page=1&limit=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert [item["id"] for item in data["items"]] == [1, 2]

    filtered = client.get(
        "/api/v1/tasks?priority=HIGH&priority=URGENT",
        headers=auth_headers,
    )
    assert filtered.status_code == 200
    f_data = filtered.json()
    assert f_data["total"] == 2
    assert len(f_data["items"]) == 2

    status_filtered = client.get(
        "/api/v1/tasks?status=IN_PROGRESS",
        headers=auth_headers,
    )
    assert status_filtered.status_code == 200
    assert status_filtered.json()["total"] == 1


def test_get_update_delete_task_success_404_and_422(
    client: TestClient,
    auth_headers: dict[str, str],
):
    create_res = client.post(
        "/api/v1/tasks",
        headers=auth_headers,
        json={"title": "Old Title"},
    )
    task_id = create_res.json()["id"]

    res_get = client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert res_get.status_code == 200

    res_404 = client.get("/api/v1/tasks/999", headers=auth_headers)
    assert res_404.status_code == 404

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

    res_patch_404 = client.patch(
        "/api/v1/tasks/999",
        headers=auth_headers,
        json={"title": "Valid"},
    )
    assert res_patch_404.status_code == 404

    res_del = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert res_del.status_code == 204

    res_del_404 = client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert res_del_404.status_code == 404


def test_task_management_rbac_archive_labels_comments(client: TestClient):
    owner_id, owner_headers = _register_and_headers(client, "tm_owner@example.com")
    editor_id, editor_headers = _register_and_headers(client, "tm_editor@example.com")
    viewer_id, viewer_headers = _register_and_headers(client, "tm_viewer@example.com")
    outsider_id, outsider_headers = _register_and_headers(
        client,
        "tm_outsider@example.com",
    )

    ws = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "TaskHub WS"},
    ).json()
    ws_id = ws["id"]

    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
        json={"user_id": editor_id, "role": "EDITOR"},
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
        json={"user_id": viewer_id, "role": "VIEWER"},
    )

    proj = client.post(
        f"/api/v1/workspaces/{ws_id}/projects",
        headers=editor_headers,
        json={"name": "Main Project"},
    ).json()
    proj_id = proj["id"]

    res_viewer_create = client.post(
        "/api/v1/tasks",
        headers=viewer_headers,
        json={"title": "Viewer Task", "project_id": proj_id},
    )
    assert res_viewer_create.status_code == 403

    res_bad_assignee = client.post(
        "/api/v1/tasks",
        headers=editor_headers,
        json={
            "title": "Bad Assignee Task",
            "project_id": proj_id,
            "assignee_id": outsider_id,
        },
    )
    assert res_bad_assignee.status_code == 422

    task = client.post(
        "/api/v1/tasks",
        headers=editor_headers,
        json={
            "title": "Valid Project Task",
            "project_id": proj_id,
            "assignee_id": viewer_id,
        },
    ).json()
    task_id = task["id"]

    assert (
        client.get(f"/api/v1/tasks/{task_id}", headers=viewer_headers).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/tasks/{task_id}", headers=outsider_headers).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=viewer_headers,
            json={"title": "Viewer Edit"},
        ).status_code
        == 403
    )

    label = client.post(
        f"/api/v1/projects/{proj_id}/labels",
        headers=editor_headers,
        json={"name": "Bug", "color": "#EF4444"},
    ).json()
    label_id = label["id"]

    res_attach = client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=editor_headers,
    )
    assert res_attach.status_code == 200
    assert len(res_attach.json()["labels"]) == 1

    res_attach_dup = client.post(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=editor_headers,
    )
    assert res_attach_dup.status_code == 409

    res_detach = client.delete(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=editor_headers,
    )
    assert res_detach.status_code == 204

    res_detach_404 = client.delete(
        f"/api/v1/tasks/{task_id}/labels/{label_id}",
        headers=editor_headers,
    )
    assert res_detach_404.status_code == 404

    comment_owner = client.post(
        f"/api/v1/tasks/{task_id}/comments",
        headers=owner_headers,
        json={"content": "Owner comment"},
    ).json()
    comment_id = comment_owner["id"]

    res_editor_del_other_comment = client.delete(
        f"/api/v1/comments/{comment_id}",
        headers=editor_headers,
    )
    assert res_editor_del_other_comment.status_code == 403

    res_archive = client.post(
        f"/api/v1/projects/{proj_id}/archive",
        headers=owner_headers,
    )
    assert res_archive.status_code == 200

    res_viewer_on_archived = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=viewer_headers,
        json={"title": "Viewer on archived"},
    )
    assert res_viewer_on_archived.status_code == 403

    res_editor_on_archived = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=editor_headers,
        json={"title": "Editor on archived"},
    )
    assert res_editor_on_archived.status_code == 409

    res_create_on_archived = client.post(
        "/api/v1/tasks",
        headers=editor_headers,
        json={"title": "New task on archived", "project_id": proj_id},
    )
    assert res_create_on_archived.status_code == 409

    res_unarchive = client.post(
        f"/api/v1/projects/{proj_id}/unarchive",
        headers=owner_headers,
    )
    assert res_unarchive.status_code == 200
    assert (
        client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=editor_headers,
            json={"title": "Updated after unarchive"},
        ).status_code
        == 200
    )
