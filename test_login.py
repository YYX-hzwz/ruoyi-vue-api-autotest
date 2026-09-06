import requests
import config

def test_login_success():
    url = f"{config.API_URL}/login"
    payload = {
        "username": config.ADMIN_USER,
        "password": config.ADMIN_PASS,
        "code": "1234",
        "uuid": "test-uuid"
    }
    resp = requests.post(url, json=payload)
    print(resp.text)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    assert "token" in data