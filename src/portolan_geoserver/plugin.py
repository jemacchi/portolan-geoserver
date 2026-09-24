"""Plugin contract for portolan-cli integration."""

from __future__ import annotations

from dataclasses import dataclass

import click

from portolan_geoserver.cli import geoserver_command_group


@dataclass(frozen=True)
class PortolanCliPlugin:
    """A small extension descriptor that portolan-cli can consume."""

    name: str
    command_path: tuple[str, ...]
    command: click.Group
    capabilities: tuple[str, ...]


def get_portolan_cli_plugin() -> PortolanCliPlugin:
    """Return the GeoServer extension descriptor for portolan-cli."""
    return PortolanCliPlugin(
        name="geoserver",
        command_path=("geoserver",),
        command=geoserver_command_group(),
        capabilities=("export", "geoserver", "catalog-publication"),
    )
