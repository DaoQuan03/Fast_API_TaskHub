import asyncio
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.core.messages import INACTIVE_USER, INVALID_CREDENTIALS
from app.core.security import create_access_token, create_token, hash_password
from app.models.enums import TokenType, UserRole
from app.models.user import User
from tests.conftest import TestingSessionLocal


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


def _seed_user(
    *,
    email: str = "admin@example.com",
    password: str = "AdminPass123!",
    role: UserRole = UserRole.ADMIN,
    is_active: bool = True,
) -> int:
    async def _seed() -> int:
        async with TestingSessionLocal() as session:
            user = User(
                email=email,
                full_name="Seeded User",
                hashed_password=hash_password(password),
                role=role,
                is_active=is_active,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user.id

    return asyncio.run(_seed())


def test_register_email_validation_normalization_and_duplicate_409(client: TestClient):
    res_invalid_email = client.post(
        "/api/v1/auth/register",
        json={
            "email": "notanemail",
            "full_name": "Invalid Email",
            "password": "Password123!",
        },
    )
    assert res_invalid_email.status_code == 422

    res1 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "  Case@Example.com ",
            "full_name": "First User",
            "password": "Password123!",
        },
    )
    assert res1.status_code == 201
    assert res1.json()["email"] == "case@example.com"
    assert res1.json()["role"] == "MEMBER"

    res2 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "case@example.com",
            "full_name": "Second User",
            "password": "Password123!",
        },
    )
    assert res2.status_code == 409


def test_login_nonexistent_email_and_wrong_password_and_inactive_user(
    client: TestClient,
):
    _register_and_login(client, email="active@example.com", password="Password123!")

    res_no_email = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "Password123!"},
    )
    res_wrong_pass = client.post(
        "/api/v1/auth/login",
        json={"email": "active@example.com", "password": "WrongPassword123!"},
    )
    assert res_no_email.status_code == 401
    assert res_wrong_pass.status_code == 401
    assert res_no_email.json()["detail"] == INVALID_CREDENTIALS
    assert res_wrong_pass.json()["detail"] == INVALID_CREDENTIALS

    _seed_user(
        email="locked@example.com",
        password="Password123!",
        role=UserRole.MEMBER,
        is_active=False,
    )
    res_inactive = client.post(
        "/api/v1/auth/login",
        json={"email": "locked@example.com", "password": "Password123!"},
    )
    assert res_inactive.status_code == 401
    assert res_inactive.json()["detail"] == INACTIVE_USER


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


def test_refresh_token_rotation_reuse_detection_and_logout(client: TestClient):
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

    ctx2 = _register_and_login(client, email="logout@example.com")
    refresh2 = ctx2["tokens"]["refresh_token"]
    res_logout = client.post("/api/v1/auth/logout", json={"refresh_token": refresh2})
    assert res_logout.status_code == 204
    res_after_logout = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh2},
    )
    assert res_after_logout.status_code == 401


def test_change_password_invalidates_old_access_token_and_refresh_token(
    client: TestClient,
):
    ctx = _register_and_login(client, email="cp@example.com", password="OldPassword123!")
    user_id = ctx["user"]["id"]
    old_issued_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    old_access_token = create_access_token(user_id, issued_at=old_issued_at)
    refresh_token = ctx["tokens"]["refresh_token"]

    res_cp = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old_access_token}"},
        json={
            "current_password": "OldPassword123!",
            "new_password": "NewPassword456!",
        },
    )
    assert res_cp.status_code == 204

    res_me_old_access = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert res_me_old_access.status_code == 401

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


def test_update_me_and_member_cannot_modify_or_delete_other_user_or_task_403(
    client: TestClient,
):
    user_a = _register_and_login(client, email="a@example.com")
    user_b = _register_and_login(client, email="b@example.com")

    token_a = user_a["tokens"]["access_token"]
    token_b = user_b["tokens"]["access_token"]
    id_a = user_a["user"]["id"]

    res_me = client.patch(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"full_name": "  Updated User A  "},
    )
    assert res_me.status_code == 200
    assert res_me.json()["full_name"] == "Updated User A"

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
    admin1_id = _seed_user(email="admin1@example.com")
    _seed_user(email="admin2@example.com")

    login_admin1 = client.post(
        "/api/v1/auth/login",
        json={"email": "admin1@example.com", "password": "AdminPass123!"},
    )
    admin1_token = login_admin1.json()["access_token"]

    res_self_del = client.delete(
        f"/api/v1/users/{admin1_id}",
        headers={"Authorization": f"Bearer {admin1_token}"},
    )
    assert res_self_del.status_code == 400

    res_self_demote = client.patch(
        f"/api/v1/users/{admin1_id}",
        headers={"Authorization": f"Bearer {admin1_token}"},
        json={"role": "MEMBER"},
    )
    assert res_self_demote.status_code == 400

    res_self_lock = client.patch(
        f"/api/v1/users/{admin1_id}",
        headers={"Authorization": f"Bearer {admin1_token}"},
        json={"is_active": False},
    )
    assert res_self_lock.status_code == 400

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
