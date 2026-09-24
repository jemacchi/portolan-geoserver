# Architecture

`portolan-geoserver` publishes Portolan catalog resources to GeoServer through
the GeoServer REST API.

The package has three layers.

## Catalog layer

The catalog layer uses `portolan-python`. It opens a Portolan catalog, lists
collections, reads collection assets, and classifies each asset from metadata.

This layer does not read GeoParquet rows or COG pixels.

## Planning layer

The planning layer converts catalog resources into GeoServer publication
candidates. It chooses the resource type, resource name, workspace, and metadata
that should be sent to GeoServer.

Use `plan` before mutation when you want to inspect the result.

## Execution layer

The execution layer uses `python-geoservercloud` through a small client wrapper.
It ensures the workspace exists, publishes GeoParquet and COG resources, and
records Portolan provenance metadata.

`sync` currently applies the same publication behavior as `publish`. It does not
prune resources that are no longer present in the catalog.
