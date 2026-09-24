"""Canonical catalog for model-visible MCP tools and their server ownership."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Literal

from app.services.workbench.agent_tools import (
    RUNTIME_TOOL_POLICIES,
    allowed_curated_domains,
    visible_runtime_tool_names,
)


ToolOwner = Literal["workbench", "postgres"]


class ToolCatalogError(RuntimeError):
    """Canonical discovery or ownership is inconsistent."""


@dataclass(frozen=True, slots=True)
class CatalogTool:
    name: str
    owner: ToolOwner
    definition: dict[str, Any]


def _definition_name(definition: dict[str, Any]) -> str:
    try:
        name = definition["function"]["name"]
    except (KeyError, TypeError) as exc:
        raise ToolCatalogError("invalid provider tool definition") from exc
    if not isinstance(name, str) or not name:
        raise ToolCatalogError("provider tool definition has no name")
    return name


class ToolCatalog:
    """Cache canonical definitions only; filter a fresh copy for every request."""

    def __init__(self) -> None:
        self._entries: dict[str, CatalogTool] = {}
        self._local_ready = False
        self._postgres_ready = False
        self._postgres_error = "PostgreSQL MCP has not been discovered."

    def _replace_owner(
        self,
        owner: ToolOwner,
        definitions: list[dict[str, Any]],
    ) -> None:
        retained = {
            name: entry for name, entry in self._entries.items() if entry.owner != owner
        }
        incoming: dict[str, CatalogTool] = {}
        for definition in definitions:
            name = _definition_name(definition)
            if name in retained:
                other = retained[name].owner
                raise ToolCatalogError(
                    f"duplicate MCP tool name {name!r} owned by {other} and {owner}"
                )
            if name in incoming:
                raise ToolCatalogError(f"duplicate MCP tool name {name!r} from {owner}")
            incoming[name] = CatalogTool(name, owner, deepcopy(definition))
        self._entries = {**retained, **incoming}

    async def discover_local(self) -> list[str]:
        from app.mcp import workbench_client

        await workbench_client.discover_model_tools()
        definitions = workbench_client.canonical_model_definitions()
        discovered = {_definition_name(item) for item in definitions}
        classified = set(RUNTIME_TOOL_POLICIES)
        missing = sorted(discovered - classified)
        stale = sorted(classified - discovered)
        if missing or stale:
            details: list[str] = []
            if missing:
                details.append("missing runtime policy: " + ", ".join(missing))
            if stale:
                details.append("policy without MCP tool: " + ", ".join(stale))
            self._local_ready = False
            raise ToolCatalogError("Workbench MCP classification mismatch (" + "; ".join(details) + ")")
        self._replace_owner("workbench", definitions)
        self._local_ready = True
        return sorted(discovered)

    async def discover_postgres(self, *, check_health: bool = True) -> list[str]:
        from app.mcp import postgres_client

        try:
            if check_health:
                await postgres_client.initialize()
            else:
                await postgres_client.discover_model_tools()
            definitions = postgres_client.model_tool_definitions()
            self._replace_owner("postgres", definitions)
        except Exception as exc:
            self._entries = {
                name: entry
                for name, entry in self._entries.items()
                if entry.owner != "postgres"
            }
            self._postgres_ready = False
            self._postgres_error = str(exc)[:500]
            raise
        self._postgres_ready = True
        self._postgres_error = ""
        return sorted(_definition_name(item) for item in definitions)

    def register_postgres_definitions(
        self, definitions: list[dict[str, Any]]
    ) -> list[str]:
        """Register already-discovered canonical definitions without network I/O."""
        self._replace_owner("postgres", definitions)
        self._postgres_ready = bool(definitions)
        self._postgres_error = "" if definitions else "PostgreSQL MCP has no model tools."
        return sorted(_definition_name(item) for item in definitions)

    async def initialize(self) -> dict[str, Any]:
        await self.discover_local()
        try:
            await self.discover_postgres()
        except Exception:
            # PostgreSQL is a separately deployed dependency. Its degraded state is visible
            # and requests may retry discovery when it becomes ready.
            pass
        return self.readiness()

    async def model_tool_definitions(self, policy: Any) -> list[dict[str, Any]]:
        if not self._local_ready:
            await self.discover_local()
        allowed_local = set(visible_runtime_tool_names(policy))
        definitions: list[dict[str, Any]] = []
        for name in sorted(self._entries):
            entry = self._entries[name]
            if entry.owner == "postgres" and not policy.allows("db"):
                continue
            if entry.owner == "workbench" and name not in allowed_local:
                continue
            definition = deepcopy(entry.definition)
            if name == "search_curated_knowledge":
                definition["function"]["parameters"]["properties"]["domain"]["enum"] = (
                    allowed_curated_domains(policy)
                )
            definitions.append(definition)
        return definitions

    def owner(self, name: str) -> ToolOwner:
        try:
            return self._entries[name].owner
        except KeyError as exc:
            raise ToolCatalogError(f"unknown MCP tool {name!r}") from exc

    def is_postgres(self, name: str) -> bool:
        return self._entries.get(name, None) is not None and self._entries[name].owner == "postgres"

    def names(self, *, owner: ToolOwner | None = None) -> list[str]:
        return sorted(
            name
            for name, entry in self._entries.items()
            if owner is None or entry.owner == owner
        )

    def schema_fingerprint(self) -> str:
        payload = [
            {
                "owner": self._entries[name].owner,
                "definition": self._entries[name].definition,
            }
            for name in sorted(self._entries)
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest() if payload else ""

    def readiness(self) -> dict[str, Any]:
        from app.mcp import postgres_client, workbench_client

        owners = {
            owner: self.names(owner=owner) for owner in ("workbench", "postgres")
        }
        return {
            "status": (
                "ok" if self._local_ready and self._postgres_ready
                else "degraded" if self._local_ready
                else "unavailable"
            ),
            "owners": owners,
            "schema_fingerprint": self.schema_fingerprint(),
            "mcp_sdk_version": version("mcp"),
            "fastmcp_version": version("fastmcp"),
            "protocol_versions": {
                "workbench": workbench_client.readiness()["protocol_version"],
                "postgres": postgres_client.readiness()["protocol_version"],
            },
            "postgres_detail": self._postgres_error,
        }


catalog = ToolCatalog()


__all__ = ["CatalogTool", "ToolCatalog", "ToolCatalogError", "catalog"]
