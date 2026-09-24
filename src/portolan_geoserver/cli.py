"""Standalone CLI for publishing Portolan catalogs to GeoServer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click
from portolan import (
    DEFAULT_REGISTRY_URL,
    download_registry_catalog,
    load_registry_entries,
)

from portolan_geoserver.client import EmptyGeoServerClient, GeoServerClient
from portolan_geoserver.model import PublishPlan, PublishResult, ServedCatalog, ServeResult
from portolan_geoserver.provider import GeoServerProvider


@click.group()
def main() -> None:
    """Publish Portolan catalogs to GeoServer."""


@main.command("plan")
@click.argument("catalog", type=click.Path(path_type=Path))
@click.option("--url", default=None, help="GeoServer REST base URL.")
@click.option("--user", default=None, help="GeoServer REST user.")
@click.option("--password", default=None, help="GeoServer REST password.")
@click.option("--workspace", default=None, help="GeoServer workspace name.")
@click.option("--offline", is_flag=True, help="Do not read existing GeoServer resources.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--verify-tls/--no-verify-tls", default=True, help="Verify GeoServer TLS.")
def plan_cmd(
    catalog: Path,
    url: str | None,
    user: str | None,
    password: str | None,
    workspace: str | None,
    offline: bool,
    json_output: bool,
    verify_tls: bool,
) -> None:
    """Show GeoServer resources that would be created or updated."""
    provider = _provider(url, user, password, workspace, offline=offline, verify_tls=verify_tls)
    plan = provider.plan(catalog)
    if json_output:
        click.echo(json.dumps(_plan_json(plan), indent=2))
    else:
        render_plan(plan)


@main.command("publish")
@click.argument("catalog", type=click.Path(path_type=Path))
@click.option("--url", default=None, help="GeoServer REST base URL.")
@click.option("--user", default=None, help="GeoServer REST user.")
@click.option("--password", default=None, help="GeoServer REST password.")
@click.option("--workspace", default=None, help="GeoServer workspace name.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--verify-tls/--no-verify-tls", default=True, help="Verify GeoServer TLS.")
def publish_cmd(
    catalog: Path,
    url: str | None,
    user: str | None,
    password: str | None,
    workspace: str | None,
    json_output: bool,
    verify_tls: bool,
) -> None:
    """Publish GeoParquet and COG resources to GeoServer."""
    result = _provider(url, user, password, workspace, verify_tls=verify_tls).publish(catalog)
    if json_output:
        click.echo(json.dumps(_result_json(result), indent=2))
    else:
        render_result(result)
    if result.errors:
        raise SystemExit(1)


@main.command("sync")
@click.argument("catalog", type=click.Path(path_type=Path))
@click.option("--url", default=None, help="GeoServer REST base URL.")
@click.option("--user", default=None, help="GeoServer REST user.")
@click.option("--password", default=None, help="GeoServer REST password.")
@click.option("--workspace", default=None, help="GeoServer workspace name.")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--verify-tls/--no-verify-tls", default=True, help="Verify GeoServer TLS.")
def sync_cmd(
    catalog: Path,
    url: str | None,
    user: str | None,
    password: str | None,
    workspace: str | None,
    json_output: bool,
    verify_tls: bool,
) -> None:
    """Reconcile GeoServer with the current catalog without pruning."""
    result = _provider(url, user, password, workspace, verify_tls=verify_tls).sync(catalog)
    if json_output:
        click.echo(json.dumps(_result_json(result), indent=2))
    else:
        render_result(result)
    if result.errors:
        raise SystemExit(1)


@main.command("serve")
@click.option(
    "--registry",
    "registry_url",
    default=DEFAULT_REGISTRY_URL,
    help="Portolan registry URL.",
)
@click.option("--catalog-id", multiple=True, help="Registry catalog id to publish.")
@click.option("--all", "serve_all", is_flag=True, help="Publish all matching registry catalogs.")
@click.option("--include-stale", is_flag=True, help="Include stale registry entries.")
@click.option("--limit", type=int, default=None, help="Maximum registry entries to publish.")
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=Path(".portolan-geoserver/registry"),
    help="Directory for downloaded registry catalog snapshots.",
)
@click.option("--url", default=None, help="GeoServer REST base URL.")
@click.option("--user", default=None, help="GeoServer REST user.")
@click.option("--password", default=None, help="GeoServer REST password.")
@click.option("--workspace", default=None, help="GeoServer workspace name.")
@click.option(
    "--mode",
    type=click.Choice(["publish", "sync"], case_sensitive=False),
    default="sync",
    show_default=True,
    help="GeoServer operation to apply to each downloaded catalog.",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON.")
@click.option("--verify-tls/--no-verify-tls", default=True, help="Verify GeoServer TLS.")
def serve_cmd(
    registry_url: str,
    catalog_id: tuple[str, ...],
    serve_all: bool,
    include_stale: bool,
    limit: int | None,
    cache_dir: Path,
    url: str | None,
    user: str | None,
    password: str | None,
    workspace: str | None,
    mode: str,
    json_output: bool,
    verify_tls: bool,
) -> None:
    """Publish Portolan registry catalogs to GeoServer."""
    if serve_all and catalog_id:
        raise click.ClickException("Use either --all or --catalog-id, not both.")
    if not serve_all and not catalog_id:
        raise click.ClickException("Use --catalog-id or --all.")
    provider = _provider(url, user, password, workspace, verify_tls=verify_tls)
    result = serve_registry(
        provider,
        registry_url=registry_url,
        catalog_ids=set(catalog_id) if catalog_id else None,
        include_stale=include_stale,
        limit=limit,
        cache_dir=cache_dir,
        mode=mode.lower(),
    )
    if json_output:
        click.echo(json.dumps(_serve_json(result), indent=2))
    else:
        render_serve_result(result)
    if result.errors:
        raise SystemExit(1)


def geoserver_command_group() -> click.Group:
    """Return the Click group that portolan-cli can mount as an extension."""
    return main


def render_plan(plan: PublishPlan) -> None:
    """Render a human-readable plan."""
    click.echo("Portolan -> GeoServer plan")
    click.echo("")
    click.echo(f"Workspace: {plan.workspace}")
    click.echo("")
    click.echo(f"{'Collection':<32} {'Format':<12} {'Action':<10} Reason")
    click.echo("-" * 72)
    for entry in plan.entries:
        fmt = entry.format.value if entry.format is not None else "-"
        click.echo(
            f"{entry.collection:<32} {fmt:<12} {entry.action.value:<10} "
            f"{entry.reason or ''}"
        )
    click.echo("")
    for action, count in plan.counts().items():
        click.echo(f"{action:<12} {count}")


def render_result(result: PublishResult) -> None:
    """Render a human-readable publish result."""
    click.echo(f"Workspace: {result.workspace}")
    click.echo(f"Published: {result.published}")
    click.echo(f"Skipped: {result.skipped}")
    for error in result.errors:
        click.echo(f"Error: {error}", err=True)


def render_serve_result(result: ServeResult) -> None:
    """Render a registry-driven serve result."""
    click.echo(f"Registry: {result.registry_url}")
    click.echo(f"Catalogs: {len(result.catalogs)}")
    for catalog in result.catalogs:
        click.echo(
            f"{catalog.id}: published={catalog.result.published} "
            f"skipped={catalog.result.skipped} path={catalog.local_path}"
        )
        for error in catalog.result.errors:
            click.echo(f"Error: {catalog.id}: {error}", err=True)
    for error in result.errors:
        click.echo(f"Error: {error}", err=True)


def serve_registry(
    provider: GeoServerProvider,
    *,
    registry_url: str,
    catalog_ids: set[str] | None,
    include_stale: bool,
    limit: int | None,
    cache_dir: Path,
    mode: str,
) -> ServeResult:
    """Download registry catalogs and publish them to GeoServer."""
    entries = load_registry_entries(
        registry_url,
        catalog_ids=catalog_ids,
        include_stale=include_stale,
        limit=limit,
    )
    if catalog_ids is not None:
        found_ids = {entry.id for entry in entries}
        missing = sorted(catalog_ids - found_ids)
    else:
        missing = []

    catalogs = []
    errors = [f"catalog not found in registry: {item}" for item in missing]
    for entry in entries:
        try:
            local_path = download_registry_catalog(entry.url, cache_dir)
            publish_result = (
                provider.publish(local_path) if mode == "publish" else provider.sync(local_path)
            )
            catalogs.append(
                ServedCatalog(
                    id=entry.id,
                    url=entry.url,
                    title=entry.title,
                    status=entry.status,
                    local_path=local_path,
                    result=publish_result,
                )
            )
        except Exception as exc:
            errors.append(f"{entry.id}: {exc}")
    return ServeResult(registry_url=registry_url, catalogs=catalogs, errors=errors)


def _provider(
    url: str | None,
    user: str | None,
    password: str | None,
    workspace: str | None,
    *,
    offline: bool = False,
    verify_tls: bool = True,
) -> GeoServerProvider:
    if offline:
        return GeoServerProvider(EmptyGeoServerClient(), workspace=workspace)
    resolved_url = url or os.environ.get("PORTOLAN_GEOSERVER_URL")
    resolved_user = user or os.environ.get("PORTOLAN_GEOSERVER_USER")
    resolved_password = password or os.environ.get("PORTOLAN_GEOSERVER_PASSWORD")
    missing = [
        flag
        for flag, value in (
            ("--url", resolved_url),
            ("--user", resolved_user),
            ("--password", resolved_password),
        )
        if not value
    ]
    if missing:
        raise click.ClickException(f"Missing GeoServer connection option(s): {', '.join(missing)}")
    return GeoServerProvider(
        GeoServerClient(
            str(resolved_url),
            str(resolved_user),
            str(resolved_password),
            verifytls=verify_tls,
        ),
        workspace=workspace,
    )


def _plan_json(plan: PublishPlan) -> dict[str, Any]:
    return {
        "workspace": plan.workspace,
        "entries": [
            {
                "collection": entry.collection,
                "format": entry.format.value if entry.format is not None else None,
                "action": entry.action.value,
                "reason": entry.reason,
            }
            for entry in plan.entries
        ],
        "counts": plan.counts(),
    }


def _result_json(result: PublishResult) -> dict[str, Any]:
    return {
        "workspace": result.workspace,
        "published": result.published,
        "skipped": result.skipped,
        "errors": result.errors,
    }


def _serve_json(result: ServeResult) -> dict[str, Any]:
    return {
        "registry_url": result.registry_url,
        "catalogs": [
            {
                "id": catalog.id,
                "url": catalog.url,
                "title": catalog.title,
                "status": catalog.status,
                "local_path": str(catalog.local_path),
                "result": _result_json(catalog.result),
            }
            for catalog in result.catalogs
        ],
        "errors": result.errors,
    }
