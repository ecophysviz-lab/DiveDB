# DiveDB

Apache Iceberg data lake + Plotly Dash visualization app for biologging data.

**Detailed package reference:** [DiveDB/AI_DOCS.md](DiveDB/AI_DOCS.md) | **Dash app reference:** [dash/AI_DOCS.md](dash/AI_DOCS.md)

## Repo layout

| Area | Path | Doc |
| --- | --- | --- |
| Python package | `DiveDB/` (services, connection, utils) | [DiveDB/AI_DOCS.md](DiveDB/AI_DOCS.md) |
| Dash app | `dash/` | [dash/AI_DOCS.md](dash/AI_DOCS.md) |
| Tests | `tests/` | `pytest.ini` at repo root |
| Deploy | `docker-compose.development.yaml`, `Makefile` | `README.md` |

## Key abstractions

| Class | Module | Role |
| --- | --- | --- |
| `DuckPond` | `DiveDB/services/duck_pond.py` | Primary data lake interface — query, write, cache |
| `DataUploader` | `DiveDB/services/data_uploader.py` | NetCDF validation and upload to Iceberg |
| `NotionORMManager` | `DiveDB/services/notion_orm.py` | ORM-like access to Notion metadata databases |
| `DiveData` | `DiveDB/services/dive_data.py` | DuckDB relation wrapper with EDF export |
| `ImmichService` | `DiveDB/services/immich_service.py` | Photo/video media asset management |

## Dev commands

```bash
# Start Jupyter + services (Docker)
make up

# Run Dash visualization app
cd dash && python data_visualization.py   # http://localhost:8054

# Run tests (no Docker required; needs root .env)
pytest

# Build CSS from SASS (dash/)
cd dash && npm run build-css
```

Copy `.env.example` → `.env` and fill in Notion credentials, S3/Iceberg config, and Immich API key.

## Organism / animal terminology

The codebase has been migrated from "animal" to "organism" in Python APIs, Notion,
**and the Iceberg storage layer**. NetCDF/pkl files keep the old names for back-compat.

| Context | Field name | Notes |
| --- | --- | --- |
| Python API params | `organism_id` / `organism_ids` | New canonical name |
| Deprecated kwargs | `animal_id` / `animal_ids` | Still accepted; merged internally |
| Iceberg/SQL column | `organism` | Renamed; partition dirs are `organism=...` |
| NetCDF / pkl files | `animal_id` | Frozen — do not rename |
| NetCDF upload metadata | `organism` | Legacy `animal` key still accepted |
| Notion DB name | `"Organism DB"` | Falls back to `"Animal DB"` |
| Notion property | `"Organism ID"` | Falls back to `"Animal ID"` |

### A warehouse must not mix `animal=` and `organism=`

Reads do **not** go through Iceberg. `_create_dataset_views` builds DuckDB views over
`read_parquet(..., hive_partitioning = true)`, which resolves columns by *name* from the
Parquet footer and Hive directory names — Iceberg field IDs are never consulted, so
renaming a field in the schema does **not** migrate existing files.

If one warehouse prefix contains both `animal=…/` and `organism=…/` directories, DuckDB
raises `Binder Error: Hive partition mismatch` and **every query fails, including
`SELECT *`** — for all datasets, not just the affected one. Pre-rename warehouses must
have their partition directories renamed, or be re-uploaded, before use.

See [DiveDB/AI_DOCS.md](DiveDB/AI_DOCS.md) for the full rationale.

## Code standards

### Philosophy

- **Fail fast** — no invented defaults, no silent fallbacks; missing data is a bug.
- **No defensive programming** — we own schemas; access fields directly.
- **DRY** — extract repeated patterns.
- **Logging** — errors/warnings only; no debug/info in production code; no `print`.
- **Quality over token cost** — do not cut corners.

### Python

- Type hints on all signatures.
- No bare `except Exception`; no `.get()` with fabricated defaults on required keys.
- Use `logging.warning` / `logging.error`; never `print`.
- Pydantic / dataclasses at API and config boundaries.

### Dash / callbacks

- Keep server-side callbacks in `callbacks.py` or `selection_callbacks.py`; client-side in `clientside_callbacks.py`.
- Never add new `dcc.Store` without documenting it in [dash/AI_DOCS.md](dash/AI_DOCS.md) Store Schemas table.
- Use `allow_duplicate=True` only when a store is legitimately written by multiple callbacks.

### Notebooks

Commit notebooks with their cell outputs stripped. Outputs are usually the bulk of a
notebook's line count (stripping one in `docs/` removed ~4,200 lines), they churn on
every re-run, and they can leak absolute data paths, tokens, or record counts into
history.

```bash
jupyter nbconvert --clear-output --inplace <notebook>
```

`scripts/warn_notebook_outputs.py` runs via pre-commit and **warns** when a staged
notebook still has outputs — it never blocks, since a rendered example notebook is
sometimes intentional. Run `pre-commit install` once per clone or the hook is inert.

## Do not

- Commit a notebook with cell outputs unless the rendered output is deliberately part of the doc — strip them first.
- Rename the `organism` column in any Iceberg schema or DuckDB view — it is the partition key. It was renamed from `animal` once, deliberately; renaming it again breaks every existing warehouse.
- Write `animal=` partition directories into a warehouse that already uses `organism=` (or vice versa) — a mixed warehouse fails *all* queries.
- Rename `animal_id` fields in NetCDF or `.pkl` files — they are part of the on-disk format contract.
- Use `animal_ids` as a new parameter name in any new Python method — use `organism_ids` instead.
- Run production deploy or image build (`make deploy`, `build.sh production`) from an automated agent session.
- Import `DiveDB` internals directly from `dash/` — use the installed package via `from DiveDB.services import ...`.
- Skip `make up` / Docker when tests require a live DuckDB/Iceberg connection (check `pytest.ini` marks).
