"""Publication model for Portolan to GeoServer workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ResourceType(Enum):
    """Generic server resource type."""

    VECTOR = "VECTOR"
    RASTER = "RASTER"
    TILES = "TILES"


class ResourceFormat(Enum):
    """Cloud-native resource formats that Portolan can expose."""

    GEOPARQUET = "GeoParquet"
    COG = "COG"
    PMTILES = "PMTiles"


class PlanAction(Enum):
    """Action needed to align GeoServer with a Portolan catalog."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    EXISTS = "EXISTS"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ServerResourceSpec:
    """Provider-independent desired state for one GeoServer resource."""

    id: str
    resource_type: ResourceType
    format: ResourceFormat
    href: str
    title: str | None
    description: str | None
    extent: dict[str, Any] | None
    crs: str | None
    primary_key: str | None
    native_name: str | None
    metadata: dict[str, object]
    source_catalog: str
    source_collection: str
    source_asset: str


@dataclass(frozen=True)
class CollectionCandidate:
    """A collection plus the resource it can publish, if any."""

    collection: str
    resource: ServerResourceSpec | None
    reason: str | None = None


@dataclass(frozen=True)
class PlanEntry:
    """One line in a GeoServer publication plan."""

    collection: str
    format: ResourceFormat | None
    action: PlanAction
    reason: str | None = None


@dataclass(frozen=True)
class PublishPlan:
    """Read-only plan for a GeoServer publication run."""

    workspace: str
    entries: list[PlanEntry]

    def counts(self) -> dict[str, int]:
        """Return action counts keyed by display value."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            counts[entry.action.value] = counts.get(entry.action.value, 0) + 1
        return counts


@dataclass(frozen=True)
class PublishResult:
    """Result from applying a publication plan."""

    workspace: str
    published: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServedCatalog:
    """One registry catalog processed by the serve command."""

    id: str
    url: str
    title: str | None
    status: str | None
    local_path: Path
    result: PublishResult


@dataclass(frozen=True)
class ServeResult:
    """Result from serving one or more registry catalogs."""

    registry_url: str
    catalogs: list[ServedCatalog]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServerCatalog:
    """Loaded Portolan catalog data needed by the GeoServer provider."""

    catalog_id: str
    catalog_href: str
    candidates: list[CollectionCandidate]
