import requests
import config

class APIClient:
    def __init__(self, username=None, password=None):
        self.base_url = config.API_URL
        self.username = username or config.ADMIN_USER
        self.password = password or config.ADMIN_PASS
        self.token = None
        self.headers = {}

    def login(self):
        url = f"{self.base_url}/login"
        payload = {"username": self.username, "password": self.password}
        resp = requests.post(url, json=payload)
        data = resp.json()
        assert data["code"] == 200, f"登录失败: {data}"
        self.token = data["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        return self.token

    def get(self, path, **kwargs):
        return requests.get(f"{self.base_url}{path}", headers=self.headers, **kwargs)

    def post(self, path, **kwargs):
        return requests.post(f"{self.base_url}{path}", headers=self.headers, **kwargs)

    def put(self, path, **kwargs):
        return requests.put(f"{self.base_url}{path}", headers=self.headers, **kwargs)

    def delete(self, path, **kwargs):
        return requests.delete(f"{self.base_url}{path}", headers=self.headers, **kwargs)