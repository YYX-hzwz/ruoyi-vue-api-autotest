"""极简响应结构校验（替代 jsonschema/pydantic，零依赖）。

为什么不直接用 `assert "rows" in resp.json`：
- 字段**改名**时，`KeyError` 只会告诉你"没有 rows"，不会告诉你"接口契约变了"；
- 字段**类型**变了（`total` 从 int 变字符串），断言毫无感知；
- 嵌套结构缺字段，只能靠人肉逐层点开。

这里实现一个够用的声明式 DSL：

    from framework.schema import S, validate
    schema = {
        "code": S.int(enum=[200]),
        "total": S.int(ge=0),
        "rows": S.list_of({
            "userId": S.int(ge=1),
            "userName": S.str(min_len=1, max_len=30),
            "status": S.str(enum=["0", "1"]),
        }),
    }
    errors = validate(payload, schema)

设计取舍：**默认允许多余字段**。后端加字段不应该让测试红——那属于契约兼容的
演进；只有删除字段、改类型、改枚举才应该红。这是"面向契约"而不是"面向实现"
写断言的关键。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping, Sequence

_MISSING = object()


class Field:
    """一个字段的期望描述。"""

    __slots__ = (
        "kind",
        "required",
        "nullable",
        "enum",
        "pattern",
        "min_len",
        "max_len",
        "ge",
        "le",
        "item",
        "fields",
        "checker",
        "label",
    )

    def __init__(
        self,
        kind: str,
        *,
        required: bool = True,
        nullable: bool = False,
        enum: Sequence[Any] | None = None,
        pattern: str | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
        ge: float | None = None,
        le: float | None = None,
        item: "Field | None" = None,
        fields: Mapping[str, "Field"] | None = None,
        checker: Callable[[Any], bool] | None = None,
        label: str = "",
    ) -> None:
        self.kind = kind
        self.required = required
        self.nullable = nullable
        self.enum = list(enum) if enum is not None else None
        self.pattern = pattern
        self.min_len = min_len
        self.max_len = max_len
        self.ge = ge
        self.le = le
        self.item = item
        self.fields = dict(fields) if fields is not None else None
        self.checker = checker
        self.label = label


class S:
    """Schema 构造器，读起来接近类型声明。"""

    @staticmethod
    def int(**kw: Any) -> Field:
        return Field("int", **kw)

    @staticmethod
    def num(**kw: Any) -> Field:
        return Field("num", **kw)

    @staticmethod
    def str(**kw: Any) -> Field:
        return Field("str", **kw)

    @staticmethod
    def bool(**kw: Any) -> Field:
        return Field("bool", **kw)

    @staticmethod
    def any(**kw: Any) -> Field:
        return Field("any", **kw)

    @staticmethod
    def list_of(item: Field | Mapping[str, Any] | None = None, **kw: Any) -> Field:
        return Field("list", item=_coerce(item), **kw)

    @staticmethod
    def obj(fields: Mapping[str, Any], **kw: Any) -> Field:
        return Field("dict", fields=_coerce_map(fields), **kw)

    @staticmethod
    def enum(*values: Any, **kw: Any) -> Field:
        return Field("any", enum=list(values), **kw)


def _coerce(spec: Any) -> Field | None:
    if spec is None:
        return None
    if isinstance(spec, Field):
        return spec
    if isinstance(spec, dict):
        return Field("dict", fields=_coerce_map(spec))
    return Field("any")


def _coerce_map(fields: Mapping[str, Any]) -> dict[str, Field]:
    return {key: (_coerce(value) or Field("any")) for key, value in fields.items()}


def validate(payload: Any, schema: Mapping[str, Any] | Field, path: str = "$") -> list[str]:
    """返回全部错误（不是第一个），便于一次看清契约坏了几处。"""
    root = schema if isinstance(schema, Field) else _coerce_map(schema)  # type: ignore[assignment]
    if isinstance(root, Field):
        return _validate_value(payload, root, path)
    errors: list[str] = []
    for key, field in root.items():
        errors.extend(_validate_value(payload.get(key, _MISSING) if isinstance(payload, dict) else _MISSING, field, f"{path}.{key}"))
    return errors


def _validate_value(value: Any, field: Field, path: str) -> list[str]:
    if value is _MISSING:
        return [] if not field.required else [f"{path}: 缺少必填字段"]
    if value is None:
        return [] if field.nullable else [f"{path}: 不允许为 null"]

    errors: list[str] = []
    kind = field.kind

    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return [f"{path}: 期望 int，实际 {type(value).__name__}({value!r})"]
    elif kind == "num":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{path}: 期望 number，实际 {type(value).__name__}({value!r})"]
    elif kind == "str":
        if not isinstance(value, str):
            return [f"{path}: 期望 str，实际 {type(value).__name__}({value!r})"]
    elif kind == "bool":
        if not isinstance(value, bool):
            return [f"{path}: 期望 bool，实际 {type(value).__name__}({value!r})"]
    elif kind == "list":
        if not isinstance(value, list):
            return [f"{path}: 期望 list，实际 {type(value).__name__}({value!r})"]
        if field.item is not None:
            for index, element in enumerate(value):
                errors.extend(_validate_value(element, field.item, f"{path}[{index}]"))
    elif kind == "dict":
        if not isinstance(value, dict):
            return [f"{path}: 期望 object，实际 {type(value).__name__}({value!r})"]
        if field.fields is not None:
            for key, sub in field.fields.items():
                errors.extend(_validate_value(value.get(key, _MISSING), sub, f"{path}.{key}"))

    if field.enum is not None and value not in field.enum:
        errors.append(f"{path}: 取值 {value!r} 不在允许集合 {field.enum} 内")
    if isinstance(value, str):
        if field.min_len is not None and len(value) < field.min_len:
            errors.append(f"{path}: 长度 {len(value)} < 最小长度 {field.min_len}")
        if field.max_len is not None and len(value) > field.max_len:
            errors.append(f"{path}: 长度 {len(value)} > 最大长度 {field.max_len}")
        if field.pattern is not None and not re.fullmatch(field.pattern, value):
            errors.append(f"{path}: {value!r} 不匹配正则 {field.pattern}")
    if field.ge is not None and isinstance(value, (int, float)) and value < field.ge:
        errors.append(f"{path}: {value} < 下界 {field.ge}")
    if field.le is not None and isinstance(value, (int, float)) and value > field.le:
        errors.append(f"{path}: {value} > 上界 {field.le}")
    if field.checker is not None and not field.checker(value):
        errors.append(f"{path}: 未通过自定义校验 {value!r}")

    return errors


def require_extra_keys(payload: Mapping[str, Any], keys: Iterable[str], path: str = "$") -> list[str]:
    """校验额外字段存在（用于 RuoYi 这类字段分散在顶层的接口）。"""
    return [f"{path}.{key}: 缺少字段" for key in keys if key not in payload]
