# Distribution

Tagged releases provide immutable source and wheel archives. The wheel contains
the standalone CLI and the `portolan-cli` plugin entry point.

## Release artifacts

Push a tag that matches the version in `pyproject.toml`:

```bash
git tag v0.1.4
git push origin v0.1.4
```

The release workflow installs the released `portolan-python` dependency, runs
the tests, and checks the package metadata. It then creates a GitHub release
with the `.whl` and `.tar.gz` files.

The workflow rejects a tag that does not match the project version. Update the
version and the `PORTOLAN_PYTHON_VERSION` workflow setting before a later
release needs a newer core library.

## Install from GitHub

Install both wheels directly from their GitHub releases:

```bash
python -m pip install \
  https://github.com/jemacchi/portolan-python/releases/download/v0.1.5/portolan_python-0.1.5-py3-none-any.whl \
  https://github.com/jemacchi/portolan-geoserver/releases/download/v0.1.5/portolan_geoserver-0.1.5-py3-none-any.whl
```

`pip` resolves `click`, `geoservercloud`, and their dependencies from PyPI.

## Install from PyPI

Install a published version and its dependency chain with:

```bash
python -m pip install portolan-geoserver==0.1.5
```

Omit the version constraint to install the latest published version.

## Related package guides

- [`portolan-python` distribution](https://github.com/jemacchi/portolan-python/blob/main/docs/distribution.md)
  covers its wheel and installation options.
- [`portolan-java` distribution](https://github.com/jemacchi/portolan-java/blob/main/docs/distribution.md)
  covers its JAR, GitHub Packages, and Maven Central requirements.
