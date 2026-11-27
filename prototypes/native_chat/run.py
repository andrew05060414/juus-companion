"""Start the local native-chat prototype."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVER_SRC = ROOT_DIR / "server" / "src"
if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))

from .engine import LocalChatEngine
from .models import GatewayRouter, load_model_profiles
from .prompt import DailyContext
from .web import serve


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class DemoFallbackGateway:
    """Deterministic loopback fallback used only when no real backend is configured."""

    def complete(
        self, *, messages: Sequence[Mapping[str, str]], metadata: Mapping[str, str]
    ) -> str:
        speaker = metadata.get("speaker_id", "")
        model = metadata.get("model_profile", "")
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        )
        short = " ".join(last_user.split())[:24]
        if speaker == "belfast":
            first = "先别急。" if model == "gemini-carbon" else "我在这里。"
            return f"<bubble>{first}</bubble><bubble>您刚才说的是“{short}”。</bubble><bubble>先喝口水，我陪您理顺。</bubble>"
        if speaker == "enterprise":
            first = "收到。" if model == "gemini-carbon" else "嗯，我在听。"
            return f"<bubble>{first}</bubble><bubble>这件事不用一次解决。</bubble><bubble>先拆出下一步。</bubble>"
        first = "说。" if model == "gemini-carbon" else "我在。"
        return f"<bubble>{first}</bubble><bubble>{short or '嗯'}。</bubble><bubble>先坐一会儿。</bubble>"


def build_engine(*, root: Path, demo_fallback: bool = True) -> LocalChatEngine:
    load_env_file(root / ".env")
    profiles = load_model_profiles()
    router = GatewayRouter.from_profiles(profiles)
    if demo_fallback:
        gateways = router.gateway_map()
        for profile in profiles:
            gateways.setdefault(profile.id, DemoFallbackGateway())
        router = GatewayRouter(gateways, profiles)
    context = DailyContext(
        time_period=os.getenv("JUUS_CONTEXT_TIME_PERIOD", "晚上"),
        weather=os.getenv("JUUS_CONTEXT_WEATHER", "晴"),
        schedule=os.getenv("JUUS_CONTEXT_SCHEDULE", "接下来一小时没有硬安排"),
        energy=os.getenv("JUUS_CONTEXT_ENERGY", "有点累"),
    )
    return LocalChatEngine(router=router, context=context)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Juus native one-on-one local chat prototype")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open", action="store_true", help="open the prototype in the default browser"
    )
    parser.add_argument(
        "--no-demo-fallback",
        action="store_true",
        help="fail when real model backends are not configured",
    )
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[2]
    engine = build_engine(root=root, demo_fallback=not args.no_demo_fallback)
    missing = engine.router.unconfigured_labels()
    if missing and args.no_demo_fallback:
        raise SystemExit("缺少真实模型后端配置: " + ", ".join(missing))
    serve(engine, host=args.host, port=args.port, open_browser=args.open)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
