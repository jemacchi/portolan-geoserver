"""Standalone CLI for publishing Portolan catalogs to GeoServer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import click

from portolan_geoserver.client import EmptyGeoServerClient, GeoServerClient
from portolan_geoserver.model import PublishPlan, PublishResult
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
