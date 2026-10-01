from juus_pipeline import readiness_message


def test_pipeline_package_is_importable() -> None:
    assert readiness_message() == "pipeline-ready"
