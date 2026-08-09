# Getting started

ZupuLint requires Python 3.12 or newer when installed as a Python package. Standalone release archives do not require Python.

## Install a release wheel

Download `zupulint-0.1.0-py3-none-any.whl` from the GitHub Release, then install it into an isolated environment:

```bash
pipx install ./zupulint-0.1.0-py3-none-any.whl
# or
uv tool install ./zupulint-0.1.0-py3-none-any.whl
zupulint version
```

## Run from source

```bash
git clone https://github.com/KanadeK/zupulint.git
cd zupulint
uv sync --all-extras --dev
uv run zupulint version
```

## First scan

All bundled examples are fictional:

```bash
zupulint sample create --destination zupulint-sample
zupulint scan zupulint-sample/valid/family.ged
zupulint scan zupulint-sample/invalid/invalid-structure.ged \
  --format html --output report.html --fail-on error
```

The valid GEDCOM produces zero findings. The invalid fixture intentionally returns exit code `1` because error-level rules are present.

## Start the local workbench

```bash
zupulint web
```

Open `http://127.0.0.1:8000`. The installed Python package serves both the built workbench and API; no Node.js process is needed for normal use. OpenAPI is available at `/docs`, and the health endpoint is `/health`.

For source-level frontend development only, run `pnpm --dir apps/web dev` alongside `uv run zupulint web`; Vite listens on `127.0.0.1:5173` and calls the local API.
