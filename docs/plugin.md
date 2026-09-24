# Portolan CLI plugin

`portolan-geoserver` exposes the entry point group `portolan.cli.plugins`.
`portolan-cli` discovers that entry point and mounts the command group under
`portolan geoserver`.

The plugin descriptor is returned by:

```python
from portolan_geoserver.plugin import get_portolan_cli_plugin

plugin = get_portolan_cli_plugin()
print(plugin.name)
print(plugin.command_path)
print(plugin.capabilities)
```

The command path is `("geoserver",)`, so the mounted command is:

```bash
portolan geoserver --help
```

The plugin boundary keeps GeoServer code out of `portolan-cli`. The standalone
CLI remains available as:

```bash
portolan-geoserver --help
```

Both entry points share the same command implementation.
