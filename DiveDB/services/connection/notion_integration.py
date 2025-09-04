"""
Notion integration for DiveDB - handles loading Notion databases and metadata mappings.
"""

import ast
import logging
import re
from typing import Dict, List, Optional, Tuple
import concurrent.futures

import pandas as pd

from ..notion_orm import NotionORMManager


class NotionIntegration:
    """Manages Notion database loading, caching, and metadata mappings"""

    def __init__(
        self,
        notion_manager: Optional[NotionORMManager] = None,
        duckdb_connection=None,
        parallelism: int = 8,
    ):
        self.notion_manager = notion_manager
        self.duckdb_connection = duckdb_connection
        self._parallelism = parallelism

        # Track Notion table names loaded into DuckDB
        self._notion_table_names: List[str] = []

        # Cache for Signal DB metadata by signal name
        self._signal_metadata_cache: Dict[str, Dict] = {}

        # Load Notion databases if available
        if self.notion_manager and self.duckdb_connection:
            self.load_notion_databases()

    def load_standardized_channels_df(self) -> Optional[pd.DataFrame]:
        """Load Standardized Channel DB into a DataFrame from DuckDB table or Notion API.
        Returns None if Notion is not available."""
        try:
            # Prefer preloaded DuckDB table created by load_notion_databases
            if "Standardized Channels" in (self._notion_table_names or []):
                df = self.duckdb_connection.sql(
                    'SELECT * FROM "Standardized Channels"'
                ).df()
                return df
        except Exception as e:
            logging.debug(f"Failed to read 'Standardized Channels' from DuckDB: {e}")

        # Fallback to direct Notion API via ORM
        if not self.notion_manager:
            return None
        try:
            Model = self.notion_manager.get_model("Standardized Channel DB")
            records = Model.objects.all()
            if not records:
                return pd.DataFrame()

            rows = []
            for rec in records:
                props = getattr(rec, "_meta").schema.keys()
                row = {}
                for p in props:
                    try:
                        row[p.replace(" ", "_").lower()] = getattr(rec, p)
                    except Exception:
                        row[p.replace(" ", "_").lower()] = None
                rows.append(row)
            return pd.DataFrame(rows)
        except Exception as e:
            logging.debug(f"Failed to load Standardized Channel DB via Notion: {e}")
            return None

    def load_signal_metadata_map(self) -> Dict[str, Dict]:
        """Return a cached mapping of signal_notion_id -> metadata from Signal DB.

        Expects a Notion database named "Signal DB" with properties:
        - Name: Signal name
        - Description: Signal description
        - Label: Display label
        - Standardized Unit: Units
        - Type: Signal type
        - Color: Display color
        - Icon (or similar): Icon path

        Returns mapping where keys are Notion record IDs and values are dicts
        with all metadata fields from Signal DB.
        """
        if self._signal_metadata_cache:
            return self._signal_metadata_cache

        mapping: Dict[str, Dict] = {}
        try:
            if not self.notion_manager:
                self._signal_metadata_cache = mapping
                return mapping

            # Prefer DuckDB materialized table if available
            if "Signals" in (self._notion_table_names or []):
                try:
                    df = self.duckdb_connection.sql('SELECT * FROM "Signals"').df()
                except Exception:
                    df = None
            else:
                df = None

            if df is None:
                logging.error("No Signals DB found in DuckDB")
                return mapping

            if df is not None and not df.empty:
                # Extract all metadata from Signal DB using Notion ID as key
                for _, row in df.iterrows():
                    notion_id = row.get("id")  # Notion record ID
                    if not notion_id:
                        continue

                    # Parse color to extract hex code
                    def parse_color(color_val):
                        """Extract hex color code from Notion color field"""
                        if pd.isna(color_val) or color_val is None:
                            return None
                        color_str = str(color_val)
                        # Look for hex pattern in strings like '\\color {#e4d596} ███████'
                        hex_match = re.search(r"#([0-9a-fA-F]{6})", color_str)
                        if hex_match:
                            return hex_match.group(0).lower()
                        return None

                    # Parse icon to handle pandas <NA> and missing values
                    def parse_icon(icon_val):
                        """Parse icon value, handling pandas <NA> and missing values"""
                        # Debug logging to understand what we're getting
                        logging.debug(
                            f"Icon value: {repr(icon_val)}, type: {type(icon_val)}"
                        )

                        # Handle pandas NA types
                        if pd.isna(icon_val) or icon_val is None:
                            return None
                        # Convert to string and check for various "missing" representations
                        icon_str = str(icon_val).strip()
                        if icon_str in ("<NA>", "nan", "None", ""):
                            return None
                        return icon_str

                    # Build metadata dict with all fields from Signal DB
                    metadata = {
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "label": row.get("label"),
                        "standardized_unit": row.get("standardized_unit"),
                        "type": row.get("type"),
                        "color": parse_color(row.get("color")),
                        "icon": parse_icon(row.get("icon")),
                    }

                    mapping[notion_id] = metadata

        except Exception as e:
            logging.debug(f"Failed to load Signal DB metadata: {e}")

        self._signal_metadata_cache = mapping
        return mapping

    def build_stdchan_mappings(
        self, std_df: pd.DataFrame
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """From Standardized Channels DataFrame, build lookup mappings:
        - channel_id_to_signal_id: mapping of channel_id(lower) -> Signal DB notion_id
        - original_alias_to_channel_id: mapping of alias(lower) -> channel_id
        """
        if std_df is None or std_df.empty:
            return {}, {}

        # Normalize expected column names to underscores lower-case
        cols = {c: c for c in std_df.columns}

        def col(name):
            key = name.replace(" ", "_").lower()
            return cols.get(key, key) if key in std_df.columns else key

        # Column resolution for required fields only
        parent_col = (
            col("parent signal")
            if col("parent signal") in std_df.columns
            else col("parent_signal")
        )
        chan_col = (
            col("channel id")
            if col("channel id") in std_df.columns
            else col("channel_id")
        )
        original_col = (
            col("original channels")
            if col("original channels") in std_df.columns
            else None
        )

        channel_id_to_signal_id: Dict[str, str] = {}
        original_alias_to_channel_id: Dict[str, str] = {}

        def parse_notion_relation(relation_str: str) -> Optional[str]:
            """Parse Notion relation field to extract first ID"""
            if not relation_str:
                return None
            try:
                # Handle string representation of relation list: "[{'id': 'abc123'}]"
                if relation_str.startswith("[") and relation_str.endswith("]"):
                    parsed = ast.literal_eval(relation_str)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        first_relation = parsed[0]
                        if isinstance(first_relation, dict) and "id" in first_relation:
                            return first_relation["id"]
                return None
            except Exception:
                return None

        for _, row in std_df.iterrows():
            parent_signal_raw = row.get(parent_col)
            channel_id = str(row.get(chan_col, "") or "").strip()
            if not channel_id:
                continue

            # Parse parent signal relation to get Signal DB ID
            if parent_signal_raw and pd.notna(parent_signal_raw):
                signal_id = parse_notion_relation(str(parent_signal_raw))
                if signal_id:
                    channel_id_to_signal_id[channel_id.lower()] = signal_id

            # Original channels expansion into alias map
            if original_col is not None and pd.notna(row.get(original_col)):
                raw = str(row.get(original_col))
                # Expect a string representation of list or comma-separated
                candidates = []
                if raw.startswith("[") and raw.endswith("]"):
                    # Try to split simple list string
                    raw2 = raw.strip("[]")
                    candidates = [
                        x.strip().strip("'\"") for x in raw2.split(",") if x.strip()
                    ]
                else:
                    candidates = [x.strip() for x in raw.split(",") if x.strip()]
                for alias in candidates:
                    original_alias_to_channel_id.setdefault(alias.lower(), channel_id)

        return channel_id_to_signal_id, original_alias_to_channel_id

    def load_notion_databases(self):
        """Load all available Notion databases into DuckDB tables"""
        if not self.notion_manager or not self.duckdb_connection:
            return

        def resolve_model_name(db_map_key: str) -> Optional[str]:
            candidates = [
                db_map_key.replace(" DB", ""),
                db_map_key.replace(" DB", "") + "s",
                db_map_key,
            ]
            for candidate in candidates:
                test_db_name = (
                    f"{candidate} DB" if not candidate.endswith(" DB") else candidate
                )
                test_db_name = test_db_name.replace("s DB", " DB")
                if test_db_name == db_map_key:
                    return candidate
            return None

        def fetch_one(db_map_key: str):
            try:
                model_name = resolve_model_name(db_map_key)
                if not model_name:
                    logging.warning(
                        f"Could not determine model name for database '{db_map_key}'"
                    )
                    return None

                model = self.notion_manager.get_model(model_name)

                # Query all data from the model
                records = model.objects.all()
                if not records:
                    return None

                data_rows = []
                schema_keys = list(model._meta.schema.keys())
                attr_names = [k.replace(" ", "_").lower() for k in schema_keys]

                for record in records:
                    row_data = {"id": record.id}
                    # Include page icon if available
                    if hasattr(record, "icon"):
                        row_data["icon"] = record.icon
                    else:
                        row_data["icon"] = None

                    for prop_name, attr_name in zip(schema_keys, attr_names):
                        if hasattr(record, prop_name):
                            value = getattr(record, prop_name)
                            if value is not None and isinstance(value, (list, dict)):
                                row_data[attr_name] = str(value)
                            else:
                                row_data[attr_name] = value
                        else:
                            row_data[attr_name] = None
                    data_rows.append(row_data)

                table_name = model_name + "s"
                df = pd.DataFrame(data_rows)
                return (table_name, df, db_map_key, len(df))
            except Exception as e:
                logging.warning(f"Failed to load Notion database '{db_map_key}': {e}")
                return None

        try:
            futures = []
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, self._parallelism)
            ) as ex:
                for db_map_key in self.notion_manager.db_map.keys():
                    futures.append(ex.submit(fetch_one, db_map_key))

                for fut in concurrent.futures.as_completed(futures):
                    result = fut.result()
                    if not result:
                        continue
                    table_name, df, db_map_key, n = result
                    try:
                        self.duckdb_connection.execute(
                            f'DROP TABLE IF EXISTS "{table_name}"'
                        )
                        self.duckdb_connection.register(table_name, df)
                        self._notion_table_names.append(table_name)
                        logging.info(
                            f"Loaded Notion database '{db_map_key}' into DuckDB table '{table_name}' with {n} records"
                        )
                    except Exception as e:
                        logging.warning(
                            f"Failed to register Notion table '{table_name}': {e}"
                        )
                        continue
        except Exception as e:
            logging.error(f"Error loading Notion databases: {e}")

    def list_notion_tables(self) -> List[str]:
        """List all available Notion tables in DuckDB"""
        if not self.notion_manager:
            return []

        return self._notion_table_names.copy()

    def get_metadata_mappings(
        self,
    ) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Dict]]:
        """Get all metadata mappings needed for channel discovery.

        Returns:
            Tuple of (channel_id_to_signal_id, original_alias_to_channel_id, signal_metadata_map)
        """
        channel_id_to_signal_id: Dict[str, str] = {}
        original_alias_to_channel_id: Dict[str, str] = {}
        signal_metadata_map: Dict[str, Dict] = {}

        if not self.notion_manager:
            return (
                channel_id_to_signal_id,
                original_alias_to_channel_id,
                signal_metadata_map,
            )

        # Load standardized channels mappings
        std_df = self.load_standardized_channels_df()
        if std_df is not None:
            (
                channel_id_to_signal_id,
                original_alias_to_channel_id,
            ) = self.build_stdchan_mappings(std_df)

        # Load all signal metadata
        signal_metadata_map = self.load_signal_metadata_map()

        return (
            channel_id_to_signal_id,
            original_alias_to_channel_id,
            signal_metadata_map,
        )
