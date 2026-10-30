"""已知缺陷的回归用例（xfail）。

这个文件是整个项目"诚实度"的证明：发现的缺陷没有被写成断言里的"预期行为"，
而是被固化成**会红**的用例，用 `xfail` 标记为"已知失败"。

- 缺陷未修复 → 用例失败，被记作 xfailed，报告里可见、不会被忽略；
- 缺陷修复后 → 用例通过，被记作 xpassed，控制台会提示"请移除 xfail 标记"；
- 有人把缺陷改回去（回归）→ 用例重新变红，立刻暴露。

`strict=False` 而不是 `strict=True` 的原因：strict=True 在缺陷修复后会直接
把 CI 判红，逼着你在修 bug 的同一个提交里改测试；而测试与修复往往不是同一个人、
不在同一个迭代。这里用 `strict=False` + 会话结束时主动提示"已修复，请移除标记"，
在"不误伤 CI"和"不遗忘清理"之间取平衡。
"""

from __future__ import annotations

import pytest

from framework.assertions import expect_biz_error, expect_perm_denied
from ruoyi.cleanup import delete_role_if_exists, delete_user_if_exists
from ruoyi.factories import role_payload, user_payload


@pytest.mark.defect("BUG-001")
@pytest.mark.xfail(strict=False, reason="BUG-001 未修复：后端未校验密码长度")
def test_weak_password_rejected(user_api) -> None:
    """密码 3 位时应被拒绝（当前实现会创建成功）。"""
    payload = user_payload(password="123")
    response = user_api.create(payload)
    try:
        expect_biz_error(response, msg_contains="密码长度")
    finally:
        if response.code == 200:
            delete_user_if_exists(user_api, payload["userName"])


@pytest.mark.defect("BUG-002")
@pytest.mark.permission
@pytest.mark.xfail(strict=False, reason="BUG-002 未修复：普通角色可读取用户列表")
def test_normal_user_cannot_list_users(normal_session) -> None:
    """未授予 system:user:list 的角色，读用户列表应得 403（当前可读到数据）。"""
    expect_perm_denied(normal_session.api.list())


@pytest.mark.defect("BUG-003")
@pytest.mark.xfail(strict=False, reason="BUG-003 未修复：角色状态未做枚举校验")
def test_invalid_role_status_rejected(role_api) -> None:
    """status=9 应被拒绝（当前会入库）。"""
    payload = role_payload(status="9")
    response = role_api.create(payload)
    try:
        expect_biz_error(response, msg_contains="状态")
    finally:
        if response.code == 200:
            delete_role_if_exists(role_api, payload["roleKey"])
