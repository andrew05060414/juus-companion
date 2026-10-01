"""Tests for fetcher client using mock data and caching."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.fetcher.client import Fetcher, compute_sha256
from pipeline.fetcher.sources import SourceItem


def test_compute_sha256(tmp_path: Path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello juus companion", encoding="utf-8")
    h = compute_sha256(test_file)
    assert len(h) == 64
    assert isinstance(h, str)


def test_fetch_item_cached(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    fetcher = Fetcher(raw_dir=raw_dir)
    item = SourceItem(
        key="fictional_test",
        rel_path="mock/test.json",
        urls=["http://example.invalid/mock.json"],
        description="Fictional mock data",
    )
    dest = raw_dir / item.rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('{"mock": true}', encoding="utf-8")

    # When file already exists and force=False, it should return cached without network call
    result = fetcher.fetch_item(item, force=False)
    assert result == dest
    assert dest.read_text(encoding="utf-8") == '{"mock": true}'


def test_manifest_generation(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    test_file = raw_dir / "test.json"
    test_file.write_text('{"version": 1}', encoding="utf-8")

    fetcher = Fetcher(raw_dir=raw_dir)
    manifest_data = {
        "version": "1.0",
        "sources": {
            "test_key": {
                "rel_path": "test.json",
                "size_bytes": test_file.stat().st_size,
                "sha256": compute_sha256(test_file),
            }
        },
    }
    with open(fetcher.manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)

    loaded = fetcher.load_manifest()
    assert loaded is not None
    assert loaded["version"] == "1.0"
    assert "test_key" in loaded["sources"]

