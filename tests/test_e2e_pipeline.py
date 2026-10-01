"""End-to-end integration test for the full pipeline run using FICTIONAL character data."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.cli import run_pipeline
from tests.test_extractor import setup_fictional_raw_tables


def test_e2e_pipeline_fictional_run(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "output"

    # Setup fictional raw tables for ship_group 88888
    setup_fictional_raw_tables(raw_dir)

    # Run complete pipeline in offline mode for fictional ship_group 88888
    exit_code = run_pipeline(
        raw_dir=raw_dir,
        output_dir=output_dir,
        groups=[88888],
        offline=True,
    )
    assert exit_code == 0

    # 1. Check SillyTavern card export
    st_files = list((output_dir / "sillytavern").glob("*.json"))
    assert len(st_files) == 1
    with open(st_files[0], "r", encoding="utf-8") as f:
        st_data = json.load(f)
    assert st_data["spec"] == "chara_card_v2"
    assert st_data["data"]["name"] == "试航者·星穹"

    # 2. Check AstrBot persona export
    astr_files = list((output_dir / "astrbot").glob("*_astrbot.json"))
    assert len(astr_files) == 1
    with open(astr_files[0], "r", encoding="utf-8") as f:
        astr_data = json.load(f)
    assert "system_prompt" in astr_data
    assert "persona_name" not in astr_data
    assert isinstance(astr_data["begin_dialogs"], list)
    assert len(astr_data["begin_dialogs"]) % 2 == 0
    assert isinstance(astr_data["begin_dialogs"][0], str)
    assert astr_data["tools"] is None

    # Sidecar persona name mapping
    names_file = output_dir / "astrbot" / "persona_names.json"
    assert names_file.exists()
    with open(names_file, "r", encoding="utf-8") as f:
        names_data = json.load(f)
    assert len(names_data) >= 1

    # 3. Check Juus Brain format export
    brain_files = list((output_dir / "juus_brain").glob("*.json"))
    assert len(brain_files) == 1
    with open(brain_files[0], "r", encoding="utf-8") as f:
        brain_data = json.load(f)
    assert brain_data["schema_version"] == "1.0"
    assert brain_data["ship_group"] == 88888
    assert brain_data["baseline_relationship"]["is_oath"] is True

    # 4. Check QA validation reports
    report_json = output_dir / "validation_report.json"
    report_md = output_dir / "validation_report.md"
    assert report_json.exists()
    assert report_md.exists()

    with open(report_json, "r", encoding="utf-8") as f:
        qa_data = json.load(f)
    assert qa_data["passed_characters"] == 1
    assert qa_data["average_score"] >= 90
