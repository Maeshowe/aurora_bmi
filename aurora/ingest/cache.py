"""
Cache manager for API responses.

Supports JSON and Parquet formats with TTL-based invalidation.
Uses atomic writes to prevent corruption.
"""

import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from aurora.core.exceptions import CacheError


logger = logging.getLogger(__name__)


class CacheManager:
    """
    File-based cache manager.

    Stores API responses in JSON or Parquet format with TTL support.
    Uses atomic writes (temp file + rename) to prevent corruption.

    Args:
        base_dir: Base directory for cache files
        ttl_days: Time-to-live in days (default 7)
        format: Storage format ("json" or "parquet")
    """

    def __init__(
        self,
        base_dir: Path,
        ttl_days: int = 7,
        format: str = "json",
    ) -> None:
        self.base_dir = Path(base_dir)
        self.ttl_days = ttl_days
        self.format = format
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(
        self,
        source: str,
        endpoint: str,
        identifier: str | None,
        trade_date: date,
    ) -> Path:
        """
        Construct cache file path.

        Format: {base_dir}/{source}/{endpoint}/{identifier}/{date}.{format}
        """
        parts = [self.base_dir, source, endpoint]
        if identifier:
            parts.append(identifier)
        parts.append(f"{trade_date.isoformat()}.{self.format}")
        return Path(*parts)

    def _is_valid(self, path: Path) -> bool:
        """Check if cached file exists and is within TTL."""
        if not path.exists():
            return False

        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        age = datetime.now() - mtime
        return age < timedelta(days=self.ttl_days)

    def _atomic_write(self, path: Path, write_func: Any) -> None:
        """
        Write file atomically using temp file + rename.

        This prevents corruption from interrupted writes.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory for atomic rename
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=".cache_",
            dir=path.parent,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                write_func(f)
            os.rename(temp_path, path)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    # JSON cache methods

    def load_json(
        self,
        source: str,
        endpoint: str,
        identifier: str | None,
        trade_date: date,
    ) -> dict[str, Any] | None:
        """
        Load JSON data from cache.

        Returns None if not cached or expired.
        """
        path = self._get_path(source, endpoint, identifier, trade_date)

        if not self._is_valid(path):
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Cache hit: {path}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Cache read error: {e}")
            return None

    def save_json(
        self,
        data: dict[str, Any],
        source: str,
        endpoint: str,
        identifier: str | None,
        trade_date: date,
    ) -> Path:
        """
        Save JSON data to cache atomically.

        Returns the cache file path.
        """
        path = self._get_path(source, endpoint, identifier, trade_date)

        def write_func(f: Any) -> None:
            json.dump(data, f, indent=2, default=str)

        try:
            self._atomic_write(path, write_func)
            logger.debug(f"Cache save: {path}")
            return path
        except Exception as e:
            raise CacheError(f"Failed to save cache: {e}") from e

    # Parquet cache methods

    def load_parquet(
        self,
        source: str,
        endpoint: str,
        identifier: str | None,
        trade_date: date,
    ) -> pd.DataFrame | None:
        """
        Load DataFrame from Parquet cache.

        Returns None if not cached or expired.
        """
        # Use .parquet extension
        path = self._get_path(source, endpoint, identifier, trade_date)
        path = path.with_suffix(".parquet")

        if not self._is_valid(path):
            return None

        try:
            df = pd.read_parquet(path)
            logger.debug(f"Cache hit: {path}")
            return df
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    def save_parquet(
        self,
        df: pd.DataFrame,
        source: str,
        endpoint: str,
        identifier: str | None,
        trade_date: date,
    ) -> Path:
        """
        Save DataFrame to Parquet cache.

        Returns the cache file path.
        """
        path = self._get_path(source, endpoint, identifier, trade_date)
        path = path.with_suffix(".parquet")
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file for atomic write
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=".cache_",
            dir=path.parent,
        )
        os.close(fd)

        try:
            df.to_parquet(temp_path, index=False, compression="snappy")
            os.rename(temp_path, path)
            logger.debug(f"Cache save: {path}")
            return path
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise CacheError(f"Failed to save cache: {e}") from e

    def clear(self, older_than_days: int | None = None) -> int:
        """
        Clear cache files.

        Args:
            older_than_days: Only clear files older than this (default: all)

        Returns:
            Number of files removed
        """
        count = 0
        cutoff = datetime.now() - timedelta(days=older_than_days or 0)

        for path in self.base_dir.rglob("*"):
            if not path.is_file():
                continue

            if older_than_days:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime > cutoff:
                    continue

            try:
                path.unlink()
                count += 1
            except OSError:
                pass

        logger.info(f"Cleared {count} cache files")
        return count
