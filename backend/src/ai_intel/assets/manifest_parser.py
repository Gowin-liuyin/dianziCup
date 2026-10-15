"""受控bytes清单的纯解析候选；不读取文件、不执行命令、不写入资产事实。"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from ai_intel.domain.access import READ_ASSET, AccessScope, PermissionDeniedError
from ai_intel.infrastructure.models.json_output import strict_json_object

PARSER_VERSION = "r11-manifest-parser-1"
MAX_MANIFEST_BYTES = 10485760
MAX_COMPONENTS = 10000
MAX_JSON_DEPTH = 16
MAX_JSON_NODES = 50000
MAX_STRING_LENGTH = 4096
COMPONENT_FIELDS = frozenset(
    {
        "ecosystem",
        "package_name",
        "display_name",
        "purl",
        "version",
        "version_scheme",
        "image_digest",
        "dependency_path",
    }
)
MANIFEST_FIELDS = frozenset(
    {
        "format_version",
        "components",
        "inventory_completeness",
        "declared_scope",
        "configuration",
        "tool_permissions",
        "input_channels",
        "network_exposure",
    }
)
CONFIGURATION_TYPES: dict[str, type[str] | type[bool]] = {
    "model_name": str,
    "provider_name": str,
    "trust_remote_code": bool,
    "authentication_required": bool,
}
INPUT_CHANNELS = frozenset({"public_api", "uploaded_documents", "retrieved_web_content"})
NETWORK_FIELDS = frozenset({"public_endpoint", "outbound_network_allowed"})
InventoryCompleteness = Literal["complete_for_declared_scope", "partial", "unknown"]


class ManifestValidationError(ValueError):
    """固定原因和有界字段位置；异常不回显输入字节、值或秘密。"""

    def __init__(self, code: str, locator: str = "/") -> None:
        self.code = code
        self.locator = locator
        super().__init__(f"{code} at {locator}")


@dataclass(frozen=True)
class DeclaredField:
    """配置值仅为清单声明；缺字段或None均不能解释为false。"""

    name: str
    value: str | bool | None
    source_field_locator: str


@dataclass(frozen=True)
class ComponentCandidate:
    """主键、包身份、展示名和purl分别保存；不由名称猜配置或版本。"""

    component_id: str
    ecosystem: str
    package_name: str
    display_name: str | None
    purl: str | None
    version: str | None
    version_scheme: str
    image_digest: str | None
    dependency_path: tuple[str, ...] | None
    source_field_locator: str


@dataclass(frozen=True)
class SnapshotCandidate:
    """按03合同组织的内部候选；不是领域公开schema或持久化快照。"""

    schema_version: Literal["r11-asset-candidate-1"]
    snapshot_id: str
    asset_id: str
    tenant_id: str
    snapshot_number: int
    observed_at: datetime
    recorded_at: datetime
    source_kind: str
    inventory_completeness: InventoryCompleteness
    declared_scope: tuple[str, ...]
    components: tuple[ComponentCandidate, ...]
    configuration: tuple[DeclaredField, ...]
    tool_permissions: tuple[str, ...] | None
    input_channels: tuple[DeclaredField, ...] | None
    network_exposure: tuple[DeclaredField, ...] | None
    snapshot_sha256: str


@dataclass(frozen=True)
class ManifestIssue:
    """冲突保留所有来源位置，不按顺序挑选一个版本。"""

    code: str
    locators: tuple[str, ...]


@dataclass(frozen=True)
class ManifestParseResult:
    """原字节仅留在调用者内存且repr隐藏，持久化策略由后续授权入口决定。"""

    snapshot: SnapshotCandidate
    source_sha256: str
    source_version: str
    parser_version: str
    issues: tuple[ManifestIssue, ...]
    source_bytes: bytes = field(repr=False)


def _text(value: object, locator: str, *, nullable: bool = True) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ManifestValidationError("invalid_field_type", locator)
    if not value or len(value) > MAX_STRING_LENGTH or any(ord(char) < 32 for char in value):
        raise ManifestValidationError("invalid_string", locator)
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ManifestValidationError("invalid_string", locator) from None
    return value


def _object(value: object, locator: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ManifestValidationError("invalid_field_type", locator)
    return {key: child for key, child in value.items()}


def _known_fields(record: Mapping[str, object], allowed: frozenset[str], locator: str) -> None:
    if not set(record) <= allowed:
        raise ManifestValidationError("unsupported_field", locator)


def _text_list(value: object, locator: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 64:
        raise ManifestValidationError("invalid_field_type", locator)
    result: list[str] = []
    for index, child in enumerate(value):
        text = _text(child, f"{locator}/{index}", nullable=False)
        if text is None:
            raise ManifestValidationError("invalid_field_type", locator)
        result.append(text)
    if len(set(result)) != len(result):
        raise ManifestValidationError("duplicate_value", locator)
    return tuple(result)


def _safe_package_name(value: str, locator: str) -> None:
    if (
        not re.fullmatch(r"[A-Za-z0-9@._/-]+", value)
        or value.startswith(("/", "."))
        or ".." in value.split("/")
        or "//" in value
        or value.endswith("/")
    ):
        raise ManifestValidationError("invalid_package_name", locator)


def _component(
    record: Mapping[str, object], locator: str, tenant_id: str, asset_id: str
) -> ComponentCandidate:
    _known_fields(record, COMPONENT_FIELDS, locator)
    if record.get("package_name") is None:
        raise ManifestValidationError("missing_package_name", locator)
    package_name = _text(record["package_name"], locator + "/package_name", nullable=False)
    if package_name is None:
        raise ManifestValidationError("missing_package_name", locator)
    _safe_package_name(package_name, locator + "/package_name")
    ecosystem = _text(record.get("ecosystem"), locator + "/ecosystem") or "unknown"
    version = _text(record.get("version"), locator + "/version")
    scheme = {"PyPI": "pep440", "npm": "semver"}.get(ecosystem, "unknown")
    declared_scheme = _text(record.get("version_scheme"), locator + "/version_scheme")
    if declared_scheme is not None and declared_scheme != scheme:
        raise ManifestValidationError("conflicting_version_scheme", locator + "/version_scheme")
    purl = _text(record.get("purl"), locator + "/purl")
    if purl is not None and not re.fullmatch(r"pkg:[a-z][a-z0-9.+-]*/[A-Za-z0-9._%@/+~-]+", purl):
        raise ManifestValidationError("unsupported_purl", locator + "/purl")
    image_digest = _text(record.get("image_digest"), locator + "/image_digest")
    if image_digest is not None and not re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest):
        raise ManifestValidationError("invalid_image_digest", locator + "/image_digest")
    dependency_path = None
    if record.get("dependency_path") is not None:
        dependency_path = _text_list(record["dependency_path"], locator + "/dependency_path")
        for path_component in dependency_path:
            _safe_package_name(path_component, locator + "/dependency_path")
    identity = json.dumps(
        [tenant_id, asset_id, ecosystem, package_name, version, image_digest, dependency_path],
        ensure_ascii=True,
    )
    return ComponentCandidate(
        str(uuid5(NAMESPACE_URL, identity)),
        ecosystem,
        package_name,
        _text(record.get("display_name"), locator + "/display_name"),
        purl,
        version,
        scheme,
        image_digest,
        dependency_path,
        locator,
    )


def _declared_fields(
    value: object, allowed_types: Mapping[str, type[str] | type[bool]], locator: str
) -> tuple[DeclaredField, ...]:
    record = _object(value, locator)
    _known_fields(record, frozenset(allowed_types), locator)
    result: list[DeclaredField] = []
    for name in sorted(record):
        child = record[name]
        field_locator = f"{locator}/{name}"
        if child is not None and type(child) is not allowed_types[name]:
            raise ManifestValidationError("invalid_field_type", field_locator)
        if isinstance(child, str):
            child = _text(child, field_locator)
        if child is None or isinstance(child, (str, bool)):
            result.append(DeclaredField(name, child, field_locator))
    return tuple(result)


def _json_rows(raw: bytes) -> tuple[dict[str, object], list[tuple[dict[str, object], str]]]:
    try:
        manifest = strict_json_object(raw, MAX_MANIFEST_BYTES, maximum_nodes=MAX_JSON_NODES)
    except UnicodeDecodeError:
        raise ManifestValidationError("invalid_encoding") from None
    except (ValueError, UnicodeError, RecursionError):
        raise ManifestValidationError("invalid_json") from None
    pending: list[tuple[object, int]] = [(manifest, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise ManifestValidationError("json_depth_limit")
        if isinstance(value, str):
            _text(value, "/")
        elif isinstance(value, dict):
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
    _known_fields(manifest, MANIFEST_FIELDS, "/")
    if type(manifest.get("format_version")) is not int or manifest["format_version"] != 1:
        raise ManifestValidationError("unsupported_format_version", "/format_version")
    components = manifest.get("components")
    if not isinstance(components, list):
        raise ManifestValidationError("invalid_field_type", "/components")
    if len(components) > MAX_COMPONENTS:
        raise ManifestValidationError("component_limit", "/components")
    return manifest, [
        (_object(value, f"/components/{index}"), f"/components/{index}")
        for index, value in enumerate(components)
    ]


def _csv_rows(
    raw: bytes, column_mapping: Mapping[str, str] | None
) -> list[tuple[dict[str, object], str]]:
    if column_mapping is None or not isinstance(column_mapping, Mapping):
        raise ManifestValidationError("missing_csv_mapping", "csv:line:1")
    if (
        not set(column_mapping) <= COMPONENT_FIELDS - {"dependency_path"}
        or "package_name" not in column_mapping
        or any(not isinstance(value, str) or not value for value in column_mapping.values())
        or len(set(column_mapping.values())) != len(column_mapping)
    ):
        raise ManifestValidationError("invalid_csv_mapping", "csv:line:1")
    for column in column_mapping.values():
        _text(column, "csv:line:1", nullable=False)
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise ManifestValidationError("invalid_encoding", "csv:line:1") from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    rows: list[tuple[dict[str, object], str]] = []
    try:
        header = next(reader, [])
        if len(set(header)) != len(header) or set(header) != set(column_mapping.values()):
            raise ManifestValidationError("invalid_csv_columns", "csv:line:1")
        for values in reader:
            locator = f"csv:line:{reader.line_num}"
            if len(values) != len(header):
                raise ManifestValidationError("invalid_csv", locator)
            if len(rows) >= MAX_COMPONENTS:
                raise ManifestValidationError("component_limit", locator)
            cells = dict(zip(header, values, strict=True))
            rows.append(
                ({name: cells[column] or None for name, column in column_mapping.items()}, locator)
            )
    except csv.Error:
        raise ManifestValidationError("invalid_csv", f"csv:line:{reader.line_num}") from None
    return rows


def parse_manifest(
    raw_bytes: bytes,
    *,
    manifest_format: str,
    scope: AccessScope,
    authorized_asset_tenant_id: str,
    asset_id: str,
    snapshot_number: int,
    source_version: str,
    observed_at: datetime,
    recorded_at: datetime,
    csv_column_mapping: Mapping[str, str] | None = None,
) -> ManifestParseResult:
    """仅接受调用方认证的租户与资产引用；READ_ASSET不授予持久化导入权限。

    JSON仅支持本模块的format_version=1；CSV仅支持显式映射组件列。
    purl保留受限不含qualifier/subpath的来源标签，不推断生态或版本，也不验证包一致性。
    原始字节、source_version与字段定位只构成候选证据，不证明声明真实或清单完整。
    """
    if not isinstance(scope, AccessScope):
        raise PermissionDeniedError("authenticated asset scope required")
    scope.requires(READ_ASSET)
    if not scope.tenant_id or not authorized_asset_tenant_id:
        raise PermissionDeniedError("tenant asset scope required")
    scope.enforce_visible("tenant", authorized_asset_tenant_id)
    if manifest_format not in {"json_manifest_v1", "csv_components_v1"}:
        raise ManifestValidationError("unsupported_format")
    if type(raw_bytes) is not bytes:
        raise ManifestValidationError("bytes_required")
    if not 1 <= len(raw_bytes) <= MAX_MANIFEST_BYTES:
        raise ManifestValidationError("manifest_size_limit")
    if type(snapshot_number) is not int or snapshot_number < 1:
        raise ManifestValidationError("invalid_snapshot_number")
    try:
        asset_id = str(UUID(asset_id))
    except (ValueError, AttributeError, TypeError):
        raise ManifestValidationError("invalid_asset_id") from None
    _text(source_version, "/source_version", nullable=False)
    for timestamp in (observed_at, recorded_at):
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ManifestValidationError("timezone_required")
    if manifest_format == "json_manifest_v1":
        if csv_column_mapping is not None:
            raise ManifestValidationError("unexpected_csv_mapping")
        manifest, rows = _json_rows(raw_bytes)
    else:
        manifest = {}
        rows = _csv_rows(raw_bytes, csv_column_mapping)
    completeness_value = manifest.get("inventory_completeness", "unknown")
    completeness: InventoryCompleteness
    if completeness_value == "complete_for_declared_scope":
        completeness = "complete_for_declared_scope"
    elif completeness_value == "partial":
        completeness = "partial"
    elif completeness_value == "unknown":
        completeness = "unknown"
    else:
        raise ManifestValidationError("invalid_inventory_completeness", "/inventory_completeness")
    declared_scope = _text_list(manifest.get("declared_scope", []), "/declared_scope")
    if completeness == "complete_for_declared_scope" and not declared_scope:
        raise ManifestValidationError("missing_declared_scope", "/declared_scope")
    components = tuple(_component(row, locator, scope.tenant_id, asset_id) for row, locator in rows)
    if len({component.component_id for component in components}) != len(components):
        raise ManifestValidationError("duplicate_component", "/components")
    configuration = _declared_fields(
        manifest.get("configuration", {}), CONFIGURATION_TYPES, "/configuration"
    )
    tool_permissions = None
    if manifest.get("tool_permissions") is not None:
        tool_permissions = _text_list(manifest["tool_permissions"], "/tool_permissions")
    input_channels = None
    if manifest.get("input_channels") is not None:
        input_channels = _declared_fields(
            manifest["input_channels"], dict.fromkeys(INPUT_CHANNELS, bool), "/input_channels"
        )
    network_exposure = None
    if manifest.get("network_exposure") is not None:
        network_exposure = _declared_fields(
            manifest["network_exposure"], dict.fromkeys(NETWORK_FIELDS, bool), "/network_exposure"
        )
    component_values = [
        [
            component.ecosystem,
            component.package_name,
            component.display_name,
            component.purl,
            component.version,
            component.version_scheme,
            component.image_digest,
            component.dependency_path,
        ]
        for component in components
    ]
    semantic_value = [
        sorted(component_values, key=lambda value: json.dumps(value)),
        completeness,
        sorted(declared_scope),
        [(value.name, value.value) for value in configuration],
        tool_permissions,
        None if input_channels is None else [(value.name, value.value) for value in input_channels],
        None
        if network_exposure is None
        else [(value.name, value.value) for value in network_exposure],
    ]
    snapshot_sha256 = hashlib.sha256(
        json.dumps(semantic_value, sort_keys=True).encode()
    ).hexdigest()
    snapshot_id = str(
        uuid5(NAMESPACE_URL, f"{scope.tenant_id}:{asset_id}:{snapshot_number}:{snapshot_sha256}")
    )
    snapshot = SnapshotCandidate(
        "r11-asset-candidate-1",
        snapshot_id,
        asset_id,
        scope.tenant_id,
        snapshot_number,
        observed_at.astimezone(UTC),
        recorded_at.astimezone(UTC),
        manifest_format,
        completeness,
        declared_scope,
        components,
        configuration,
        tool_permissions,
        input_channels,
        network_exposure,
        snapshot_sha256,
    )
    identities: dict[tuple[str, str], list[ComponentCandidate]] = {}
    for component in components:
        identities.setdefault((component.ecosystem, component.package_name), []).append(component)
    issues = tuple(
        ManifestIssue(
            "conflicting_component_versions", tuple(value.source_field_locator for value in group)
        )
        for group in identities.values()
        if len({value.version for value in group if value.version is not None}) > 1
    )
    return ManifestParseResult(
        snapshot,
        hashlib.sha256(raw_bytes).hexdigest(),
        source_version,
        PARSER_VERSION,
        issues,
        raw_bytes,
    )
