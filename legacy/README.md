# legacy：重构前的历史实现

本目录保存重构前的实现，仅作对照阅读，不参与测试执行（`pytest.ini` 的 `testpaths = tests` 已排除本目录）。

阅读当前实现请从 `framework/`、`ruoyi/`、`tests/` 三个目录开始。

对照方式：

```bash
git log --oneline
diff legacy/test_user_api.py tests/test_02_user_crud.py
```
