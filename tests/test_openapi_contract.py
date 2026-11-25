from pathlib import Path

from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename


def test_openapi_draft_is_valid():
    spec_path = Path(__file__).resolve().parents[1] / "docs" / "openapi-draft.yaml"
    spec, base_uri = read_from_filename(str(spec_path))
    validate(spec, base_uri=base_uri)
