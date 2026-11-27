# pipeline

`pipeline/` is the local-only import and validation boundary for character
data. Source material and generated character cards belong under the ignored
`data/` directory and must never be committed. As of 2026-11-26 the batch
SillyTavern card generation entrypoints are frozen; the registry and exporter
modules remain as reference infrastructure. See `docs/native-chat-prototype.md`.

The package shares the root `pyproject.toml` and `uv.lock` with `server/` so
the repository has one reproducible lint/test toolchain without coupling the
two runtime source trees.
