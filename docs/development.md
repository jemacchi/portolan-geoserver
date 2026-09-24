# Development

The project uses `uv`. During local development, `portolan-python` is resolved
from `../portolan-python` as an editable dependency.

## Setup

```bash
make setup
```

Run this from the `portolan-geoserver` repository root.

## Test and check

```bash
make test
make lint
make typecheck
make check
```

`make check` runs lint, type checking, and the test suite. Tests use mocked or
empty GeoServer clients, so they do not require a running GeoServer.

## Build

```bash
make build
```

The build target creates source and wheel distributions in `dist/`.

## Clean local artifacts

```bash
make clean
```

This removes local build, cache, and coverage directories.
