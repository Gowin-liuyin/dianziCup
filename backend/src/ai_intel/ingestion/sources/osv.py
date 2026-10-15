"""OSV 连接器: aliases/related/upstream 分立保存, 区间边界语义完整保留。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from ai_intel.infrastructure.models.json_output import strict_json_object

OSV_CONNECTOR_NAME = "osv-vulnerability"
OSV_CONNECTOR_VERSION = "osv-1.0.0"
OSV_SOURCE_SCHEMA_VERSION = "osv-schema-1"


class OsvContractError(RuntimeError):
    """未知字段版本或响应结构: 明确报错并保留原始记录, 不猜语义。"""


@dataclass(frozen=True)
class VersionRangeEvent:
    """区间事件: introduced/fixed/last_affected 边界类型显式保留。"""

    event_type: str
    version_value: str


@dataclass(frozen=True)
class PackageRange:
    """独立范围分支；不同版本体系及仓库不能依据扁平兼容字段合并。"""

    range_type: str | None
    events: tuple[VersionRangeEvent, ...] = field(default_factory=tuple)
    repository_uri: str | None = None
    unsupported_scheme: bool = False


@dataclass(frozen=True)
class AffectedPackage:
    """range_branches 为逐分支输入；旧 ranges_type/events 仅保留调用兼容。"""

    ecosystem: str | None
    package_name: str | None
    ranges_type: str | None
    events: tuple[VersionRangeEvent, ...] = field(default_factory=tuple)
    explicit_versions: tuple[str, ...] = field(default_factory=tuple)
    unsupported_scheme: bool = False
    range_branches: tuple[PackageRange, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OsvRecord:
    """OSV 标准化记录: 三类关系分立; related 不合并身份。"""

    osv_id: str
    modified_at: str | None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    related: tuple[str, ...] = field(default_factory=tuple)
    upstream: tuple[str, ...] = field(default_factory=tuple)
    affected: tuple[AffectedPackage, ...] = field(default_factory=tuple)
    withdrawn: bool = False
    source_schema_version: str = OSV_SOURCE_SCHEMA_VERSION
    raw_record: dict[str, object] = field(default_factory=dict, repr=False)


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise OsvContractError(f"{field_name} must be an array of strings")
    return tuple(value)


def _optional_text(value: object, field_name: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise OsvContractError(f"{field_name} must be a string when present")
    return value


def _timestamp(value: object, field_name: str) -> str | None:
    text = _optional_text(value, field_name)
    if text is not None:
        try:
            timestamp = datetime.fromisoformat(text)
            if timestamp.utcoffset() is None or "T" not in text:
                raise ValueError("timestamp lacks explicit timezone")
        except ValueError:
            raise OsvContractError(f"{field_name} must be a timezone-aware timestamp") from None
    return text


def _objects(value: object, field_name: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) > 1000:
        raise OsvContractError(f"{field_name} must be a bounded array")
    result: list[dict[str, object]] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise OsvContractError(f"{field_name} entry must be an object")
        result.append(entry)
    return result


def normalize_osv_record(payload: dict[str, object]) -> OsvRecord:
    """按固定 OSV schema 标准化; 未知 scheme 标 unsupported 不静默转换。"""
    try:
        strict_json_object(json.dumps(payload, ensure_ascii=False, allow_nan=False), 2097152)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise OsvContractError("invalid or oversized OSV JSON record") from None
    osv_id = payload.get("id")
    if not isinstance(osv_id, str) or not osv_id:
        raise OsvContractError("missing osv id; raw record preserved by caller")
    schema_version = payload.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, str):
        raise OsvContractError("schema_version must be a string when present")
    if schema_version is not None and not re.fullmatch(
        r"1\.(0|[1-9]\d*)\.(0|[1-9]\d*)", schema_version
    ):
        raise OsvContractError("unsupported OSV schema major version or malformed version")
    aliases = _string_tuple(payload.get("aliases", []), "aliases")
    related = _string_tuple(payload.get("related", []), "related")
    upstream = _string_tuple(payload.get("upstream", []), "upstream")
    modified_at = _timestamp(payload.get("modified"), "modified")
    _timestamp(payload.get("published"), "published")
    withdrawn_at = _timestamp(payload.get("withdrawn"), "withdrawn")
    affected_packages: list[AffectedPackage] = []
    for entry in _objects(payload.get("affected", []), "affected"):
        package = entry.get("package")
        ecosystem: str | None = None
        package_name: str | None = None
        if package is not None and not isinstance(package, dict):
            raise OsvContractError("package must be an object when present")
        if isinstance(package, dict):
            ecosystem = _optional_text(package.get("ecosystem"), "package.ecosystem")
            package_name = _optional_text(package.get("name"), "package.name")
        events: list[VersionRangeEvent] = []
        ranges_type: str | None = None
        unsupported_scheme = False
        range_branches: list[PackageRange] = []
        for version_range in _objects(entry.get("ranges", []), "ranges"):
            ranges_type = _optional_text(version_range.get("type"), "ranges.type")
            repository_uri = _optional_text(version_range.get("repo"), "ranges.repo")
            branch_unsupported = ranges_type not in ("SEMVER", "ECOSYSTEM", "GIT")
            branch_events: list[VersionRangeEvent] = []
            for event in _objects(version_range.get("events", []), "ranges.events"):
                if len(event) != 1:
                    raise OsvContractError("range event must carry exactly one boundary")
                boundary_type, boundary_value = next(iter(event.items()))
                if not isinstance(boundary_value, str) or not boundary_value:
                    raise OsvContractError("range boundary value must be a nonempty string")
                if boundary_type not in ("introduced", "fixed", "last_affected", "limit"):
                    branch_unsupported = True
                branch_events.append(
                    VersionRangeEvent(event_type=boundary_type, version_value=boundary_value)
                )
            range_branches.append(
                PackageRange(ranges_type, tuple(branch_events), repository_uri, branch_unsupported)
            )
            events.extend(branch_events)
            unsupported_scheme = unsupported_scheme or branch_unsupported
        explicit_versions = _string_tuple(entry.get("versions", []), "versions")
        affected_packages.append(
            AffectedPackage(
                ecosystem=ecosystem,
                package_name=package_name,
                ranges_type=ranges_type,
                events=tuple(events),
                explicit_versions=explicit_versions,
                unsupported_scheme=unsupported_scheme,
                range_branches=tuple(range_branches),
            )
        )
    return OsvRecord(
        osv_id=osv_id,
        modified_at=modified_at,
        aliases=aliases,
        related=related,
        upstream=upstream,
        affected=tuple(affected_packages),
        withdrawn=withdrawn_at is not None,
        raw_record=payload,
    )


def bounded_package_query(
    query_allowed_packages: object, ecosystem: str, package_name: str
) -> list[dict[str, object]]:
    """按允许产品/包小范围查询; 拒绝无界全库下载请求。"""
    if not ecosystem or not package_name:
        raise OsvContractError("ecosystem and package are required for bounded query")
    results = query_allowed_packages(ecosystem, package_name)  # type: ignore[operator]
    if not isinstance(results, list):
        raise OsvContractError("query results must be a list")
    return _objects(results, "query results")
