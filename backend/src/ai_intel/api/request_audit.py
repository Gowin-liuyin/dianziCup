"""Record rejected self-reported identity field names through the existing auth audit port."""

from collections.abc import Iterable

from ai_intel.api.authentication import AuthenticationSessionService

REJECTED_IDENTITY_FIELDS = frozenset({"tenant_id", "user_id", "role", "permissions"})


def record_rejected_identity_fields(
    authentication: AuthenticationSessionService | None, submitted_fields: Iterable[str]
) -> None:
    fields = REJECTED_IDENTITY_FIELDS.intersection(submitted_fields)
    if authentication is not None and fields:
        authentication.record_identity_spoof_attempt(dict.fromkeys(fields, ""))
