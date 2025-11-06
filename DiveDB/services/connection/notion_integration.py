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

    def load_signal_metadata_map(
        self, channel_ids: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """Return a cached mapping of channel_id -> metadata from Standardized Channels and Parent Signals.

        Uses ORM to traverse from Standardized Channels to their Parent Signals,
        combining channel-specific overrides with parent signal base properties.

        Args:
            channel_ids: Optional list of channel IDs to load metadata for. If None, loads all channels.

        Returns mapping where keys are Standardized Channel IDs and values are dicts
        with all metadata fields (preferring channel overrides over parent defaults).
        """
        # If specific channel_ids requested, don't use cache - fetch fresh
        # If no channel_ids specified and cache exists, return cache
        if channel_ids is None and self._signal_metadata_cache:
            return self._signal_metadata_cache

        mapping: Dict[str, Dict] = {}

        if not self.notion_manager:
            if channel_ids is None:
                self._signal_metadata_cache = mapping
            return mapping

        # Normalize channel_ids to lowercase for case-insensitive comparison
        normalized_filter = (
            set(cid.lower() for cid in channel_ids) if channel_ids else None
        )

        # Helper functions for parsing
        def parse_color(color_val):
            """Extract hex color code from Notion color field"""
            if pd.isna(color_val) or color_val is None or not color_val:
                return None
            color_str = str(color_val)
            # Look for hex pattern in strings like '\\color {#e4d596} ███████'
            hex_match = re.search(r"#([0-9a-fA-F]{6})", color_str)
            if hex_match:
                return hex_match.group(0).lower()
            return None

        def parse_icon(icon_val):
            """Parse icon value, handling pandas <NA> and missing values"""
            if pd.isna(icon_val) or icon_val is None or not icon_val:
                return None
            icon_str = str(icon_val).strip()
            if icon_str in ("<NA>", "nan", "None", ""):
                return None
            return icon_str

        def safe_get_attr(obj, *attr_names, default=None):
            """Try multiple attribute names and return the first non-None value"""
            for attr_name in attr_names:
                if hasattr(obj, attr_name):
                    val = getattr(obj, attr_name, None)
                    if val is not None:
                        return val
            return default

        try:
            # Load Standardized Channels using ORM
            print("Loading Standardized Channels via ORM for metadata mapping")
            StandardizedChannelModel = self.notion_manager.get_model(
                "Standardized Channel"
            )
            channel_records = StandardizedChannelModel.objects.all()

            if not channel_records:
                print("No Standardized Channel records found")
                self._signal_metadata_cache = mapping
                return mapping

            print(f"Found {len(channel_records)} Standardized Channel records")

            # Process each channel and traverse to parent signal
            for channel in channel_records:
                channel_id = safe_get_attr(channel, "Channel ID", "channel_id")
                if not channel_id:
                    print(f"Skipping channel {channel.id} - no Channel ID")
                    continue

                # If filtering by specific channel_ids, skip channels not in the list
                if normalized_filter and channel_id.lower() not in normalized_filter:
                    continue

                print("Channel: ", channel)
                print(
                    f"Channel {channel_id}: methods={[attr for attr in dir(channel) if callable(getattr(channel, attr)) and not attr.startswith('__')]}"
                )

                # Get parent signal using the injected relationship method
                # Method is named after target database: get_signal() for Signal DB
                parent_signals = None
                if hasattr(channel, "get_signal"):
                    parent_signals = channel.get_signal()
                    print(
                        f"Channel {channel_id}: Found {len(parent_signals) if parent_signals else 0} parent signal(s)"
                    )
                else:
                    print(f"Channel {channel_id}: No get_signal method found")
                # Extract parent signal properties if available
                parent = (
                    parent_signals[0]
                    if parent_signals and len(parent_signals) > 0
                    else None
                )

                if parent:
                    # Combine channel overrides with parent signal defaults
                    # Build description: parent description + channel description suffix
                    parent_desc = (
                        safe_get_attr(parent, "Description", "description") or ""
                    )
                    channel_suffix = (
                        safe_get_attr(
                            channel, "Description Suffix", "description_suffix"
                        )
                        or ""
                    )
                    combined_description = (
                        f"{parent_desc} {channel_suffix}".strip()
                        if parent_desc or channel_suffix
                        else None
                    )

                    # Icon: prefer channel icon, fallback to parent icon
                    channel_icon = parse_icon(getattr(channel, "icon", None))
                    parent_icon = parse_icon(getattr(parent, "icon", None))

                    metadata = {
                        "name": safe_get_attr(parent, "Label", "Name", "label", "name"),
                        "description": combined_description,
                        "label": safe_get_attr(parent, "Label", "label"),
                        "standardized_unit": safe_get_attr(
                            channel, "Unit Override", "unit_override"
                        )
                        or safe_get_attr(parent, "Unit", "unit"),
                        "type": safe_get_attr(parent, "Type", "type"),
                        "color": parse_color(
                            safe_get_attr(channel, "Color Override", "color_override")
                        )
                        or parse_color(safe_get_attr(parent, "Color", "color")),
                        "icon": channel_icon or parent_icon,
                    }

                    mapping[channel_id] = metadata
                    print(f"Mapped channel {channel_id} with parent signal metadata")
                else:
                    # No parent signal - use channel properties only
                    print(
                        f"Channel {channel_id} has no parent signal, using channel properties only"
                    )
                    metadata = {
                        "name": safe_get_attr(
                            channel, "Label", "Name", "label", "name"
                        ),
                        "description": safe_get_attr(
                            channel,
                            "Description Suffix",
                            "Description",
                            "description_suffix",
                            "description",
                        ),
                        "label": safe_get_attr(channel, "Label", "label"),
                        "standardized_unit": safe_get_attr(
                            channel, "Unit Override", "Unit", "unit_override", "unit"
                        ),
                        "type": safe_get_attr(channel, "Type", "type"),
                        "color": parse_color(
                            safe_get_attr(
                                channel,
                                "Color Override",
                                "Color",
                                "color_override",
                                "color",
                            )
                        ),
                        "icon": parse_icon(getattr(channel, "icon", None)),
                    }
                    mapping[channel_id] = metadata

            print(f"Successfully mapped {len(mapping)} channels to metadata")

        except Exception as e:
            print(f"Failed to load Signal DB metadata via ORM: {e}")

        # Only cache when loading all channels (no filter)
        if channel_ids is None:
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
        channel_ids: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Dict]]:
        """Get all metadata mappings needed for channel discovery.

        Args:
            channel_ids: Optional list of channel IDs to load metadata for. If None, loads all channels.

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

        # Load signal metadata (optionally filtered by channel_ids)
        signal_metadata_map = self.load_signal_metadata_map(channel_ids=channel_ids)

        return (
            channel_id_to_signal_id,
            original_alias_to_channel_id,
            signal_metadata_map,
        )
