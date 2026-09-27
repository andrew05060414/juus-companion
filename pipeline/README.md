# pipeline

`pipeline/` is the local-only import and validation boundary for character
data. Source material and generated character cards belong under the ignored
`data/` directory and must never be committed.

The package shares the root `pyproject.toml` and `uv.lock` with `server/` so
the repository has one reproducible lint/test toolchain without coupling the
two runtime source trees.
