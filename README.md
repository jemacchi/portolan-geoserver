# Portolan GeoServer

A Python integration between Portolan catalogs and GeoServer.

`portolan-geoserver` discovers resources from Portolan catalogs and maps them to appropriate GeoServer stores, resources, and layers.

It combines:

* `portolan-python` for understanding Portolan;
* `python-geoservercloud` for interacting with GeoServer.

The project can operate as a standalone CLI and can also expose itself as a plugin for a pluggable `portolan-cli`.

## Purpose

Given a Portolan catalog such as:

```text
catalog
├── buildings
│   └── buildings.parquet
├── roads
│   └── roads.parquet
└── orthophoto
    └── imagery.tif
```

the integration should be able to derive:

```text
Portolan GeoParquet asset
        ↓
GeoServer GeoParquet DataStore
        ↓
FeatureType
        ↓
Layer
```

and:

```text
Portolan COG asset
        ↓
GeoServer COG CoverageStore
        ↓
Coverage
        ↓
Layer
```

The actual GeoParquet and COG data access remains the responsibility of GeoServer's corresponding native stores/readers.

## Architecture

```text
                   Portolan Catalog
                          │
                          ▼
                   portolan-python
                          │
                   domain objects
                          │
                          ▼
                 portolan-geoserver
                  mapping / planning
                          │
                          ▼
                python-geoservercloud
                          │
                          ▼
                      GeoServer
                 ┌────────┴────────┐
                 ▼                 ▼
         GeoParquet Store       COG Store
                 │                 │
                 ▼                 ▼
           FeatureTypes         Coverages
                 │                 │
                 └────────┬────────┘
                          ▼
                        Layers
```

## Responsibilities

`portolan-geoserver` is responsible for:

* opening Portolan catalogs through `portolan-python`;
* discovering collections and assets;
* determining whether an asset can be mapped to a supported GeoServer store;
* generating a publication plan;
* creating appropriate GeoServer stores;
* creating resources;
* publishing layers;
* recording Portolan provenance;
* reconciling existing GeoServer resources with Portolan catalogs;
* supporting dry-run/plan operations;
* supporting synchronization.

Potential commands include:

```bash
portolan-geoserver plan <catalog>
portolan-geoserver publish <catalog>
portolan-geoserver sync <catalog>
```

## Portolan CLI plugin

The same project should optionally register commands with `portolan-cli`.

Once installed:

```bash
pip install portolan-cli
pip install portolan-geoserver
```

the user may obtain:

```bash
portolan geoserver plan ...
portolan geoserver publish ...
portolan geoserver sync ...
```

without moving GeoServer-specific code into `portolan-cli`.

Conceptually:

```text
portolan-cli
     │
     │ discovers plugins
     ▼
portolan-geoserver
```

The standalone and plugin interfaces should call the same application layer and must not duplicate publication logic.

## Dependency boundaries

The project deliberately separates responsibilities.

### `portolan-python`

Answers questions such as:

* What collections exist?
* What assets belong to a collection?
* What is the asset HREF?
* What media type does it declare?
* What Portolan metadata applies?
* Is the catalog conformant?

### `portolan-geoserver`

Answers:

* Which GeoServer store corresponds to this asset?
* What should the store be called?
* Which workspace should contain it?
* What resources need to be created?
* What needs to change during synchronization?

### `python-geoservercloud`

Handles GeoServer operations.

### GeoServer

Reads and serves the actual data.

This means `portolan-geoserver` should **not** implement GeoParquet or COG readers.

## Planning before mutation

Publication should preferably be represented internally as a plan:

```text
Portolan Catalog
       ↓
Publication Planner
       ↓
Publication Plan
       ↓
GeoServer Executor
```

Example conceptual plan:

```yaml
workspace: overture

stores:
  - name: buildings
    type: geoparquet
    asset: s3://bucket/buildings.parquet

resources:
  - name: buildings
    store: buildings

layers:
  - name: buildings
    resource: buildings
```

This makes dry-run, testing, auditing, and reconciliation substantially easier.

## Provenance

Resources managed from Portolan should preserve enough provenance to identify their source.

Possible metadata:

```text
portolan.managed
portolan.catalog
portolan.collection
portolan.asset
portolan.checksum
```

For GeoServer, authoritative provenance should preferably be associated with the published resource (`FeatureTypeInfo` / `CoverageInfo`) rather than only with `LayerInfo`.

This enables future synchronization to answer:

```text
Which Portolan object created this resource?

Has the source changed?

Should this resource be updated?

Should an obsolete managed resource be removed?
```

## Relationship with `geoserver-portolan`

The two projects solve related problems using different integration strategies.

`portolan-geoserver` is an **external Python-driven integration**:

```text
Portolan
   ↓
Python
   ↓
GeoServer API
```

`geoserver-portolan` is a **native GeoServer integration**:

```text
GeoServer
   ↓
Java
   ↓
Portolan
```

They should share mapping concepts and expected behavior where appropriate, but neither should depend on the other.

`portolan-geoserver` is particularly useful for:

* automation;
* CI/CD;
* external orchestration;
* existing GeoServer installations;
* experimentation;
* provisioning and synchronization.

---
