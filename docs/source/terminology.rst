Terminology: Organism / Animal Migration
========================================

Overview
--------

The DiveDB codebase is actively migrating from the term "animal" to "organism" in
Python APIs and Notion databases. This migration is intentionally partial: storage
layers (Iceberg columns, NetCDF files) retain the old names because they are frozen
format contracts that cannot be renamed without data migration.

The table below defines which name is canonical in each context and whether it can
be changed.

.. list-table:: Organism / Animal field name reference
   :widths: 25 25 50
   :header-rows: 1

   * - Context
     - Field name
     - Notes
   * - Python API parameters
     - ``organism_id`` / ``organism_ids``
     - New canonical name — use in all new code
   * - Deprecated Python kwargs
     - ``animal_id`` / ``animal_ids``
     - Still accepted; merged internally by each method
   * - Iceberg / SQL column
     - ``animal``
     - **Frozen** — partition key, do not rename
   * - NetCDF / ``.pkl`` files
     - ``animal_id``
     - **Frozen** — on-disk format contract, do not rename
   * - Notion database name
     - ``"Organism DB"``
     - Falls back to ``"Animal DB"`` for older workspaces
   * - Notion property
     - ``"Organism ID"``
     - Falls back to ``"Animal ID"`` for older workspaces

Why These Layers Are Frozen
---------------------------

**Iceberg / SQL column ``animal``**
    This column is the Iceberg partition key for all data and events tables. Renaming
    it would require rewriting every existing Iceberg table file and is not supported
    by schema evolution without a full data migration. All SQL queries and DuckDB views
    continue to use ``animal`` as the column name.

**NetCDF / ``.pkl`` files ``animal_id``**
    Files already stored on disk or archived carry ``animal_id`` as a coordinate or
    variable name. Renaming would break all existing upload pipelines and archived
    datasets. The ``DataUploader`` maps ``animal_id`` from NetCDF files to the
    ``animal`` Iceberg column during ingest.

Rules for New Code
------------------

- Always use ``organism_id`` / ``organism_ids`` as parameter names in new Python methods.
- Never introduce ``animal_ids`` as a parameter name in new code.
- SQL queries and DuckDB view definitions must continue to reference ``animal`` as the column.
- When accessing Notion, try ``"Organism DB"`` / ``"Organism ID"`` first; the ORM
  integration automatically falls back to the legacy names.
- ``get_model("Animal")`` in ``NotionORMManager`` tries ``"Organism"`` first and
  falls back to ``"Animal"`` for older Notion workspaces.
