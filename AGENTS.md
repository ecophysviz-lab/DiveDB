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

## DiveDB versioning

### Re-uploading replaces; it must not duplicate

`upload_netcdf` calls `duck_pond.delete_deployment_data(...)` **before** writing
(`data_uploader.py`, "dedup_delete" timing step), which deletes the deployment's existing
`data` and `events` rows using a partition-aligned Iceberg filter
(`EqualTo("deployment", …)`).

**The Iceberg delete alone is not enough.** It is a *metadata* operation: it unlinks the
old data files from the manifest but leaves the Parquet files on disk. Reads do not go
through Iceberg — `_create_dataset_views` builds DuckDB views over
`read_parquet(..., hive_partitioning = true)` against the warehouse directory, so orphaned
files stay visible. Before this was fixed, a second upload of the same deployment doubled
every row (7,051,164 → 14,102,328 on a real deployment) while Iceberg's own
`table.scan()` still reported the correct count, and nothing was logged.

`delete_deployment_data` therefore enumerates the deployment's data files via
`table.inspect.files()` **before** the delete, then removes them from storage afterwards
(`_deployment_data_files` / `_remove_data_files`), handling both the local filesystem and
S3. File removal is best-effort and logged rather than raised, since the Iceberg commit
has already succeeded by that point.

When touching this code path, keep `TestDuckPondDeleteDeploymentData` green — it asserts
the DuckDB view and Iceberg row counts agree after a re-upload, and that deleting one
deployment leaves siblings intact. Both fail if the file cleanup is removed.

**This is the same underlying hazard as the `animal=`/`organism=` partition mismatch
above:** reads bypass Iceberg, so anything that changes the manifest without changing the
directory contents will not behave as expected.

### The storage layer does not know whether a file changed

There is no hash, mtime, or `source_file` column anywhere in the `data`/`events`
schemas — they hold measurement columns only. The `hashlib` usage in
`services/utils/cache_utils.py` is for query caching and is unrelated to uploads.

So on its own, re-running an upload of an *unchanged* file costs a full
delete + re-write, identical to a changed one.

`docs/upload_docs.ipynb` closes that gap in the notebook layer: it fingerprints each
netCDF (SHA-256, streamed) and stores it as an Iceberg **table property** on the
dataset's `data` table:

```text
divedb.source.<deployment_id> = "sha256:<hex>"
```

Read with `table.properties.get(key)`; written with
`table.transaction().set_properties(**{key: value})`. Note `Table.update_properties()`
does **not** exist in pyiceberg 0.9.1 — properties are set through the transaction.

Table properties were chosen over a sidecar file because they live in the catalog, so
the record travels with the warehouse for both the local and S3 backends. The
fingerprint is recorded **only after a successful upload**, so an interrupted upload
retries on the next run instead of being wrongly marked complete.

### Version history comes from Iceberg snapshots

Each upload is a fresh Iceberg commit, so prior versions stay reachable through snapshot
history. This is a side effect of the delete + append, not a deliberate versioning
scheme — and without the fingerprint check, every no-op re-upload burns a snapshot.

### Pin DiveDB in downstream consumers

`pyologger` and `EcoPhysVideoViz` install DiveDB from git. **Pin the ref.** An unpinned
`git+https://…/DiveDB` resolves to whatever the default branch held at install time,
which silently produces a site-packages copy that disagrees with this repo.

The concrete failure: `origin/main` still contains the pre-rename uploader that requires
`metadata["animal"]`, so an organism-keyed upload dies with `KeyError: 'animal'` even
when the working tree is correct. The rename lives on `organism-rename`, not `main` —
pinning to `main` reproduces the bug.

Both consumers are pinned to an exact commit rather than a branch, since a branch ref
still moves:

```toml
"DiveDB @ git+https://github.com/ecophysviz-lab/DiveDB.git@197449138c8c108d862f9a1547e99abb9c195e61"
```

That SHA is the tip of `organism-rename` (PR #53). Re-pin to a release tag once it
merges to `main`.

Symptom to recognize: if `KeyError: 'animal'` appears while this repo's source clearly
uses `organism`, the installed copy is stale. Check with
`python -c "import DiveDB; print(DiveDB.__file__)"` — if it resolves to `site-packages`
rather than this working tree, reinstall against the pin.

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

**Never hardcode credentials in a notebook cell.** Read them from the environment:

```python
import os
from dotenv import load_dotenv

load_dotenv()
storage_options = {
    "key": os.environ["S3_ACCESS_KEY"],
    "secret": os.environ["S3_SECRET_KEY"],
    "client_kwargs": {"endpoint_url": os.environ["S3_ENDPOINT"]},
}
```

Use `os.environ[...]`, not `os.getenv(KEY, "<literal>")`. A literal fallback is exactly
how a hardcoded secret survives a `load_dotenv()` that silently found no `.env` — it
looks like config, keeps working, and gets committed. Fail loudly on a missing env var
instead; that matches the repo's fail-fast rule.

A committed-and-pushed credential is compromised. Rotate it *first*, then purge it from
history — purging alone does nothing, since anyone may already have fetched it.

`scripts/check_notebooks.py` runs via pre-commit: it **blocks** on apparent hardcoded
credentials and **warns** on cell outputs (a rendered example notebook is sometimes
intentional). Run `pre-commit install` once per clone or the hook is inert.

## Do not

- Hardcode a credential anywhere — notebook cell, script, or config. Read from the environment; never use a literal fallback in `os.getenv`.
- Commit a notebook with cell outputs unless the rendered output is deliberately part of the doc — strip them first.
- Rename the `organism` column in any Iceberg schema or DuckDB view — it is the partition key. It was renamed from `animal` once, deliberately; renaming it again breaks every existing warehouse.
- Write `animal=` partition directories into a warehouse that already uses `organism=` (or vice versa) — a mixed warehouse fails *all* queries.
- Rename `animal_id` fields in NetCDF or `.pkl` files — they are part of the on-disk format contract.
- Use `animal_ids` as a new parameter name in any new Python method — use `organism_ids` instead.
- Run production deploy or image build (`make deploy`, `build.sh production`) from an automated agent session.
- Import `DiveDB` internals directly from `dash/` — use the installed package via `from DiveDB.services import ...`.
- Skip `make up` / Docker when tests require a live DuckDB/Iceberg connection (check `pytest.ini` marks).
