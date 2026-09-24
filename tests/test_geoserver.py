"""GeoServer publication tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from portolan import RegistryCatalogEntry

from portolan_geoserver import (
    GeoServerProvider,
    PlanAction,
    ResourceFormat,
    ResourceType,
    discover_server_resources,
)
from portolan_geoserver import cli as cli_module
from portolan_geoserver.cli import main
from portolan_geoserver.client import (
    GeoServerClient,
    coverage_store_names,
    metadata_entries,
    metadata_payload,
)
from portolan_geoserver.plugin import get_portolan_cli_plugin
from portolan_geoserver.provider import geoserver_resource_name

pytestmark = pytest.mark.unit


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _base_extent() -> dict[str, Any]:
    return {
        "spatial": {"bbox": [[-71.0, -35.0, -70.0, -34.0]]},
        "temporal": {"interval": [[None, None]]},
    }


def _collection(
    collection_id: str,
    asset: dict[str, Any],
    *,
    title: str | None = None,
    spatial: bool = True,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "Collection",
        "stac_version": "1.1.0",
        "id": collection_id,
        "description": f"{collection_id} description",
        "license": "CC-BY-4.0",
        "extent": _base_extent(),
        "links": [],
        "assets": {"data": asset},
        "keywords": ["portolan", collection_id],
        "summaries": {"proj:epsg": [4326]},
    }
    if spatial:
        data["table:primary_geometry"] = "geometry"
    if title:
        data["title"] = title
    return data


def _catalog(root: Path) -> None:
    _write_json(
        root / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "demo-catalog",
            "description": "Demo catalog",
            "links": [
                {"rel": "child", "href": "./roads/collection.json"},
                {"rel": "child", "href": "./elevation/collection.json"},
                {"rel": "child", "href": "./basemap/collection.json"},
                {"rel": "child", "href": "./notes/collection.json"},
                {"rel": "child", "href": "./table/collection.json"},
            ],
        },
    )
    _write_json(
        root / "roads" / "collection.json",
        _collection(
            "roads",
            {
                "href": "https://example.test/roads.parquet",
                "type": "application/vnd.apache.parquet",
                "roles": ["data"],
                "file:checksum": "sha256:roads",
            },
            title="Roads",
        ),
    )
    _write_json(
        root / "elevation" / "collection.json",
        _collection(
            "elevation",
            {
                "href": "https://example.test/elevation.tif",
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data"],
            },
        ),
    )
    _write_json(
        root / "basemap" / "collection.json",
        _collection(
            "basemap",
            {
                "href": "https://example.test/basemap.pmtiles",
                "type": "application/vnd.pmtiles",
                "roles": ["data"],
            },
        ),
    )
    _write_json(
        root / "notes" / "collection.json",
        _collection(
            "notes",
            {
                "href": "https://example.test/notes.txt",
                "type": "text/plain",
                "roles": ["data"],
            },
        ),
    )
    _write_json(
        root / "table" / "collection.json",
        _collection(
            "table",
            {
                "href": "https://example.test/table.parquet",
                "type": "application/vnd.apache.parquet",
                "roles": ["data"],
            },
            spatial=False,
        ),
    )


def _catalog_without_id(root: Path) -> None:
    _write_json(
        root / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "description": "Demo catalog",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
    )
    _write_json(
        root / "roads" / "collection.json",
        _collection(
            "roads",
            {
                "href": "./roads.parquet",
                "media_type": "application/vnd.apache.parquet",
                "roles": ["metadata"],
            },
        ),
    )


class RecordingGeoServerClient:
    """Small fake for provider tests."""

    def __init__(self, existing: dict[str, dict[str, Any]] | None = None) -> None:
        self.existing = existing or {}
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def list_portolan_resources(self, workspace: str) -> dict[str, dict[str, Any]]:
        self.calls.append(("list_portolan_resources", (workspace,)))
        return self.existing

    def ensure_workspace(self, workspace: str) -> None:
        self.calls.append(("ensure_workspace", (workspace,)))

    def publish_geoparquet(
        self,
        workspace: str,
        name: str,
        href: str,
        metadata: dict[str, object],
        primary_key: str | None = None,
        native_name: str | None = None,
    ) -> None:
        self.calls.append(
            ("publish_geoparquet", (workspace, name, href, metadata, primary_key, native_name))
        )

    def publish_cog(
        self, workspace: str, name: str, href: str, metadata: dict[str, object]
    ) -> None:
        self.calls.append(("publish_cog", (workspace, name, href, metadata)))


def test_discovers_publishable_resources(tmp_path: Path) -> None:
    _catalog(tmp_path)

    resources = discover_server_resources(tmp_path)

    assert [(r.id, r.resource_type, r.format) for r in resources] == [
        ("roads", ResourceType.VECTOR, ResourceFormat.GEOPARQUET),
        ("elevation", ResourceType.RASTER, ResourceFormat.COG),
        ("basemap", ResourceType.TILES, ResourceFormat.PMTILES),
    ]
    assert resources[0].href == "https://example.test/roads.parquet"
    assert resources[0].metadata["file:checksum"] == "sha256:roads"
    assert resources[0].crs == "EPSG:4326"
    assert resources[0].native_name == "roads"


def test_discovers_local_assets_and_catalog_id_fallback(tmp_path: Path) -> None:
    _catalog_without_id(tmp_path)

    resources = discover_server_resources(tmp_path)

    assert len(resources) == 1
    assert resources[0].href == (tmp_path / "roads" / "roads.parquet").as_uri()
    assert resources[0].metadata["roles"] == ["metadata"]


def test_geoserver_plan_marks_create_exists_and_skips(tmp_path: Path) -> None:
    _catalog(tmp_path)
    client = RecordingGeoServerClient(
        existing={
            "roads": {
                "portolan.asset": "https://example.test/roads.parquet",
                "portolan.checksum": "sha256:roads",
            }
        }
    )
    provider = GeoServerProvider(client=client, workspace="portolan")

    plan = provider.plan(tmp_path)

    entries = [
        (entry.collection, entry.format, entry.action, entry.reason)
        for entry in plan.entries
    ]
    assert entries == [
        ("roads", ResourceFormat.GEOPARQUET, PlanAction.EXISTS, None),
        ("elevation", ResourceFormat.COG, PlanAction.CREATE, None),
        ("basemap", ResourceFormat.PMTILES, PlanAction.SKIP, "unsupported by GeoServer provider"),
        ("notes", None, PlanAction.SKIP, "unsupported media type: text/plain"),
        ("table", None, PlanAction.SKIP, "non-spatial Parquet asset"),
    ]
    assert plan.counts() == {"EXISTS": 1, "CREATE": 1, "SKIP": 3}


def test_geoserver_plan_marks_changed_asset_as_update(tmp_path: Path) -> None:
    _catalog(tmp_path)
    provider = GeoServerProvider(
        client=RecordingGeoServerClient(existing={"roads": {"portolan.asset": "old.parquet"}}),
        workspace="portolan",
    )

    plan = provider.plan(tmp_path)

    assert plan.entries[0].action == PlanAction.UPDATE


def test_geoserver_plan_marks_changed_primary_key_and_checksum_as_update(
    tmp_path: Path,
) -> None:
    _catalog(tmp_path)
    collection = json.loads((tmp_path / "roads" / "collection.json").read_text(encoding="utf-8"))
    collection["table:columns"] = [{"name": "objectid"}, {"name": "geometry"}]
    _write_json(tmp_path / "roads" / "collection.json", collection)
    provider = GeoServerProvider(
        client=RecordingGeoServerClient(
            existing={
                "roads": {
                    "portolan.asset": "https://example.test/roads.parquet",
                    "portolan.primary_key": "old_id",
                    "portolan.checksum": "old-checksum",
                }
            }
        ),
        workspace="portolan",
    )

    plan = provider.plan(tmp_path)

    assert plan.entries[0].action == PlanAction.UPDATE


def test_geoserver_publish_sends_provenance_and_safe_names(tmp_path: Path) -> None:
    _catalog(tmp_path)
    collection = json.loads((tmp_path / "roads" / "collection.json").read_text(encoding="utf-8"))
    collection["id"] = "transport/roads"
    _write_json(tmp_path / "roads" / "collection.json", collection)
    client = RecordingGeoServerClient()
    provider = GeoServerProvider(client=client, workspace="portolan")

    result = provider.publish(tmp_path)

    assert result.published == 2
    assert result.skipped == 3
    publish_calls = [call for call in client.calls if call[0].startswith("publish_")]
    assert [call[0] for call in publish_calls] == ["publish_geoparquet", "publish_cog"]
    metadata = publish_calls[0][1][3]
    assert publish_calls[0][1][1] == "transport__roads"
    assert metadata["portolan.managed"] is True
    assert metadata["portolan.catalog"] == (tmp_path / "catalog.json").as_uri()
    assert metadata["portolan.collection"] == "transport/roads"
    assert metadata["portolan.asset"] == "https://example.test/roads.parquet"
    assert metadata["portolan.checksum"] == "sha256:roads"
    assert metadata["portolan.geoserver_name"] == "transport__roads"


def test_geoserver_publish_skips_existing_resources(tmp_path: Path) -> None:
    _catalog(tmp_path)
    client = RecordingGeoServerClient(
        existing={
            "roads": {
                "portolan.asset": "https://example.test/roads.parquet",
                "portolan.checksum": "sha256:roads",
            },
            "elevation": {"portolan.asset": "https://example.test/elevation.tif"},
        }
    )
    provider = GeoServerProvider(client=client, workspace="portolan")

    result = provider.sync(tmp_path)

    assert result.published == 0
    assert result.skipped == 5


def test_cli_plan_supports_offline_text_and_json(tmp_path: Path) -> None:
    _catalog(tmp_path)

    text = CliRunner().invoke(main, ["plan", str(tmp_path), "--offline"])
    as_json = CliRunner().invoke(main, ["plan", str(tmp_path), "--offline", "--json"])

    assert text.exit_code == 0, text.output
    assert "Workspace: demo-catalog" in text.output
    assert "roads" in text.output
    payload = json.loads(as_json.output)
    assert payload["workspace"] == "demo-catalog"
    assert payload["counts"]["CREATE"] == 2


def test_cli_publish_uses_env_credentials_and_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _catalog(tmp_path)
    fake_client = RecordingGeoServerClient()
    monkeypatch.setenv("PORTOLAN_GEOSERVER_URL", "http://geoserver.test/geoserver")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_USER", "admin")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_PASSWORD", "secret")
    monkeypatch.setattr(cli_module, "GeoServerClient", lambda *args, **kwargs: fake_client)

    result = CliRunner().invoke(
        main,
        ["publish", str(tmp_path), "--workspace", "demo", "--json", "--no-verify-tls"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["workspace"] == "demo"
    assert payload["published"] == 2
    assert "secret" not in result.output


def test_cli_serve_publishes_registry_catalogs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _catalog(tmp_path / "downloaded")
    fake_client = RecordingGeoServerClient()
    monkeypatch.setenv("PORTOLAN_GEOSERVER_URL", "http://geoserver.test/geoserver")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_USER", "admin")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_PASSWORD", "secret")
    monkeypatch.setattr(cli_module, "GeoServerClient", lambda *args, **kwargs: fake_client)
    monkeypatch.setattr(
        cli_module,
        "load_registry_entries",
        lambda *args, **kwargs: [
            RegistryCatalogEntry(
                id="demo",
                url="https://registry.test/demo/catalog.json",
                title="Demo",
                status="valid",
            )
        ],
    )
    monkeypatch.setattr(
        cli_module,
        "download_registry_catalog",
        lambda catalog_url, output_dir: tmp_path / "downloaded",
    )

    result = CliRunner().invoke(
        main,
        [
            "serve",
            "--catalog-id",
            "demo",
            "--registry",
            "https://registry.test/catalogs.json",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--workspace",
            "registry-workspace",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["registry_url"] == "https://registry.test/catalogs.json"
    assert payload["catalogs"][0]["id"] == "demo"
    assert payload["catalogs"][0]["local_path"] == str(tmp_path / "downloaded")
    assert payload["catalogs"][0]["result"]["published"] == 2


def test_cli_serve_reports_missing_registry_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTOLAN_GEOSERVER_URL", "http://geoserver.test/geoserver")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_USER", "admin")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_PASSWORD", "secret")
    monkeypatch.setattr(
        cli_module,
        "GeoServerClient",
        lambda *args, **kwargs: RecordingGeoServerClient(),
    )
    monkeypatch.setattr(cli_module, "load_registry_entries", lambda *args, **kwargs: [])

    result = CliRunner().invoke(
        main,
        ["serve", "--catalog-id", "missing", "--cache-dir", str(tmp_path), "--json"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["errors"] == ["catalog not found in registry: missing"]


def test_cli_serve_validates_selection_options(tmp_path: Path) -> None:
    both = CliRunner().invoke(
        main,
        ["serve", "--all", "--catalog-id", "demo", "--cache-dir", str(tmp_path)],
    )
    neither = CliRunner().invoke(main, ["serve", "--cache-dir", str(tmp_path)])

    assert both.exit_code != 0
    assert "Use either --all or --catalog-id" in both.output
    assert neither.exit_code != 0
    assert "Use --catalog-id or --all" in neither.output


def test_cli_sync_returns_error_exit_for_publish_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _catalog(tmp_path)

    class FailingClient(RecordingGeoServerClient):
        def publish_geoparquet(
            self,
            workspace: str,
            name: str,
            href: str,
            metadata: dict[str, object],
            primary_key: str | None = None,
            native_name: str | None = None,
        ) -> None:
            raise RuntimeError("boom")

    monkeypatch.setenv("PORTOLAN_GEOSERVER_URL", "http://geoserver.test/geoserver")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_USER", "admin")
    monkeypatch.setenv("PORTOLAN_GEOSERVER_PASSWORD", "secret")
    monkeypatch.setattr(cli_module, "GeoServerClient", lambda *args, **kwargs: FailingClient())

    result = CliRunner().invoke(main, ["sync", str(tmp_path)])

    assert result.exit_code == 1
    assert "Error: roads: boom" in result.output


def test_cli_publish_requires_connection_options(tmp_path: Path) -> None:
    _catalog(tmp_path)

    result = CliRunner().invoke(main, ["publish", str(tmp_path)])

    assert result.exit_code != 0
    assert "Missing GeoServer connection option" in result.output


def test_plugin_descriptor_exposes_click_group() -> None:
    plugin = get_portolan_cli_plugin()

    assert plugin.name == "geoserver"
    assert plugin.command_path == ("geoserver",)
    assert "export" in plugin.capabilities
    assert plugin.command.name == "main"


def test_geoserver_resource_name_sanitizes_collection_ids() -> None:
    assert geoserver_resource_name("medio-ambiente/meteorologicos diarios") == (
        "medio-ambiente__meteorologicos_diarios"
    )
    assert geoserver_resource_name("...") == "collection"


def test_metadata_and_coverage_helpers_handle_payload_variants() -> None:
    assert metadata_payload({"portolan.managed": True}) == {
        "entry": [{"@key": "portolan.managed", "$": "true"}]
    }
    assert metadata_entries({"entry": {"portolan.managed": "true"}}) == {
        "portolan.managed": "true"
    }
    assert metadata_entries({"entry": [{"@key": "portolan.collection", "$": "roads"}]}) == {
        "portolan.collection": "roads"
    }
    assert coverage_store_names({"coverageStores": {"coverageStore": {"name": "elevation"}}}) == [
        "elevation"
    ]
    assert coverage_store_names({"coverageStores": ""}) == []


class RaisingRestClient:
    def get(self, path: str) -> Any:
        raise RuntimeError(path)


class RestEndpoints:
    def featuretype(self, workspace: str, datastore: str, name: str) -> str:
        return f"/{workspace}/{datastore}/{name}"

    def coveragestores(self, workspace: str) -> str:
        return f"/{workspace}/coveragestores"


class RestService:
    rest_client = RaisingRestClient()
    rest_endpoints = RestEndpoints()


class BrokenGeoServerApi:
    rest_service = RestService()

    def get_datastores(self, workspace: str) -> tuple[list[dict[str, str]], int]:
        return ([{"name": "broken"}], 200)


def test_geoserver_client_ignores_unreadable_existing_feature_types() -> None:
    client = GeoServerClient.__new__(GeoServerClient)
    client._client = BrokenGeoServerApi()
    client._coverage_stores = lambda workspace: ([], 404)  # type: ignore[method-assign]

    assert client.list_portolan_resources("workspace") == {}


class Response:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class RecordingRestClient:
    def __init__(self) -> None:
        self.puts: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str) -> Response:
        if path.endswith("coveragestores"):
            return Response({"coverageStores": {"coverageStore": [{"name": "elevation"}]}})
        return Response(
            {
                "featureType": {
                    "metadata": {
                        "entry": [
                            {"@key": "portolan.managed", "$": "true"},
                            {"@key": "portolan.collection", "$": "roads"},
                        ]
                    }
                }
            }
        )

    def put(self, path: str, json: dict[str, Any]) -> Response:
        self.puts.append((path, json))
        return Response({}, 200)


class FullRestEndpoints:
    def featuretype(self, workspace: str, datastore: str, name: str) -> str:
        return f"/{workspace}/datastores/{datastore}/featuretypes/{name}"

    def coveragestores(self, workspace: str) -> str:
        return f"/{workspace}/coveragestores"

    def coverage(self, workspace: str, coverage_store: str, name: str) -> str:
        return f"/{workspace}/coveragestores/{coverage_store}/coverages/{name}"


class FullRestService:
    def __init__(self) -> None:
        self.rest_client = RecordingRestClient()
        self.rest_endpoints = FullRestEndpoints()


class RecordingGeoServerApi:
    def __init__(self) -> None:
        self.rest_service = FullRestService()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_datastores(self, workspace: str) -> tuple[list[dict[str, str]], int]:
        return ([{"name": "roads"}], 200)

    def get_coverage(
        self, workspace: str, coverage_store: str, coverage: str
    ) -> tuple[dict[str, Any], int]:
        return (
            {
                "metadata": {
                    "entry": [
                        {"@key": "portolan.managed", "$": "true"},
                        {"@key": "portolan.collection", "$": "elevation"},
                    ]
                }
            },
            200,
        )

    def create_workspace(self, workspace: str) -> tuple[str, int]:
        self.calls.append(("create_workspace", {"workspace": workspace}))
        return ("", 201)

    def create_datastore(self, **kwargs: Any) -> tuple[str, int]:
        self.calls.append(("create_datastore", kwargs))
        return ("", 201)

    def create_feature_type(self, **kwargs: Any) -> tuple[str, int]:
        self.calls.append(("create_feature_type", kwargs))
        return ("", 201)

    def create_coverage_store(self, **kwargs: Any) -> tuple[str, int]:
        self.calls.append(("create_coverage_store", kwargs))
        return ("", 201)

    def create_coverage(self, **kwargs: Any) -> tuple[str, int]:
        self.calls.append(("create_coverage", kwargs))
        return ("", 201)


def test_geoserver_client_reads_and_writes_resources() -> None:
    api = RecordingGeoServerApi()
    client = GeoServerClient.__new__(GeoServerClient)
    client._client = api

    existing = client.list_portolan_resources("portolan")
    client.ensure_workspace("portolan")
    client.publish_geoparquet(
        "portolan",
        "roads",
        "https://example.test/roads.parquet",
        {"title": "Roads", "description": "Roads", "keywords": ["roads"]},
        primary_key="objectid",
        native_name="roads_native",
    )
    client.publish_cog(
        "portolan",
        "elevation",
        "https://example.test/elevation.tif",
        {"title": "Elevation"},
    )

    assert existing == {
        "roads": {"portolan.managed": "true", "portolan.collection": "roads"},
        "elevation": {"portolan.managed": "true", "portolan.collection": "elevation"},
    }
    assert [call[0] for call in api.calls] == [
        "create_workspace",
        "create_datastore",
        "create_feature_type",
        "create_coverage_store",
        "create_coverage",
    ]
    datastore = api.calls[1][1]
    assert datastore["connection_parameters"]["primary_key_id"] == "objectid"
    assert datastore["connection_parameters"]["uri"] == "https://example.test/roads.parquet"
    assert len(api.rest_service.rest_client.puts) == 2


def test_geoserver_client_raises_on_failed_rest_operation() -> None:
    client = GeoServerClient.__new__(GeoServerClient)

    with pytest.raises(RuntimeError, match="failed with HTTP 500"):
        client._raise_on_error("create workspace", ("broken", 500))
