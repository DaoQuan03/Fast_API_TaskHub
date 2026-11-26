from fastapi.testclient import TestClient


def _create_user_and_headers(
    client: TestClient,
    email: str,
    full_name: str = "Workspace User",
) -> tuple[int, dict[str, str]]:
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": full_name,
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    token = login.json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def test_workspace_crud_and_owner_membership(client: TestClient):
    owner_id, owner_headers = _create_user_and_headers(client, "owner@example.com")
    _, outsider_headers = _create_user_and_headers(client, "outsider@example.com")

    res_create = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "  Backend Engineering  "},
    )
    assert res_create.status_code == 201
    ws = res_create.json()
    ws_id = ws["id"]
    assert ws["name"] == "Backend Engineering"
    assert ws["owner_id"] == owner_id

    res_list_owner = client.get("/api/v1/workspaces", headers=owner_headers)
    assert res_list_owner.status_code == 200
    assert res_list_owner.json()["total"] == 1

    res_list_outsider = client.get("/api/v1/workspaces", headers=outsider_headers)
    assert res_list_outsider.status_code == 200
    assert res_list_outsider.json()["total"] == 0

    res_get_outsider = client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers=outsider_headers,
    )
    assert res_get_outsider.status_code == 403

    res_patch = client.patch(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner_headers,
        json={"name": "Core Platform"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["name"] == "Core Platform"

    res_null_name = client.patch(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner_headers,
        json={"name": None},
    )
    assert res_null_name.status_code == 422


def test_workspace_members_management_and_rbac(client: TestClient):
    owner_id, owner_headers = _create_user_and_headers(client, "ws_owner@example.com")
    member_id, member_headers = _create_user_and_headers(client, "ws_member@example.com")

    ws_res = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Product Team"},
    )
    ws_id = ws_res.json()["id"]

    res_add_owner_role = client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "OWNER"},
    )
    assert res_add_owner_role.status_code == 422

    res_add = client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "VIEWER"},
    )
    assert res_add.status_code == 201
    assert res_add.json()["role"] == "VIEWER"

    res_dup = client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "EDITOR"},
    )
    assert res_dup.status_code == 409

    res_viewer_get = client.get(
        f"/api/v1/workspaces/{ws_id}",
        headers=member_headers,
    )
    assert res_viewer_get.status_code == 200

    res_viewer_patch_ws = client.patch(
        f"/api/v1/workspaces/{ws_id}",
        headers=member_headers,
        json={"name": "Viewer Hack"},
    )
    assert res_viewer_patch_ws.status_code == 403

    res_viewer_del_ws = client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers=member_headers,
    )
    assert res_viewer_del_ws.status_code == 403

    res_promote = client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}",
        headers=owner_headers,
        json={"role": "EDITOR"},
    )
    assert res_promote.status_code == 200
    assert res_promote.json()["role"] == "EDITOR"

    res_promote_to_owner = client.patch(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}",
        headers=owner_headers,
        json={"role": "OWNER"},
    )
    assert res_promote_to_owner.status_code == 422

    res_remove_owner = client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{owner_id}",
        headers=owner_headers,
    )
    assert res_remove_owner.status_code == 400

    res_remove_member = client.delete(
        f"/api/v1/workspaces/{ws_id}/members/{member_id}",
        headers=owner_headers,
    )
    assert res_remove_member.status_code == 204

    res_del_ws = client.delete(
        f"/api/v1/workspaces/{ws_id}",
        headers=owner_headers,
    )
    assert res_del_ws.status_code == 204
