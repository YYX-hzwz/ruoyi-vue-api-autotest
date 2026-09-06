# RuoYi-Vue API 自动化测试

针对开源后台管理系统 RuoYi-Vue 的 API 层自动化测试，覆盖登录、用户管理、角色管理、公共接口 4 个模块，共 **43 条测试用例**。

## 环境要求
- Python 3.10+
- RuoYi-Vue 后端运行在 `http://localhost:8080`
- MySQL 5.7+（RuoYi 数据库已初始化）

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 启动 RuoYi-Vue 后端（确保接口可访问）
3. 运行测试：`pytest`
4. 查看报告：打开生成的 `report.html`

## 测试覆盖
| 模块 | 用例数 | 场景 |
|------|--------|------|
| 登录 | 5 | 成功/失败/空参数/错误密码 |
| 用户管理 | 19 | CRUD、搜索、分页、越权、禁用登录、参数校验 |
| 角色管理 | 18 | CRUD、菜单分配、状态管理、越权 |
| 公共接口 | 5 | getInfo/getRouters/字典/配置/公告 |

## 缺陷记录
共发现 4 个缺陷，详见 [docs/defects.md](docs/defects.md)，含 1 个高危越权漏洞。

## 项目结构
autotest/
├── config.py
├── api_client.py
├── requirements.txt
├── pytest.ini
├── README.md
├── data/
│   └── users.json
├── test_login.py
├── test_user_api.py
├── test_user_api_extended.py
├── test_role_api.py
├── test_common_api.py
└── docs/
    ├── defects.md
    └── test_plan.md

## 踩坑记录
- 验证码开关在配置文件中不生效，实际由数据库 `sys_config` 表控制，最终通过修改代码临时禁用。
- 用户名/手机号/邮箱存在唯一性约束，测试数据使用 `uuid` 动态生成。
- 普通角色用户可访问用户列表接口（疑似缺少权限注解），已记为高危缺陷。