"""OSV 连接器: aliases/related/upstream 分立保存, 区间边界语义完整保留。"""

from __future__ import annotations

from dataclasses import dataclass, field

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
class AffectedPackage:
    """受影响包: ecosystem/package/ranges/events/explicit versions 原样保留。"""

    ecosystem: str | None
    package_name: str | None
    ranges_type: str | None
    events: tuple[VersionRangeEvent, ...] = field(default_factory=tuple)
    explicit_versions: tuple[str, ...] = field(default_factory=tuple)
    unsupported_scheme: bool = False


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


def _string_tuple(value: object) -> tuple[str, ...]:
    """把任意 JSON 数组收敛为字符串元组; 非列表返回空而不猜测。"""
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))


def normalize_osv_record(payload: dict[str, object]) -> OsvRecord:
    """按固定 OSV schema 标准化; 未知 scheme 标 unsupported 不静默转换。"""
    osv_id = payload.get("id")
    if not isinstance(osv_id, str) or not osv_id:
        raise OsvContractError("missing osv id; raw record preserved by caller")
    schema_version = payload.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, str):
        raise OsvContractError("schema_version must be a string when present")
    aliases = _string_tuple(payload.get("aliases"))
    related = _string_tuple(payload.get("related"))
    upstream = _string_tuple(payload.get("upstream"))
    affected_packages: list[AffectedPackage] = []
    raw_affected = payload.get("affected")
    for entry in raw_affected if isinstance(raw_affected, list) else []:
        if not isinstance(entry, dict):
            raise OsvContractError("affected entry must be an object")
        package = entry.get("package")
        ecosystem: str | None = None
        package_name: str | None = None
        if isinstance(package, dict):
            ecosystem = str(package["ecosystem"]) if package.get("ecosystem") is not None else None
            package_name = str(package["name"]) if package.get("name") is not None else None
        events: list[VersionRangeEvent] = []
        ranges_type: str | None = None
        unsupported_scheme = False
        for version_range in entry.get("ranges", []):
            if not isinstance(version_range, dict):
                raise OsvContractError("range entry must be an object")
            ranges_type = (
                str(version_range.get("type")) if version_range.get("type") is not None else None
            )
            if ranges_type not in ("SEMVER", "ECOSYSTEM", "GIT") and ranges_type is not None:
                unsupported_scheme = True
            for event in version_range.get("events", []):
                if not isinstance(event, dict) or len(event) != 1:
                    raise OsvContractError("range event must carry exactly one boundary")
                boundary_type, boundary_value = next(iter(event.items()))
                if boundary_type not in ("introduced", "fixed", "last_affected"):
                    unsupported_scheme = True
                events.append(
                    VersionRangeEvent(
                        event_type=str(boundary_type), version_value=str(boundary_value)
                    )
                )
        explicit_versions = tuple(
            str(item) for item in entry.get("versions", []) if isinstance(item, str)
        )
        affected_packages.append(
            AffectedPackage(
                ecosystem=ecosystem,
                package_name=package_name,
                ranges_type=ranges_type,
                events=tuple(events),
                explicit_versions=explicit_versions,
                unsupported_scheme=unsupported_scheme,
            )
        )
    return OsvRecord(
        osv_id=osv_id,
        modified_at=str(payload["modified"]) if payload.get("modified") is not None else None,
        aliases=aliases,
        related=related,
        upstream=upstream,
        affected=tuple(affected_packages),
        withdrawn=payload.get("withdrawn") is not None,
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
    return [item for item in results if isinstance(item, dict)]
