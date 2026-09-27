"""Minimal package boundary for the local data pipeline."""


def readiness_message() -> str:
    """Return a side-effect-free smoke value until the pipeline is built."""

    return "pipeline-ready"
