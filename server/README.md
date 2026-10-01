# server

`server/` will contain the Juus Companion brain service. The first milestone
only establishes the package boundary and environment-variable configuration;
business endpoints are intentionally out of scope for M0-1.

The service uses the repository-level `pyproject.toml` and `uv.lock`. Keeping
one development lockfile for the server and pipeline prevents lint/test tools
from drifting while their runtime packages remain isolated under their own
`src/` directories.
