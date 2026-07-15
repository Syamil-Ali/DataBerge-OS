from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AgentSpec:
    name: str
    role: str
    instructions: str


AgentFactory = Callable[[AgentSpec, list[Any] | None], Any]
ToolkitFactory = Callable[..., Any]
