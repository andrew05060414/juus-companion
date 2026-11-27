$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
uv run python -m prototypes.native_chat.run --host 127.0.0.1 --port 8765 --open
