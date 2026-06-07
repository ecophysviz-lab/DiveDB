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

The codebase is migrating from "animal" to "organism" in Python APIs and Notion. Frozen storage layers keep the old names.

| Context | Field name | Notes |
| --- | --- | --- |
| Python API params | `organism_id` / `organism_ids` | New canonical name |
| Deprecated kwargs | `animal_id` / `animal_ids` | Still accepted; merged internally |
| Iceberg/SQL column | `animal` | Frozen — do not rename |
| NetCDF / pkl files | `animal_id` | Frozen — do not rename |
| Notion DB name | `"Organism DB"` | Falls back to `"Animal DB"` |
| Notion property | `"Organism ID"` | Falls back to `"Animal ID"` |

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

## Do not

- Rename the `animal` column in any Iceberg schema or DuckDB view — it is the partition key and is frozen.
- Rename `animal_id` fields in NetCDF or `.pkl` files — they are part of the on-disk format contract.
- Use `animal_ids` as a new parameter name in any new Python method — use `organism_ids` instead.
- Run production deploy or image build (`make deploy`, `build.sh production`) from an automated agent session.
- Import `DiveDB` internals directly from `dash/` — use the installed package via `from DiveDB.services import ...`.
- Skip `make up` / Docker when tests require a live DuckDB/Iceberg connection (check `pytest.ini` marks).
