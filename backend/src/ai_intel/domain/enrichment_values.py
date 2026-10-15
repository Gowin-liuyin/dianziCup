"""Nine bounded signal values preserve source semantics without granting publication authority."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from ai_intel.domain.values import UtcTimestamp

Label = Annotated[str, Field(min_length=1, max_length=200)]
Description = Annotated[str, Field(min_length=1, max_length=2000)]
CveId = Annotated[str, Field(pattern=r"^CVE-[0-9]{4}-[0-9]{4,19}$")]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
DimensionName = Literal[
    "cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"
]


class SignalValue(BaseModel):
    """Strict values are candidates; source, evidence and permissions are checked separately."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CvssSignalValue(SignalValue):
    kind: Literal["cvss_signal"] = "cvss_signal"
    standard_version: Literal["2.0", "3.0", "3.1", "4.0"]
    base_score: Annotated[float, Field(strict=True, ge=0, le=10, allow_inf_nan=False)]
    vector: Annotated[str, Field(min_length=1, max_length=500)]
    authority: Label
    scored_at: UtcTimestamp | None = None


class EpssSignalValue(SignalValue):
    kind: Literal["epss_signal"] = "epss_signal"
    cve_id: CveId
    probability: Probability
    percentile: Probability
    data_date: date
    model_version: Label | None = None


class KevSignalValue(SignalValue):
    kind: Literal["kev_signal"] = "kev_signal"
    cve_id: CveId
    catalog_version: Label
    date_added: date
    required_action: Description
    due_date: date | None = None
    ransomware_use: Literal["known", "unknown"] = "unknown"


class WeaknessValue(SignalValue):
    kind: Literal["weakness"] = "weakness"
    cwe_id: Annotated[str, Field(pattern=r"^CWE-[1-9][0-9]{0,5}$")]
    taxonomy_version: Label
    name: Label


class AtlasMappingValue(SignalValue):
    kind: Literal["atlas_mapping"] = "atlas_mapping"
    technique_id: Annotated[str, Field(pattern=r"^AML\.T[0-9]{4}(\.[0-9]{3})?$")]
    taxonomy_version: Label
    mechanism: Description
    prerequisites: tuple[Description, ...] = Field(default=(), max_length=20)


class VersionInterval(SignalValue):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "not": {
                        "required": ["fixed", "last_affected"],
                        "properties": {
                            "fixed": {"type": "string"},
                            "last_affected": {"type": "string"},
                        },
                    }
                },
                {
                    "anyOf": [
                        {"required": [field], "properties": {field: {"type": "string"}}}
                        for field in ("introduced", "fixed", "last_affected")
                    ]
                },
            ]
        }
    )

    introduced: Label | None = None
    fixed: Label | None = None
    last_affected: Label | None = None
    branch: Label | None = None

    @model_validator(mode="after")
    def require_unambiguous_upper_boundary(self) -> VersionInterval:
        if self.fixed is not None and self.last_affected is not None:
            raise ValueError("fixed exclusive and last_affected inclusive cannot share an interval")
        if self.introduced is None and self.fixed is None and self.last_affected is None:
            raise ValueError("version interval requires a source boundary")
        return self


class VersionAssertionValue(SignalValue):
    kind: Literal["version_assertion"] = "version_assertion"
    package_key: Label
    ecosystem: Label
    scheme: Literal["pep440", "semver", "osv_ecosystem", "git", "unknown"]
    raw_expression: Description
    intervals: tuple[VersionInterval, ...] = Field(default=(), max_length=50)
    explicit_versions: tuple[Label, ...] = Field(default=(), max_length=100)
    comparison_support: Literal["supported", "unsupported", "unknown"] = "unknown"
    vendor_fix: Description | None = None
    mitigations: tuple[Description, ...] = Field(default=(), max_length=20)
    limitations: tuple[Description, ...] = Field(default=(), max_length=20)


class LiteratureReferenceValue(SignalValue):
    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {
                    "properties": {
                        "target_document_id": {"type": "null"},
                        "target_revision_id": {"type": "null"},
                    }
                },
                {
                    "required": ["target_document_id", "target_revision_id"],
                    "properties": {
                        "target_document_id": {"type": "string"},
                        "target_revision_id": {"type": "string"},
                    },
                },
            ]
        }
    )

    kind: Literal["literature_reference"] = "literature_reference"
    uri: HttpUrl
    title: Annotated[str, Field(min_length=1, max_length=500)]
    reference_kind: Literal["paper", "article", "standard", "policy"]
    relation: Literal["background", "analysis", "defense", "experimental"]
    support_summary: Description
    target_document_id: UUID | None = None
    target_revision_id: UUID | None = None
    limitations: tuple[Description, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def require_paired_target_identity(self) -> LiteratureReferenceValue:
        if (self.target_document_id is None) != (self.target_revision_id is None):
            raise ValueError("target document and revision identity must be paired")
        return self


class ArtifactReferenceValue(SignalValue):
    kind: Literal["artifact_reference"] = "artifact_reference"
    uri: HttpUrl
    title: Annotated[str, Field(min_length=1, max_length=500)]
    artifact_kind: Literal["poc", "detection_template", "analysis_repository"]
    static_status: Literal["candidate_found", "static_reviewed", "verification_failed"]
    commit_sha: Annotated[str, Field(pattern=r"^([0-9a-f]{40}|[0-9a-f]{64})$")] | None = None
    artifact_path: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    license_identifier: Label | None = None
    limitations: tuple[Description, ...] = Field(default=(), max_length=20)


class ExposureAggregateValue(SignalValue):
    """Only aggregate service counts; no host records or affected-asset estimate are accepted."""

    kind: Literal["exposure_aggregate"] = "exposure_aggregate"
    provider: Literal["hunter", "quake"]
    query_id: Label
    query_version: Label
    service_count: Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]
    retrieved_at: UtcTimestamp
    observed_at: UtcTimestamp | None = None
    ttl_seconds: Annotated[int, Field(strict=True, ge=1, le=604800)]
    limitations: tuple[Description, ...] = Field(min_length=1, max_length=20)


EnrichmentValue = Annotated[
    CvssSignalValue
    | EpssSignalValue
    | KevSignalValue
    | WeaknessValue
    | AtlasMappingValue
    | VersionAssertionValue
    | LiteratureReferenceValue
    | ArtifactReferenceValue
    | ExposureAggregateValue,
    Field(discriminator="kind"),
]

ENRICHMENT_VALUE_MODELS: dict[str, type[SignalValue]] = {
    "cvss_signal": CvssSignalValue,
    "epss_signal": EpssSignalValue,
    "kev_signal": KevSignalValue,
    "weakness": WeaknessValue,
    "atlas_mapping": AtlasMappingValue,
    "version_assertion": VersionAssertionValue,
    "literature_reference": LiteratureReferenceValue,
    "artifact_reference": ArtifactReferenceValue,
    "exposure_aggregate": ExposureAggregateValue,
}
