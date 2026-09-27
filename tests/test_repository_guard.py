from pathlib import Path

from tools.check_repository_guard import MAX_JSON_BYTES, scan_paths


def test_guard_rejects_audio_outside_local_data(tmp_path: Path) -> None:
    candidate = tmp_path / "server" / "not-a-game-asset.ogg"
    candidate.parent.mkdir()
    candidate.write_bytes(b"fixture")

    violations = scan_paths(tmp_path, [Path("server/not-a-game-asset.ogg")])

    assert len(violations) == 1
    assert "audio file suffix" in violations[0].reason


def test_guard_rejects_live2d_metadata_even_when_small(tmp_path: Path) -> None:
    candidate = tmp_path / "server" / "avatar.model3.json"
    candidate.parent.mkdir()
    candidate.write_text("{}", encoding="utf-8")

    violations = scan_paths(tmp_path, [Path("server/avatar.model3.json")])

    assert len(violations) == 1
    assert "Live2D" in violations[0].reason


def test_guard_rejects_oversized_json_outside_allowlist(tmp_path: Path) -> None:
    candidate = tmp_path / "server" / "payload.json"
    candidate.parent.mkdir()
    candidate.write_bytes(b"{" + b"a" * MAX_JSON_BYTES + b"}")

    violations = scan_paths(tmp_path, [Path("server/payload.json")])

    assert len(violations) == 1
    assert "JSON is" in violations[0].reason


def test_guard_allows_oversized_synthetic_fixture(tmp_path: Path) -> None:
    candidate = tmp_path / "tests" / "fixtures" / "synthetic.json"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"{" + b"a" * MAX_JSON_BYTES + b"}")

    assert scan_paths(tmp_path, [Path("tests/fixtures/synthetic.json")]) == []
