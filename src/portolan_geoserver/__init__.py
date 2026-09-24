"""GeoServer integration for Portolan catalogs."""

from portolan_geoserver.model import (
    CollectionCandidate,
    PlanAction,
    PlanEntry,
    PublishPlan,
    PublishResult,
    ResourceFormat,
    ResourceType,
    ServerCatalog,
    ServerResourceSpec,
)
from portolan_geoserver.planner import discover_server_resources, load_server_catalog
from portolan_geoserver.provider import GeoServerProvider

__all__ = [
    "CollectionCandidate",
    "GeoServerProvider",
    "PlanAction",
    "PlanEntry",
    "PublishPlan",
    "PublishResult",
    "ResourceFormat",
    "ResourceType",
    "ServerCatalog",
    "ServerResourceSpec",
    "discover_server_resources",
    "load_server_catalog",
]
