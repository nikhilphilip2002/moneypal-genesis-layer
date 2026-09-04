"""One immutable source-access decision for a submitted Workbench request."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.config import settings
from app.services.workbench.sources import SOURCES


class SourceGroup(str, Enum):
    INTERNAL_DATA = "internal_data"
    INTERNAL_METADATA = "internal_metadata"
    LOCAL_KNOWLEDGE = "local_knowledge"
    EXTERNAL_INDEXED = "external_indexed"
    LIVE_EXTERNAL = "live_external"


SOURCE_GROUPS: dict[str, SourceGroup] = {
    "db": SourceGroup.INTERNAL_DATA,
    "schema": SourceGroup.INTERNAL_METADATA,
    "knowledge": SourceGroup.LOCAL_KNOWLEDGE,
    "macro": SourceGroup.EXTERNAL_INDEXED,
    "competitive": SourceGroup.EXTERNAL_INDEXED,
    "regulatory": SourceGroup.EXTERNAL_INDEXED,
    "web": SourceGroup.LIVE_EXTERNAL,
}
EXTERNAL_GROUPS = frozenset({SourceGroup.EXTERNAL_INDEXED, SourceGroup.LIVE_EXTERNAL})
POLICY_VERSION = "source-access-v1"


class SourceAccessDenied(PermissionError):
    pass


def source_group(source_id: str) -> SourceGroup:
    try:
        return SOURCE_GROUPS[source_id]
    except KeyError as exc:
        raise SourceAccessDenied(f"Unknown source: {source_id}") from exc


def is_external(source_id: str) -> bool:
    return source_group(source_id) in EXTERNAL_GROUPS


@dataclass(frozen=True, slots=True)
class SourceAccessPolicy:
    """Consent ∩ role ∩ deployment availability, frozen for one request."""

    role: str
    external_sources_enabled: bool
    deployment_external_connectors_enabled: bool
    role_sources: tuple[str, ...]
    deployment_sources: tuple[str, ...]
    effective_sources: tuple[str, ...]
    version: str = POLICY_VERSION

    def allows(self, source_id: str) -> bool:
        return source_id in self.effective_sources

    def require(self, source_id: str) -> None:
        if not self.allows(source_id):
            reason = "external source consent is required" if is_external(source_id) else "source is unavailable"
            raise SourceAccessDenied(f"{source_id}: {reason}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "external_sources_enabled": self.external_sources_enabled,
            "deployment_external_connectors_enabled": self.deployment_external_connectors_enabled,
            "effective_sources": list(self.effective_sources),
        }


def build_policy(
    *, role: str, external_sources_enabled: bool = False,
) -> SourceAccessPolicy:
    ordered_ids = tuple(SOURCES)
    role_sources = tuple(source_id for source_id in ordered_ids if SOURCES[source_id].visible_to(role))
    deployment_sources = tuple(
        source_id
        for source_id in ordered_ids
        if (
            not is_external(source_id)
            or settings.workbench_external_connectors_enabled
        )
        and (source_id != "web" or settings.exa_mcp_enabled)
    )
    effective_sources = tuple(
        source_id
        for source_id in ordered_ids
        if source_id in role_sources
        and source_id in deployment_sources
        and (external_sources_enabled or not is_external(source_id))
    )
    return SourceAccessPolicy(
        role=role,
        external_sources_enabled=bool(external_sources_enabled),
        deployment_external_connectors_enabled=settings.workbench_external_connectors_enabled,
        role_sources=role_sources,
        deployment_sources=deployment_sources,
        effective_sources=effective_sources,
    )


def source_metadata(role: str) -> list[dict[str, Any]]:
    """Describe role-visible sources without treating consent as deployment availability."""
    policy = build_policy(role=role, external_sources_enabled=True)
    metadata: list[dict[str, Any]] = []
    for source_id in policy.role_sources:
        source = SOURCES[source_id]
        group = source_group(source_id)
        metadata.append({
            "id": source.id,
            "label": source.label,
            "describes": source.describes,
            "sensitive": source.sensitive,
            "group": group.value,
            "requires_external_consent": group in EXTERNAL_GROUPS,
            "deployment_available": source_id in policy.deployment_sources,
        })
    return metadata


__all__ = [
    "EXTERNAL_GROUPS",
    "POLICY_VERSION",
    "SOURCE_GROUPS",
    "SourceAccessDenied",
    "SourceAccessPolicy",
    "SourceGroup",
    "build_policy",
    "is_external",
    "source_group",
    "source_metadata",
]
