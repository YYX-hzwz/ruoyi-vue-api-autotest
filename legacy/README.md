# legacy：重构前的原始版本

保留原因：**留证据**。

这个目录里的代码是重构前的状态（43 条用例），它有三个典型问题：

1. `test_user_extended.py:90` 把缺陷写成了通过（`assert code == 200  # 后端未校验密码长度，先让测试通过`）
2. 三份报告声称 43/43 全绿，同时文档声称发现高危越权——自相矛盾
3. fixture 在 4 个文件里重复 6 份，`conftest.py` 是 0 字节

对照阅读方式：

```bash
git log --oneline            # 看重构是怎么分步提交的
diff legacy/test_user_api.py tests/test_02_user_crud.py
```

**不要**在这个目录里改代码，也不要让 pytest 收集它（`pytest.ini` 的 `testpaths = tests` 已经排除）。

新代码请从 `framework/`、`ruoyi/`、`tests/` 三个目录开始读。

重构后的评审记录见 `docs/review-2026.md`（"重构前"视角），
修复结果见 `README.md`。
