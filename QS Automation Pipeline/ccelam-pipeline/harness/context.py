"""Context inputs: what is available — eligible models, available tools,
and layered permissions (org > workspace > user)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(__file__).resolve().parent / "config"
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class Model:
    id: str
    provider: str
    capabilities: frozenset[str]
    cost_tier: int
    policies: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ArgSpec:
    kind: str                     # path_in | dir_out | str
    required: bool = False
    suffix: str | None = None


@dataclass(frozen=True)
class Tool:
    name: str
    kind: str                     # local | external_acp
    side_effect: str              # read | write
    risk: str
    requires: frozenset[str]
    intents: tuple[str, ...]
    args: dict[str, ArgSpec]
    argv: tuple[str, ...]
    exit_codes: dict[str, str]
    timeout_s: int
    preconditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Permissions:
    """Effective permissions after layering. Allows intersect across
    layers, denies union; the most restrictive layer always wins."""
    root: Path
    allowed_tools: frozenset[str] | None      # None = unrestricted
    denied_tools: frozenset[str]
    allowed_models: frozenset[str] | None
    write_paths: tuple[Path, ...]
    max_risk: str

    def tool_allowed(self, name: str) -> tuple[bool, str]:
        if name in self.denied_tools:
            return False, f"tool '{name}' is denied by policy"
        if self.allowed_tools is not None and name not in self.allowed_tools:
            return False, f"tool '{name}' is not in the effective allow-list"
        return True, ""

    def model_allowed(self, model_id: str) -> bool:
        return self.allowed_models is None or model_id in self.allowed_models


@dataclass
class Context:
    models: list[Model]
    tools: dict[str, Tool]
    permissions: Permissions
    python: str = "python3"
    extra: dict[str, Any] = field(default_factory=dict)


def _allow(values: list[str] | None) -> frozenset[str] | None:
    if values is None or "*" in values:
        return None
    return frozenset(values)


def _intersect(a: frozenset[str] | None,
               b: frozenset[str] | None) -> frozenset[str] | None:
    if a is None:
        return b
    if b is None:
        return a
    return a & b


def layer_permissions(raw: dict[str, Any], base: Path) -> Permissions:
    layers = [raw.get(k, {}) for k in ("org", "workspace", "user")]
    root = (base / raw.get("workspace", {}).get("root", ".")).resolve()

    allowed_tools = allowed_models = None
    denied: set[str] = set()
    max_risk = "high"
    for layer in layers:
        allowed_tools = _intersect(allowed_tools, _allow(layer.get("allow_tools")))
        allowed_models = _intersect(allowed_models, _allow(layer.get("allow_models")))
        denied |= set(layer.get("deny_tools", []))
        r = layer.get("max_risk")
        if r and RISK_ORDER[r] < RISK_ORDER[max_risk]:
            max_risk = r

    write_paths = tuple(
        (root / p).resolve()
        for p in raw.get("workspace", {}).get("write_paths", []))
    return Permissions(root, allowed_tools, frozenset(denied),
                       allowed_models, write_paths, max_risk)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_context(config_dir: Path = CONFIG_DIR,
                 permissions: dict[str, Any] | None = None,
                 root: Path = PIPELINE_ROOT,
                 python: str = "python3") -> Context:
    models = [Model(m["id"], m["provider"], frozenset(m["capabilities"]),
                    m["cost_tier"], frozenset(m.get("policies", [])))
              for m in _read(config_dir / "models.json")["models"]]
    tools = {}
    for t in _read(config_dir / "tools.json")["tools"]:
        tools[t["name"]] = Tool(
            name=t["name"], kind=t["kind"], side_effect=t["side_effect"],
            risk=t["risk"], requires=frozenset(t.get("requires", [])),
            intents=tuple(t.get("intents", [])),
            args={k: ArgSpec(**v) for k, v in t.get("args", {}).items()},
            argv=tuple(t.get("argv", [])),
            exit_codes=dict(t.get("exit_codes", {})),
            timeout_s=int(t.get("timeout_s", 60)),
            preconditions=tuple(t.get("preconditions", [])))
    raw_perms = permissions if permissions is not None \
        else _read(config_dir / "permissions.json")
    return Context(models, tools, layer_permissions(raw_perms, root), python)
