"""Bounded business requests select dimensions without granting identity or egress authority."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_intel.domain.enrichment_values import DimensionName
from ai_intel.infrastructure.models.generation import Provider

ALL_ENRICHMENT_DIMENSIONS: tuple[DimensionName, ...] = (
    "cvss",
    "epss",
    "kev",
    "cwe",
    "atlas",
    "versions",
    "literature",
    "poc",
    "exposure",
)


class EnrichmentModelInputVersions(BaseModel):
    """Server code versions identify the prompt, selector and output schema actually used."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    prompt_version: str = Field(min_length=1, max_length=200)
    selection_version: str = Field(min_length=1, max_length=200)
    schema_version: str = Field(min_length=1, max_length=200)


class EnrichmentExecutionPolicy(BaseModel):
    """Only server configuration creates this policy; no HTTP request grants model egress."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    generation_enabled: bool = False
    generation_provider: Provider | None = None
    approved_model: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_.:/-]{1,200}$")
    private_egress_granted: bool = False
    aggregate_enabled: bool = False
    data_mode: Literal["live", "fixture"] = "live"
    model_input_versions: EnrichmentModelInputVersions | None = None

    @model_validator(mode="after")
    def validate_model_authority(self) -> "EnrichmentExecutionPolicy":
        if self.generation_enabled and (
            self.generation_provider is None or self.approved_model is None
        ):
            raise ValueError("enabled generation requires an approved provider and model")
        if self.private_egress_granted and not self.generation_enabled:
            raise ValueError("private model egress requires enabled server generation")
        return self


class EventEnrichmentRequest(BaseModel):
    """Unknown product selection is retained; it never becomes an arbitrary provider query."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    expected_event_version: int = Field(strict=True, ge=1)
    dimensions: tuple[DimensionName, ...] = Field(
        default=ALL_ENRICHMENT_DIMENSIONS, min_length=1, max_length=9
    )
    product_query_id: Literal["ollama", "vllm"] | None = None

    @field_validator("dimensions", mode="before")
    @classmethod
    def validate_selected_dimensions(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 9:
            raise ValueError("one to nine dimensions are required")
        if any(type(item) is not str or item not in ALL_ENRICHMENT_DIMENSIONS for item in value):
            raise ValueError("only registered dimensions are permitted")
        if len(set(value)) != len(value):
            raise ValueError("duplicate dimension selection")
        return tuple(dimension for dimension in ALL_ENRICHMENT_DIMENSIONS if dimension in value)

    @model_validator(mode="after")
    def validate_product_selection(self) -> "EventEnrichmentRequest":
        if self.product_query_id is not None and "exposure" not in self.dimensions:
            raise ValueError("product selection requires the exposure dimension")
        return self
