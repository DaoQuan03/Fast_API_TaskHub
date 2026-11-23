from fastapi.testclient import TestClient

from app.core.security import create_token, hash_password
from app.models.enums import TokenType, UserRole
from app.models.user import User
from tests.test_task import TestingSessionLocal, client, setup_test_db  # noqa: F401


def _register_and_login(
    client: TestClient,
    email: str = "user1@example.com",
    password: str = "Password123!",
    full_name: str = "User One",
) -> dict:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert reg.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return {"user": reg.json(), "tokens": login.json()}


def _create_admin() -> int:
    import asyncio

    async def _seed() -> int:
        async with TestingSessionLocal() as session:
            admin = User(
                email="admin@example.com",
                full_name="Admin User",
                hashed_password=hash_password("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            return admin.id

    return asyncio.run(_seed())


def test_register_duplicate_email_returns_409(client: TestClient):
    res1 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "full_name": "First User",
            "password": "Password123!",
        },
    )
    assert res1.status_code == 201
    assert res1.json()["role"] == "MEMBER"

    res2 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "full_name": "Second User",
            "password": "Password123!",
        },
    )
    assert res2.status_code == 409


def test_refresh_token_cannot_call_protected_api_401(client: TestClient):
    ctx = _register_and_login(client)
    refresh_token = ctx["tokens"]["refresh_token"]

    res = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert res.status_code == 401
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_invalid_sub_claim_returns_401_not_500(client: TestClient):
    bad_token, _, _ = create_token("not-an-integer", TokenType.ACCESS)
    res = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {bad_token}"},
    )
    assert res.status_code == 401


def test_refresh_token_rotation_and_reuse_detection_401(client: TestClient):
    ctx = _register_and_login(client)
    old_refresh = ctx["tokens"]["refresh_token"]

    res1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res1.status_code == 200
    new_refresh = res1.json()["refresh_token"]
    assert new_refresh != old_refresh

    res_reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res_reuse.status_code == 401

    res_new_after_compromise = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert res_new_after_compromise.status_code == 401


def test_change_password_revokes_refresh_and_old_password_fails_401(client: TestClient):
    ctx = _register_and_login(client, email="cp@example.com", password="OldPassword123!")
    access_token = ctx["tokens"]["access_token"]
    refresh_token = ctx["tokens"]["refresh_token"]

    res_cp = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )
    assert res_cp.status_code == 204

    res_old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "cp@example.com", "password": "OldPassword123!"},
    )
    assert res_old_login.status_code == 401

    res_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert res_refresh.status_code == 401

    res_new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "cp@example.com", "password": "NewPassword456!"},
    )
    assert res_new_login.status_code == 200


def test_member_cannot_modify_or_delete_other_user_or_task_403(client: TestClient):
    user_a = _register_and_login(client, email="a@example.com")
    user_b = _register_and_login(client, email="b@example.com")

    token_a = user_a["tokens"]["access_token"]
    token_b = user_b["tokens"]["access_token"]
    id_a = user_a["user"]["id"]

    res_patch_user = client.patch(
        f"/api/v1/users/{id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"full_name": "Hacked Name"},
    )
    assert res_patch_user.status_code == 403

    res_del_user = client.delete(
        f"/api/v1/users/{id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_del_user.status_code == 403

    task_res = client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "User A Private Task"},
    )
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    res_patch_task = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "User B hijack"},
    )
    assert res_patch_task.status_code == 403

    res_del_task = client.delete(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_del_task.status_code == 403


def test_admin_protections_and_password_72_bytes_limit(client: TestClient):
    admin_id = _create_admin()
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    admin_token = login_admin.json()["access_token"]

    res_self_del = client.delete(
        f"/api/v1/users/{admin_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_self_del.status_code == 400

    res_demote_last_admin = client.patch(
        f"/api/v1/users/{admin_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "MEMBER"},
    )
    assert res_demote_last_admin.status_code == 400

    multibyte_password = "ắ" * 40
    res_72_bytes = client.post(
        "/api/v1/auth/register",
        json={
            "email": "utf8@example.com",
            "full_name": "UTF8 User",
            "password": multibyte_password,
        },
    )
    assert res_72_bytes.status_code == 422
