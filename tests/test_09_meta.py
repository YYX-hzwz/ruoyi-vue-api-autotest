"""测试套件自检（meta test）。

测试代码也是代码。这个文件用来守护重构后定下的约束，
防止几个月后又退回到"硬编码 + 直接 requests + 裸 sleep"的老路。

这些检查跑得很快，但能挡住 90% 的规范回退。
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
REGISTRY = ROOT / "defects" / "registry.json"
SELF = Path(__file__).name

REQUIRED_DEFECT_FIELDS = [
    "id",
    "title",
    "severity",
    "module",
    "status",
    "expected",
    "actual",
    "root_cause",
    "impact",
    "fix",
    "reproduction",
    "test",
]

FORBIDDEN_PATTERNS = [
    (r"admin123", "禁止在用例里硬编码口令，应从 settings 读取"),
    (r"localhost:8080", "禁止硬编码环境地址，应从 settings 读取"),
    (r"roleIds\s*=\s*\[2\]", "禁止硬编码角色 id，应按 roleKey 解析"),
    (r"time\.sleep\(", "禁止裸 sleep，用 framework.assertions.eventually 轮询"),
    (r"\brequests\.(get|post|put|delete)\(", "禁止在用例里直接发请求，必须经过 apis 层"),
    (r"assert\s+\w+\.status_code\s*==\s*200", "只断言 HTTP 200 不携带业务信息，用 expect_ok"),
]


def _registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["defects"]


def _defect_markers(request: pytest.FixtureRequest) -> dict[str, list[str]]:
    marked: dict[str, list[str]] = {}
    for item in request.session.items:
        marker = item.get_closest_marker("defect")
        if marker and marker.args:
            marked.setdefault(str(marker.args[0]), []).append(item.nodeid)
    return marked


def test_registry_schema_is_complete() -> None:
    defects = _registry()
    assert defects, "缺陷登记表不应为空"
    for defect in defects:
        missing = [field for field in REQUIRED_DEFECT_FIELDS if not defect.get(field)]
        assert not missing, f"{defect.get('id')} 缺少字段: {missing}"
        assert defect["severity"] in {"高", "中", "低"}, f"{defect['id']} 严重程度取值不规范"
        assert defect["status"] in {"open", "fixed", "closed"}, f"{defect['id']} 状态取值不规范"


def test_every_defect_is_bound_to_a_test(request: pytest.FixtureRequest) -> None:
    """登记的缺陷必须有对应用例，否则"记录"就只是文档，不会回归。"""
    marked = _defect_markers(request)
    registered = {defect["id"] for defect in _registry()}

    unbound = registered - set(marked)
    assert not unbound, f"以下缺陷没有任何 @pytest.mark.defect 用例: {sorted(unbound)}"

    orphan = set(marked) - registered
    assert not orphan, f"以下用例标记了不存在的缺陷 id: {sorted(orphan)}"


def test_defect_tests_reference_registry_path() -> None:
    """登记表里的 test 字段必须指向真实存在的用例文件。"""
    for defect in _registry():
        nodeid = defect["test"]
        path = ROOT / nodeid.split("::")[0]
        assert path.is_file(), f"{defect['id']} 指向的用例文件不存在: {path}"
        source = path.read_text(encoding="utf-8")
        function = nodeid.split("::")[-1]
        assert f"def {function}(" in source, f"{defect['id']} 指向的用例不存在: {nodeid}"


@pytest.mark.parametrize(
    "path",
    sorted(TESTS_DIR.glob("test_*.py")),
    ids=lambda path: path.name,
)
def test_no_forbidden_patterns(path: Path) -> None:
    if path.name == SELF:
        pytest.skip("自检文件本身包含禁用模式的定义")
    source = path.read_text(encoding="utf-8")
    hits = []
    for pattern, reason in FORBIDDEN_PATTERNS:
        if re.search(pattern, source):
            hits.append(f"{pattern} → {reason}")
    assert not hits, f"{path.name} 命中禁用模式:\n  - " + "\n  - ".join(hits)


@pytest.mark.parametrize(
    "path",
    sorted(TESTS_DIR.glob("test_*.py")),
    ids=lambda path: path.name,
)
def test_module_has_docstring(path: Path) -> None:
    """模块级 docstring 是这个文件"为什么存在"的唯一说明。

    没有它，半年后没人敢删、也没人敢改。
    """
    module = ast.parse(path.read_text(encoding="utf-8"))
    docstring = ast.get_docstring(module)
    assert docstring and len(docstring.strip()) > 20, f"{path.name} 缺少有意义的模块说明"


def test_no_duplicate_test_names() -> None:
    seen: dict[str, Path] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                key = f"{path.name}::{node.name}"
                assert key not in seen, f"重复用例名: {key}"
                seen[key] = path
    assert len(seen) >= 30, f"用例数量异常偏少（{len(seen)}），检查是否被误删"
