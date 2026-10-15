"""库存格式dispatcher与冻结声明序列化；历史读取不使用新代码重解析旧SBOM。"""

import hashlib
import ipaddress
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, urlsplit

from packageurl import PackageURL

from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.assets.manifest_parser import (
    ManifestParseResult,
    ManifestValidationError,
    parse_manifest,
)
from ai_intel.assets.sbom_inventory_contracts import (
    AssetSnapshotSbomResponse,
    SbomRedactionResponse,
)
from ai_intel.assets.sbom_parser import SBOM_ADAPTER_VERSION, SbomParseResult, parse_sbom
from ai_intel.domain.access import AccessScope


class SbomProjectionValidationError(ValueError):
    """冻结展示载荷的标记/引用不一致，不接受伪造的脱敏前缀声明。"""


def _decoded_uri_text(value: str) -> str:
    for _ in range(4):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


def _safe_http_uri(value: str) -> bool:
    """仅离线判断可展示URI；不解析DNS，userinfo/query/fragment不作为公开文档定位。"""
    if (
        not value.isascii()
        or any(ord(char) <= 32 for char in value)
        or any(char in "\\?#" for char in value)
    ):
        return False
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or "%" in parsed.netloc
        ):
            return False
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return False
        host = host.lower().rstrip(".")
        address = None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if re.fullmatch(r"[0-9.]+", host):
                return False
        if address is not None:
            if not address.is_global:
                return False
        elif (
            "." not in host
            or host in {"localhost", "localhost.localdomain"}
            or host.endswith(
                (".localhost", ".localdomain", ".local", ".internal", ".lan", ".home", ".intranet")
            )
            or len(host) > 253
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in host.split(".")
            )
        ):
            return False
        path = _decoded_uri_text(parsed.path)
        return not any(ord(char) <= 32 or char in "\\:@?#%" for char in path)
    except ValueError:
        return False


def _safe_purl_reference(value: str) -> bool:
    try:
        package = PackageURL.from_string(value)
    except ValueError:
        return False
    if package.qualifiers or package.subpath:
        return False
    fields = (package.type, package.namespace or "", package.name, package.version or "")
    return not any(
        any(ord(char) <= 32 or char in "\\:%?#" for char in field) or "://" in field
        for field in fields
    ) and not any(char in "/@" for char in (package.version or ""))


def _safe_reference(value: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@+-]*", value):
        return True
    if re.fullmatch(r"DocumentRef-[A-Za-z0-9.+-]+:SPDXRef-[A-Za-z0-9.-]+", value):
        return True
    if re.fullmatch(r"urn:uuid:[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
        return True
    cdx = re.fullmatch(
        r"urn:cdx:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/[1-9][0-9]*#(.+)", value
    )
    if cdx is not None:
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@+-]*", cdx[1]))
    if value.startswith("pkg:"):
        return _safe_purl_reference(value)
    return _safe_http_uri(value)


def safe_sbom_snapshot(snapshot: AssetSnapshotResponse) -> AssetSnapshotResponse:
    """仅隐藏SBOM中不可安全展示的PURL；组件身份、来源事实hash和旧JSON/CSV不变。"""
    if snapshot.source_kind not in {"cyclonedx_json", "spdx_json"}:
        return snapshot
    return snapshot.model_copy(
        update={
            "components": tuple(
                component
                if component.purl is None or _safe_purl_reference(component.purl)
                else component.model_copy(update={"purl": None})
                for component in snapshot.components
            )
        }
    )


def safe_sbom_sidecar(
    result: AssetSnapshotSbomResponse,
    snapshot: AssetSnapshotResponse | None = None,
) -> AssetSnapshotSbomResponse:
    """源摘要不变；schema2已标位置的opaque引用可重放，其余客户端保留前缀不受信任。"""
    old_redactions = {item.source_field_locator: item for item in result.redactions}
    if len(old_redactions) != len(result.redactions) or (
        result.schema_version == "r11-sbom-sidecar-1" and old_redactions
    ):
        raise SbomProjectionValidationError("invalid stored SBOM display markers")
    redactions = dict(old_redactions)
    used_redactions: set[str] = set()

    def mark(locator: str, alias: str | None = None) -> None:
        redactions[locator] = SbomRedactionResponse(
            source_field_locator=locator,
            reason="unsafe_uri_or_path",
            replacement_ref=alias,
        )
        used_redactions.add(locator)

    def reference(value: str, locator: str) -> str:
        if (
            result.schema_version == "r11-sbom-sidecar-2"
            and locator in old_redactions
            and re.fullmatch(r"redacted-ref:[0-9a-f]{64}", value)
            and old_redactions[locator].reason == "unsafe_uri_or_path"
            and old_redactions[locator].replacement_ref == value
        ):
            used_redactions.add(locator)
            return value
        if _safe_reference(value):
            return value
        if result.schema_version == "r11-sbom-sidecar-2":
            raise SbomProjectionValidationError("unbound stored SBOM display reference")
        alias = "redacted-ref:" + hashlib.sha256(value.encode()).hexdigest()
        mark(locator, alias)
        return alias

    def locator(value: str) -> str:
        if not value.startswith("/"):
            raise SbomProjectionValidationError("invalid stored SBOM source locator")
        if result.schema_version == "r11-sbom-sidecar-2" and value in old_redactions:
            marker = old_redactions[value]
            if marker.replacement_ref is None and any(
                re.fullmatch(r"redacted-field:[0-9a-f]{64}", field) for field in value.split("/")
            ):
                used_redactions.add(value)
                return value
        fields = value.split("/")
        protected = []
        changed = False
        for field in fields:
            decoded = _decoded_uri_text(field.replace("~1", "/").replace("~0", "~"))
            if decoded.startswith(("/", "\\", "~/")) or re.match(
                r"^[A-Za-z][A-Za-z0-9+.-]*:",
                decoded,
            ):
                if result.schema_version == "r11-sbom-sidecar-2":
                    raise SbomProjectionValidationError("unbound stored SBOM source locator")
                field = "redacted-field:" + hashlib.sha256(decoded.encode()).hexdigest()
                changed = True
            protected.append(field)
        safe = "/".join(protected)
        if changed:
            mark(safe)
        return safe

    components = tuple(
        item.model_copy(
            update={
                "source_ref": None
                if item.source_ref is None
                else reference(
                    item.source_ref,
                    item.source_field_locator
                    + ("/bom-ref" if result.source_format == "cyclonedx_json" else "/SPDXID"),
                )
            }
        )
        for item in result.component_sources
    )
    edges = tuple(
        item.model_copy(
            update={
                "source_ref": reference(
                    item.source_ref,
                    item.source_field_locator.rsplit("/", 2)[0] + "/ref"
                    if result.source_format == "cyclonedx_json"
                    else item.source_field_locator + "/spdxElementId",
                ),
                "target_ref": reference(
                    item.target_ref,
                    item.source_field_locator
                    if result.source_format == "cyclonedx_json"
                    else item.source_field_locator + "/relatedSpdxElement",
                ),
            }
        )
        for item in result.dependency_edges
    )
    declarations = tuple(
        item.model_copy(
            update={
                field: tuple(
                    reference(value, f"{item.source_field_locator}/{field}/{index}")
                    for index, value in enumerate(getattr(item, field))
                )
                for field in ("assemblies", "dependencies", "vulnerabilities")
            }
        )
        for item in result.completeness_declarations
    )
    documents = []
    for item in result.external_documents:
        uri = item.document_uri
        uri_locator = item.source_field_locator + "/spdxDocument"
        if uri is None:
            if (
                uri_locator not in old_redactions
                or old_redactions[uri_locator].replacement_ref is not None
            ):
                raise SbomProjectionValidationError("invalid stored SBOM document marker")
            used_redactions.add(uri_locator)
        elif uri is not None and not _safe_http_uri(uri):
            if result.schema_version == "r11-sbom-sidecar-2":
                raise SbomProjectionValidationError("unbound stored SBOM document URI")
            mark(uri_locator)
            uri = None
        documents.append(item.model_copy(update={"document_uri": uri}))
    if snapshot is not None:
        hidden_purls = {
            item.component_id
            for item in snapshot.components
            if item.purl is not None and not _safe_purl_reference(item.purl)
        }
        for component_source in result.component_sources:
            for field in component_source.field_sources:
                if field.field_name == "purl" and component_source.component_id in hidden_purls:
                    mark(field.source_field_locator)
    else:
        for component_source in result.component_sources:
            for field in component_source.field_sources:
                marker = old_redactions.get(field.source_field_locator)
                if (
                    field.field_name == "purl"
                    and marker is not None
                    and marker.replacement_ref is None
                ):
                    used_redactions.add(field.source_field_locator)
    unmapped = tuple(locator(value) for value in result.unmapped_field_locators)
    if result.schema_version == "r11-sbom-sidecar-2" and set(old_redactions) != used_redactions:
        raise SbomProjectionValidationError("unbound stored SBOM display marker")
    return result.model_copy(
        update={
            "schema_version": "r11-sbom-sidecar-2",
            "component_sources": components,
            "dependency_edges": edges,
            "completeness_declarations": declarations,
            "external_documents": tuple(documents),
            "unmapped_field_locators": unmapped,
            "redactions": tuple(redactions[key] for key in sorted(redactions)),
        }
    )


@dataclass(frozen=True)
class InventoryParseResult:
    manifest: ManifestParseResult
    sbom: SbomParseResult | None

    @property
    def semantic_sha256(self) -> str:
        if self.sbom is not None:
            return self.sbom.combined_semantic_sha256
        return self.manifest.snapshot.snapshot_sha256


def parse_inventory_input(
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
) -> InventoryParseResult:
    """显式格式选择；SBOM拒绝CSV映射，未知格式仍由既有parser固定拒绝。"""
    if manifest_format in {"cyclonedx_json", "spdx_json"}:
        if csv_column_mapping is not None:
            raise ManifestValidationError("unexpected_csv_mapping")
        sbom = parse_sbom(
            raw_bytes,
            sbom_format=manifest_format,
            scope=scope,
            authorized_asset_tenant_id=authorized_asset_tenant_id,
            asset_id=asset_id,
            snapshot_number=snapshot_number,
            source_version=source_version,
            observed_at=observed_at,
            recorded_at=recorded_at,
        )
        return InventoryParseResult(sbom.manifest, sbom)
    return InventoryParseResult(
        parse_manifest(
            raw_bytes,
            manifest_format=manifest_format,
            scope=scope,
            authorized_asset_tenant_id=authorized_asset_tenant_id,
            asset_id=asset_id,
            snapshot_number=snapshot_number,
            source_version=source_version,
            observed_at=observed_at,
            recorded_at=recorded_at,
            csv_column_mapping=csv_column_mapping,
        ),
        None,
    )


def freeze_sbom_sidecar(result: SbomParseResult) -> AssetSnapshotSbomResponse:
    """身份只由认证候选取得，typed sidecar与版本/hash一次冻结。"""
    snapshot = result.manifest.snapshot
    return safe_sbom_sidecar(
        AssetSnapshotSbomResponse.model_validate(
            {
                "schema_version": "r11-sbom-sidecar-1",
                "snapshot_id": snapshot.snapshot_id,
                "asset_id": snapshot.asset_id,
                "tenant_id": snapshot.tenant_id,
                "adapter_version": SBOM_ADAPTER_VERSION,
                "source_format": snapshot.source_kind,
                "spec_version": result.spec_version,
                "projection_sha256": snapshot.snapshot_sha256,
                "sidecar_sha256": result.sidecar_sha256,
                "combined_semantic_sha256": result.combined_semantic_sha256,
                "raw_sha256": result.raw_sha256,
                "component_sources": result.component_sources,
                "dependency_edges": result.dependency_edges,
                "completeness_declarations": result.completeness_declarations,
                "external_documents": result.external_documents,
                "unmapped_field_locators": result.unmapped_field_locators,
            }
        ),
        AssetSnapshotResponse.model_validate(snapshot),
    )
