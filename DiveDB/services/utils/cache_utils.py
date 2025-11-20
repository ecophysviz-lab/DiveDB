"""
Cache utilities for DuckPond get_data() calls.

Provides file-based caching using pickle format with parameter hashing
and TTL-based expiration.
"""

import hashlib
import pickle
import time
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd


def _normalize_value(value: Any) -> Any:
    """
    Normalize a value for consistent hashing.

    Converts lists to sorted tuples, handles None values.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return tuple(sorted(value)) if value else None
    if isinstance(value, tuple):
        return tuple(sorted(value)) if value else None
    return value


def generate_cache_key(params_dict: Dict[str, Any]) -> str:
    """
    Generate a cache key from parameters using MD5 hash.

    Args:
        params_dict: Dictionary of parameters to hash

    Returns:
        MD5 hash string (hexdigest)
    """
    # Exclude parameters that don't affect the query result
    excluded_params = {"use_cache", "add_timestamp_column"}

    # Create a normalized dict with sorted keys
    normalized_params = {}
    for key in sorted(params_dict.keys()):
        if key not in excluded_params:
            normalized_params[key] = _normalize_value(params_dict[key])

    # Convert to string representation for hashing
    # Use repr() for consistent string representation
    param_str = repr(normalized_params)

    # Generate MD5 hash
    hash_obj = hashlib.md5(param_str.encode("utf-8"))
    return hash_obj.hexdigest()


def get_cache_path(cache_key: str, cache_dir: str = ".cache/duckpond") -> Path:
    """
    Get the full path to a cache file.

    Args:
        cache_key: Cache key (MD5 hash)
        cache_dir: Base cache directory (relative to workspace root)

    Returns:
        Path object pointing to the cache file
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path / f"{cache_key}.pkl"


def load_from_cache(
    cache_key: str, ttl_seconds: int = 86400, cache_dir: str = ".cache/duckpond"
) -> Optional[pd.DataFrame]:
    """
    Load a DataFrame from cache if it exists and is not expired.

    Args:
        cache_key: Cache key (MD5 hash)
        ttl_seconds: Time-to-live in seconds (default: 86400 = 1 day)
        cache_dir: Base cache directory (relative to workspace root)

    Returns:
        DataFrame if cache hit and not expired, None otherwise
    """
    cache_file = get_cache_path(cache_key, cache_dir)

    if not cache_file.exists():
        return None

    # Check if file is expired
    file_age = time.time() - cache_file.stat().st_mtime
    if file_age > ttl_seconds:
        # File expired, delete it
        cache_file.unlink()
        return None

    try:
        with open(cache_file, "rb") as f:
            df = pickle.load(f)
        return df
    except (pickle.UnpicklingError, EOFError, IOError) as e:
        # Corrupted cache file, delete it
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Corrupted cache file {cache_file}: {e}")
        cache_file.unlink()
        return None


def save_to_cache(
    cache_key: str, dataframe: pd.DataFrame, cache_dir: str = ".cache/duckpond"
) -> None:
    """
    Save a DataFrame to cache.

    Args:
        cache_key: Cache key (MD5 hash)
        dataframe: DataFrame to cache
        cache_dir: Base cache directory (relative to workspace root)
    """
    cache_file = get_cache_path(cache_key, cache_dir)

    try:
        with open(cache_file, "wb") as f:
            pickle.dump(dataframe, f)
    except (IOError, OSError) as e:
        # If we can't write to cache, just log and continue
        # Don't fail the operation
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to save cache file {cache_file}: {e}")


def cleanup_old_cache_files(
    cache_dir: str = ".cache/duckpond", ttl_seconds: int = 86400
) -> int:
    """
    Remove cache files older than TTL.

    Args:
        cache_dir: Base cache directory (relative to workspace root)
        ttl_seconds: Time-to-live in seconds (default: 86400 = 1 day)

    Returns:
        Number of files removed
    """
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        return 0

    removed_count = 0
    current_time = time.time()

    for cache_file in cache_path.glob("*.pkl"):
        try:
            file_age = current_time - cache_file.stat().st_mtime
            if file_age > ttl_seconds:
                cache_file.unlink()
                removed_count += 1
        except (OSError, IOError):
            # Skip files we can't access
            continue

    return removed_count
