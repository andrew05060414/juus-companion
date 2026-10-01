"""Client for downloading and caching upstream game data with manifest tracking."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from pipeline.config import DEFAULT_RAW_DIR
from pipeline.fetcher.sources import UPSTREAM_SOURCES, SourceItem

logger = logging.getLogger(__name__)


def compute_sha256(file_path: Path) -> str:
    """Compute sha256 checksum for a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class Fetcher:
    """Downloads and verifies upstream raw game asset tables."""

    def __init__(self, raw_dir: Optional[Path] = None, timeout: int = 45):
        self.raw_dir = raw_dir or DEFAULT_RAW_DIR
        self.timeout = timeout
        self.manifest_path = self.raw_dir / "manifest.json"

    def fetch_item(self, item: SourceItem, force: bool = False) -> Optional[Path]:
        """Fetch a single source item if missing or force requested."""
        dest_path = self.raw_dir / item.rel_path
        if dest_path.exists() and not force:
            logger.info("Using cached %s -> %s", item.key, dest_path)
            return dest_path

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "JuusCompanion-Pipeline/0.1"}

        last_error = None
        for url in item.urls:
            logger.info("Fetching %s from %s ...", item.key, url)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        content = resp.read()
                        with open(dest_path, "wb") as f:
                            f.write(content)
                        logger.info("Saved %s (%d bytes) to %s", item.key, len(content), dest_path)
                        return dest_path
            except Exception as e:
                logger.warning("Failed to fetch %s from %s: %s", item.key, url, e)
                last_error = e

        if item.required:
            raise RuntimeError(f"Failed to fetch required source {item.key}: {last_error}")
        logger.warning("Optional source %s could not be fetched; continuing without it", item.key)
        return None

    def fetch_all(self, force: bool = False) -> Dict[str, Path]:
        """Fetch all configured upstream sources and write manifest.json."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        results: Dict[str, Path] = {}
        manifest_sources = {}

        for item in UPSTREAM_SOURCES:
            dest = self.fetch_item(item, force=force)
            if dest and dest.exists():
                results[item.key] = dest
                size = dest.stat().st_size
                sha256 = compute_sha256(dest)
                manifest_sources[item.key] = {
                    "rel_path": item.rel_path,
                    "size_bytes": size,
                    "sha256": sha256,
                    "description": item.description,
                    "cached": not force,
                }
            # Polite rate limit: ≤1 req/s against upstream hosts
            time.sleep(1.0)

        manifest_data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sources": manifest_sources,
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, ensure_ascii=False, indent=2)

        logger.info("Manifest saved to %s", self.manifest_path)
        return results

    def load_manifest(self) -> Optional[dict]:
        """Load manifest.json if exists."""
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

