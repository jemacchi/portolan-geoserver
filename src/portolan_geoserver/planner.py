"""Discover GeoServer publication candidates from Portolan catalogs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from portolan import Asset, AssetFormat, Catalog, Collection

from portolan_geoserver.model import (
    CollectionCandidate,
    ResourceFormat,
    ResourceType,
    ServerCatalog,
    ServerResourceSpec,
)


def load_server_catalog(source: str | Path) -> ServerCatalog:
    """Load a Portolan catalog into GeoServer publication candidates."""
    catalog = Catalog.open(source)
    catalog_id = catalog.id or _fallback_catalog_id(catalog.href)
    candidates = [
        _collection_candidate(catalog, collection)
        for collection in catalog.collections()
    ]
    return ServerCatalog(
        catalog_id=catalog_id,
        catalog_href=catalog.href,
        candidates=candidates,
    )


def discover_server_resources(source: str | Path) -> list[ServerResourceSpec]:
    """Return all resources that the GeoServer provider can publish."""
    return [
        candidate.resource
        for candidate in load_server_catalog(source).candidates
        if candidate.resource is not None
    ]


def _collection_candidate(catalog: Catalog, collection: Collection) -> CollectionCandidate:
    collection_id = collection.id
    asset = _primary_asset(collection)
    if asset is None:
        return CollectionCandidate(collection=collection_id, resource=None, reason="no data asset")

    if asset.format is AssetFormat.GEOPARQUET and not _has_geometry(collection.data):
        return CollectionCandidate(
            collection=collection_id,
            resource=None,
            reason="non-spatial Parquet asset",
        )

    resource_type, resource_format = _classify_asset(asset)
    if resource_type is None or resource_format is None:
        return CollectionCandidate(
            collection=collection_id,
            resource=None,
            reason=f"unsupported media type: {asset.media_type or 'unknown'}",
        )

    collection_data = collection.data
    metadata = _resource_metadata(collection_data, asset)
    return CollectionCandidate(
        collection=collection_id,
        resource=ServerResourceSpec(
            id=collection_id,
            resource_type=resource_type,
            format=resource_format,
            href=asset.href,
            title=_string_or_none(collection_data.get("title")),
            description=_string_or_none(collection_data.get("description")),
            extent=collection_data.get("extent")
            if isinstance(collection_data.get("extent"), dict)
            else None,
            crs=_crs(collection_data),
            primary_key=_primary_key(collection_data),
            native_name=_native_name(asset, resource_format),
            metadata=metadata,
            source_catalog=catalog.href,
            source_collection=collection_id,
            source_asset=asset.key,
        ),
    )


def _primary_asset(collection: Collection) -> Asset | None:
    assets = list(collection.assets())
    if not assets:
        return None
    for asset in assets:
        if "data" in asset.roles:
            return asset
    return assets[0]


def _classify_asset(asset: Asset) -> tuple[ResourceType | None, ResourceFormat | None]:
    if asset.format is AssetFormat.GEOPARQUET:
        return ResourceType.VECTOR, ResourceFormat.GEOPARQUET
    if asset.format is AssetFormat.COG:
        return ResourceType.RASTER, ResourceFormat.COG
    if asset.format is AssetFormat.PMTILES:
        return ResourceType.TILES, ResourceFormat.PMTILES
    return None, None


def _native_name(asset: Asset, resource_format: ResourceFormat) -> str | None:
    if resource_format is ResourceFormat.GEOPARQUET:
        stem = Path(urlparse(asset.href).path).stem
        if stem:
            return stem
    return asset.key


def _has_geometry(collection: dict[str, Any]) -> bool:
    if isinstance(collection.get("table:primary_geometry"), str):
        return True
    if collection.get("geoparquet:geometry_type") is not None:
        return True
    columns = collection.get("table:columns")
    if not isinstance(columns, list):
        return False
    for column in columns:
        if not isinstance(column, dict):
            continue
        if column.get("name") in {"geom", "geometry", "the_geom"}:
            return True
    return False


def _resource_metadata(collection: dict[str, Any], asset: Asset) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in ("license", "providers", "keywords", "summaries"):
        value = collection.get(key)
        if value is not None:
            metadata[key] = value
    for key in ("file:checksum", "checksum:multihash", "type", "roles"):
        value = asset.raw.get(key)
        if value is not None:
            metadata[key] = value
    return metadata


def _crs(collection: dict[str, Any]) -> str | None:
    summaries = collection.get("summaries")
    if not isinstance(summaries, dict):
        return None
    epsg = summaries.get("proj:epsg")
    if isinstance(epsg, list) and epsg:
        return f"EPSG:{epsg[0]}"
    if isinstance(epsg, int):
        return f"EPSG:{epsg}"
    return None


def _primary_key(collection: dict[str, Any]) -> str | None:
    columns = collection.get("table:columns")
    if not isinstance(columns, list):
        return None
    names: list[str] = []
    for column in columns:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        if isinstance(name, str):
            names.append(name)
    lowered = {name.lower(): name for name in names}
    for candidate in ("id", "objectid", "_id", "fid", "ogc_fid", "gid"):
        match = lowered.get(candidate)
        if match is not None:
            return match
    return None


def _fallback_catalog_id(href: str) -> str:
    parent = Path(urlparse(href).path).parent.name
    return parent or "portolan"


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None
