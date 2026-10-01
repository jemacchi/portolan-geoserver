# Distribution

Tagged releases provide immutable source and wheel archives. The wheel contains
the standalone CLI and the `portolan-cli` plugin entry point.

## Release artifacts

Push a tag that matches the version in `pyproject.toml`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow installs the released `portolan-python` dependency, runs
the tests, and checks the package metadata. It then creates a GitHub release
with the `.whl` and `.tar.gz` files.

The workflow rejects a tag that does not match the project version. Update the
version and the `PORTOLAN_PYTHON_VERSION` workflow setting before a later
release needs a newer core library.

## Install from GitHub

Install both wheels because `portolan-python` is not yet available from PyPI:

```bash
python -m pip install \
  https://github.com/jemacchi/portolan-python/releases/download/v0.1.0/portolan_python-0.1.0-py3-none-any.whl \
  https://github.com/jemacchi/portolan-geoserver/releases/download/v0.1.0/portolan_geoserver-0.1.0-py3-none-any.whl
```

`pip` resolves `click`, `geoservercloud`, and their dependencies from PyPI.

## Publish to PyPI

Publish `portolan-python` before this package. PyPI must be able to resolve the
declared `portolan-python>=0.1.0` dependency for normal installations.

Complete these steps once:

1. Add a pending trusted publisher for the `portolan-geoserver` PyPI project.
2. Select the GitHub repository `jemacchi/portolan-geoserver`.
3. Set the workflow name to `release.yml` and the environment to `pypi`.
4. Create the `pypi` environment in the GitHub repository.
5. Add the repository variable `PUBLISH_PYPI` with the value `true`.

The workflow then uses an OpenID Connect token instead of a stored PyPI token.
After publication, consumers can install the complete dependency chain with:

```bash
python -m pip install portolan-geoserver==0.1.0
```

PyPI versions are immutable. Increase the version in `pyproject.toml` before
the next release.

## Related package guides

- [`portolan-python` distribution](https://github.com/jemacchi/portolan-python/blob/main/docs/distribution.md)
  covers its wheel and PyPI setup.
- [`portolan-java` distribution](https://github.com/jemacchi/portolan-java/blob/main/docs/distribution.md)
  covers its JAR, GitHub Packages, and Maven Central requirements.
