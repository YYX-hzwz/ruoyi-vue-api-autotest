import pytest
from api_client import APIClient

@pytest.fixture(scope="module")
def client():
    c = APIClient()
    c.login()
    return c

def test_get_info(client):
    resp = client.get("/getInfo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "user" in data
    assert "roles" in data
    assert "permissions" in data

def test_get_routers(client):
    resp = client.get("/getRouters")
    assert resp.status_code == 200
    assert resp.json()["code"] == 200

def test_get_dict_data(client):
    # 常用字典类型 sys_normal_disable
    resp = client.get("/system/dict/data/type/sys_normal_disable")
    assert resp.status_code == 200
    assert resp.json()["code"] == 200

def test_get_config_list(client):
    resp = client.get("/system/config/list?pageNum=1&pageSize=5")
    assert resp.status_code == 200
    assert resp.json()["code"] == 200

def test_get_notice_list(client):
    resp = client.get("/system/notice/list?pageNum=1&pageSize=5")
    assert resp.status_code == 200
    assert resp.json()["code"] == 200