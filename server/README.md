# server

`server/` will contain the Juus Companion brain service. The first milestone
only establishes the package boundary and environment-variable configuration;
business endpoints are intentionally out of scope for M0-1.

The service uses the repository-level `pyproject.toml` and `uv.lock`. Keeping
one development lockfile for the server and pipeline prevents lint/test tools
from drifting while their runtime packages remain isolated under their own
`src/` directories.

服务端现有无框架依赖的气泡解析、媒体候选校验与近期窗口回填工具。
格式、配置、容错和与 #15 的边界见
[`ADR-0006`（提议）](../docs/decisions/ADR-0006-bubble-protocol.md)。
解析结果含供宿主记录的 trace 告警及 `needs_retry`，不会执行模型重试、落库或网络调用。
