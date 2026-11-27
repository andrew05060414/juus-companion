"""Environment-configured model profiles for local one-on-one chat."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from prototypes.shared.model_gateway import ModelGateway, OpenAICompatibleGateway


@dataclass(frozen=True, slots=True)
class ModelProfile:
    id: str
    label: str
    model_name: str
    base_url: str | None
    api_key_env: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url)


def load_model_profiles(environ: Mapping[str, str] | None = None) -> tuple[ModelProfile, ...]:
    """Load two logical comparison lanes without hardcoding endpoints or secrets."""

    env = os.environ if environ is None else environ
    shared_key_env = (
        "JUUS_MODEL_API_KEY"
        if env.get("JUUS_MODEL_API_KEY") or not env.get("NINEROUTER_KEY")
        else "NINEROUTER_KEY"
    )

    def profile(prefix: str, profile_id: str, label: str, default_model: str) -> ModelProfile:
        return ModelProfile(
            id=profile_id,
            label=label,
            model_name=env.get(f"JUUS_{prefix}_MODEL", default_model).strip() or default_model,
            base_url=(
                env.get(f"JUUS_{prefix}_BASE_URL")
                or env.get("JUUS_MODEL_BASE_URL")
                or env.get("NINEROUTER_URL")
                or ""
            ).strip()
            or None,
            api_key_env=f"JUUS_{prefix}_API_KEY"
            if env.get(f"JUUS_{prefix}_API_KEY")
            else shared_key_env,
        )

    return (
        profile("GEMINI", "gemini-carbon", "Gemini 4 Carbon", "gemini-4-carbon"),
        profile(
            "SONNET",
            "sonnet",
            "Sonnet",
            env.get("NINEROUTER_SONNET_MODEL", "sonnet").strip() or "sonnet",
        ),
    )


class GatewayRouter:
    def __init__(
        self, gateways: Mapping[str, ModelGateway], profiles: Sequence[ModelProfile]
    ) -> None:
        self._gateways = dict(gateways)
        self.profiles = tuple(profiles)

    def complete(
        self, model_id: str, *, messages: Sequence[Mapping[str, str]], metadata: Mapping[str, str]
    ) -> str:
        try:
            gateway = self._gateways[model_id]
        except KeyError as exc:
            raise RuntimeError(f"unknown model profile: {model_id}") from exc
        return gateway.complete(messages=messages, metadata=metadata)

    @classmethod
    def from_profiles(
        cls,
        profiles: Sequence[ModelProfile],
        *,
        timeout_seconds: float = 45.0,
    ) -> GatewayRouter:
        gateways: dict[str, ModelGateway] = {}
        for profile in profiles:
            if profile.base_url:
                gateways[profile.id] = OpenAICompatibleGateway(
                    profile.base_url,
                    model=profile.model_name,
                    api_key_env=profile.api_key_env,
                    timeout_seconds=timeout_seconds,
                )
        return cls(gateways, profiles)

    def gateway_map(self) -> dict[str, ModelGateway]:
        return dict(self._gateways)

    def unconfigured_labels(self) -> list[str]:
        return [profile.label for profile in self.profiles if not profile.configured]
