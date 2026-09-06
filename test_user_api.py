import pytest
import requests
import json
import uuid
from api_client import APIClient

@pytest.fixture(scope="module")
def client():
    c = APIClient()
    c.login()
    return c

@pytest.fixture
def create_user(client):
    """创建测试用户，返回 user_data 和 user_id，测试结束后清理"""
    with open("data/users.json", encoding="utf-8") as f:
        user_data = json.load(f)["valid_user"]
    # 保证唯一性
    suffix = uuid.uuid4().hex[:8]
    user_data["userName"] = f"test_{suffix}"
    user_data["phonenumber"] = f"139{suffix}"
    user_data["email"] = f"test_{suffix}@example.com"

    # 创建用户
    resp = client.post("/system/user", json=user_data)
    assert resp.json()["code"] == 200, f"创建用户失败: {resp.text}"

    # 查询用户ID
    search_resp = client.get(f"/system/user/list?pageNum=1&pageSize=10&userName={user_data['userName']}")
    rows = search_resp.json().get("rows", [])
    user_id = None
    for row in rows:
        if row["userName"] == user_data["userName"]:
            user_id = row["userId"]
            break
    assert user_id is not None, "未找到新创建的用户"

    yield user_data, user_id

    # 清理：删除用户（可选）
    client.delete(f"/system/user/{user_id}")

def test_get_user_list(client):
    resp = client.get("/system/user/list?pageNum=1&pageSize=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "rows" in data

def test_create_user(create_user):
    user_data, user_id = create_user
    assert user_id is not None

def test_search_user(client, create_user):
    user_data, user_id = create_user
    resp = client.get(f"/system/user/list?pageNum=1&pageSize=10&userName={user_data['userName']}")
    assert resp.json()["code"] == 200
    rows = resp.json().get("rows", [])
    assert any(row["userName"] == user_data["userName"] for row in rows)

def test_update_user(client, create_user):
    user_data, user_id = create_user
    updated_data = dict(user_data)
    updated_data["userId"] = user_id
    updated_data["nickName"] = "修改后的昵称"
    resp = client.put("/system/user", json=updated_data)
    assert resp.json()["code"] == 200, f"更新失败: {resp.text}"

def test_delete_user(client):
    # 单独测试删除
    with open("data/users.json", encoding="utf-8") as f:
        user_data = json.load(f)["valid_user"]
    suffix = uuid.uuid4().hex[:8]
    user_data["userName"] = f"del_{suffix}"
    user_data["phonenumber"] = f"138{suffix}"
    user_data["email"] = f"del_{suffix}@example.com"

    resp = client.post("/system/user", json=user_data)
    assert resp.json()["code"] == 200

    search_resp = client.get(f"/system/user/list?pageNum=1&pageSize=10&userName={user_data['userName']}")
    rows = search_resp.json().get("rows", [])
    user_id = None
    for row in rows:
        if row["userName"] == user_data["userName"]:
            user_id = row["userId"]
            break
    assert user_id is not None

    del_resp = client.delete(f"/system/user/{user_id}")
    assert del_resp.json()["code"] == 200