# Examples

These examples assume a local Portolan catalog at `./catalog`.

## Install a released version

Until both packages are published on PyPI, install their released wheels in one
command:

```bash
python -m pip install \
  https://github.com/jemacchi/portolan-python/releases/download/v0.1.3/portolan_python-0.1.3-py3-none-any.whl \
  https://github.com/jemacchi/portolan-geoserver/releases/download/v0.1.2/portolan_geoserver-0.1.2-py3-none-any.whl
```

Confirm that the standalone command and plugin metadata are available:

```bash
portolan-geoserver --help
python -c "from importlib.metadata import entry_points; print(entry_points(group='portolan.cli.plugins'))"
```

After PyPI publication, the equivalent installation is:

```bash
python -m pip install portolan-geoserver==0.1.2
```

## Show a publication plan without GeoServer access

```bash
portolan-geoserver plan ./catalog --offline
```

Offline planning uses an empty GeoServer inventory. It is useful for checking
which collections can become GeoServer resources.

## Show a JSON plan

```bash
portolan-geoserver plan ./catalog --offline --json
```

The JSON output is suitable for tests and CI logs.

## Publish a catalog

```bash
export PORTOLAN_GEOSERVER_URL=http://localhost:8080/geoserver
export PORTOLAN_GEOSERVER_USER=admin
export PORTOLAN_GEOSERVER_PASSWORD=geoserver

portolan-geoserver publish ./catalog --workspace demo
```

The command reads the catalog with `portolan-python` and sends supported assets
to GeoServer. Unsupported assets are skipped.

## Serve registry catalogs

```bash
portolan-geoserver serve \
  --catalog-id example-catalog \
  --cache-dir ./.portolan-geoserver/registry \
  --workspace demo
```

`serve` downloads catalog snapshots from the Portolan registry, then publishes
or syncs each downloaded catalog.

## Use it through portolan-cli

When both packages are installed in the same environment, `portolan-cli` can
mount the plugin command group.

```bash
portolan geoserver plan ./catalog --offline
portolan geoserver serve --catalog-id example-catalog --workspace demo
```

The standalone command and the plugin command call the same implementation.
