"""GeoServer plan and publish orchestration."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from portolan_geoserver.client import GeoServerClientProtocol
from portolan_geoserver.model import (
    PlanAction,
    PlanEntry,
    PublishPlan,
    PublishResult,
    ResourceFormat,
    ServerCatalog,
    ServerResourceSpec,
)
from portolan_geoserver.planner import load_server_catalog


class GeoServerProvider:
    """GeoServer implementation for Portolan publication workflows."""

    def __init__(self, client: GeoServerClientProtocol, workspace: str | None = None) -> None:
        self._client = client
        self._workspace = workspace

    def plan(self, source: str | Path) -> PublishPlan:
        """Compute a read-only GeoServer publication plan."""
        return self.plan_catalog(load_server_catalog(source))

    def plan_catalog(self, catalog: ServerCatalog) -> PublishPlan:
        """Compute a read-only GeoServer publication plan for a loaded catalog."""
        workspace = self._workspace or catalog.catalog_id
        existing = self._client.list_portolan_resources(workspace)
        entries: list[PlanEntry] = []
        for candidate in catalog.candidates:
            if candidate.resource is None:
                entries.append(
                    PlanEntry(
                        collection=candidate.collection,
                        format=None,
                        action=PlanAction.SKIP,
                        reason=candidate.reason,
                    )
                )
                continue
            if candidate.resource.format not in {ResourceFormat.GEOPARQUET, ResourceFormat.COG}:
                entries.append(
                    PlanEntry(
                        collection=candidate.collection,
                        format=candidate.resource.format,
                        action=PlanAction.SKIP,
                        reason="unsupported by GeoServer provider",
                    )
                )
                continue
            action = _action_for_existing(candidate.resource, existing.get(candidate.collection))
            entries.append(
                PlanEntry(
                    collection=candidate.collection,
                    format=candidate.resource.format,
                    action=action,
                )
            )
        return PublishPlan(workspace=workspace, entries=entries)

    def publish(self, source: str | Path) -> PublishResult:
        """Publish GeoParquet and COG resources to GeoServer."""
        return self.publish_catalog(load_server_catalog(source))

    def publish_catalog(self, catalog: ServerCatalog) -> PublishResult:
        """Publish a loaded catalog to GeoServer."""
        workspace = self._workspace or catalog.catalog_id
        self._client.ensure_workspace(workspace)
        existing = self._client.list_portolan_resources(workspace)
        published = 0
        skipped = 0
        errors: list[str] = []
        for candidate in catalog.candidates:
            if candidate.resource is None:
                skipped += 1
                continue
            if candidate.resource.format not in {ResourceFormat.GEOPARQUET, ResourceFormat.COG}:
                skipped += 1
                continue
            if (
                _action_for_existing(candidate.resource, existing.get(candidate.collection))
                == PlanAction.EXISTS
            ):
                skipped += 1
                continue
            resource = _with_geoserver_name(
                _with_provenance(candidate.resource, catalog.catalog_href),
                geoserver_resource_name(candidate.resource.id),
            )
            try:
                if resource.format == ResourceFormat.GEOPARQUET:
                    self._client.publish_geoparquet(
                        workspace,
                        geoserver_resource_name(resource.id),
                        resource.href,
                        resource.metadata,
                        resource.primary_key,
                        resource.native_name,
                    )
                else:
                    self._client.publish_cog(
                        workspace,
                        geoserver_resource_name(resource.id),
                        resource.href,
                        resource.metadata,
                    )
                published += 1
            except Exception as exc:
                errors.append(f"{candidate.collection}: {exc}")
        return PublishResult(
            workspace=workspace,
            published=published,
            skipped=skipped,
            errors=errors,
        )

    def sync(self, source: str | Path) -> PublishResult:
        """Reconcile GeoServer with the current catalog without pruning."""
        return self.publish(source)


def geoserver_resource_name(collection_id: str) -> str:
    """Return a GeoServer-safe resource name for a STAC collection id."""
    name = collection_id.replace("/", "__")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._-")
    return name or "collection"


def _with_geoserver_name(resource: ServerResourceSpec, server_name: str) -> ServerResourceSpec:
    metadata = dict(resource.metadata)
    metadata["portolan.geoserver_name"] = server_name
    return replace(resource, metadata=metadata)


def _with_provenance(resource: ServerResourceSpec, catalog_href: str) -> ServerResourceSpec:
    metadata = dict(resource.metadata)
    metadata["title"] = resource.title
    metadata["description"] = resource.description
    metadata["portolan.managed"] = True
    metadata["portolan.catalog"] = catalog_href
    metadata["portolan.collection"] = resource.source_collection
    metadata["portolan.asset"] = resource.href
    metadata["portolan.primary_key"] = resource.primary_key
    metadata["portolan.native_name"] = resource.native_name
    checksum = metadata.get("file:checksum") or metadata.get("checksum:multihash")
    if checksum is not None:
        metadata["portolan.checksum"] = checksum
    return replace(resource, metadata=metadata)


def _action_for_existing(
    resource: ServerResourceSpec, existing_metadata: dict[str, object] | None
) -> PlanAction:
    if existing_metadata is None:
        return PlanAction.CREATE
    if existing_metadata.get("portolan.asset") != resource.href:
        return PlanAction.UPDATE
    if (
        resource.primary_key is not None
        and existing_metadata.get("portolan.primary_key") != resource.primary_key
    ):
        return PlanAction.UPDATE
    checksum = resource.metadata.get("file:checksum") or resource.metadata.get("checksum:multihash")
    if checksum is not None and existing_metadata.get("portolan.checksum") != checksum:
        return PlanAction.UPDATE
    return PlanAction.EXISTS
