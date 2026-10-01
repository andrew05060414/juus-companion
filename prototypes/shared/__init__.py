"""Shared contracts used by both M0 prototypes."""

from .domain import Character, ChatMessage, Group, GroupEvent, GroupRun
from .model_gateway import ModelGateway, OpenAICompatibleGateway

__all__ = [
    "Character",
    "ChatMessage",
    "Group",
    "GroupEvent",
    "GroupRun",
    "ModelGateway",
    "OpenAICompatibleGateway",
]
