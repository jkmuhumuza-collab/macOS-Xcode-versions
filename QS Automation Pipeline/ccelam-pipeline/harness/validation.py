"""Host validation: policy, safety, scope — enforced before any tool runs.

Selection is not permission. Every step in the plan is validated up
front; one refusal blocks the whole plan (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .context import RISK_ORDER, Context, Tool
from .selector import Selection


@dataclass
class Decision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)   # refusals
    checks: list[dict] = field(default_factory=list)   # full audit trail

    def record(self, layer: str, step: str, ok: bool, detail: str):
        self.checks.append({"layer": layer, "step": step,
                            "result": "PASS" if ok else "REFUSE",
                            "detail": detail})
        if not ok:
            self.allowed = False
            self.reasons.append(f"[{layer}] {step}: {detail}")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_arg(ctx: Context, value: str) -> Path:
    p = Path(value)
    return (p if p.is_absolute() else ctx.permissions.root / p).resolve()


def _validate_step(ctx: Context, tool: Tool, args: dict[str, str],
                   d: Decision):
    perms = ctx.permissions
    name = tool.name

    # --- policy -----------------------------------------------------
    if tool.kind == "external_acp":
        d.record("policy", name, False,
                 "external ACP loop is provider-owned and stays outside the "
                 "harness boundary — select-only, never executed here")
        return
    ok, why = perms.tool_allowed(name)
    d.record("policy", name, ok, why or "tool permitted at org, workspace and user level")

    # --- safety -----------------------------------------------------
    risk_ok = RISK_ORDER[tool.risk] <= RISK_ORDER[perms.max_risk]
    d.record("safety", name, risk_ok,
             f"risk '{tool.risk}' within ceiling '{perms.max_risk}'" if risk_ok
             else f"risk '{tool.risk}' exceeds ceiling '{perms.max_risk}'")
    if tool.side_effect == "write":
        has_out = any(s.kind == "dir_out" for s in tool.args.values())
        d.record("safety", name, has_out and bool(perms.write_paths),
                 "write tool declares its output scope" if has_out and perms.write_paths
                 else "write tool without a declared, permitted output scope")

    # --- scope ------------------------------------------------------
    for spec_name, spec in tool.args.items():
        value = args.get(spec_name)
        if value in (None, ""):
            if spec.required:
                d.record("scope", name, False, f"missing required arg '{spec_name}'")
            continue
        if spec.kind in ("path_in", "dir_out"):
            p = resolve_arg(ctx, value)
            if not _inside(p, perms.root):
                d.record("scope", name, False,
                         f"'{spec_name}' resolves outside the workspace root: {p}")
                continue
            if spec.suffix and p.suffix.lower() != spec.suffix:
                d.record("scope", name, False,
                         f"'{spec_name}' must be a {spec.suffix} file")
                continue
            if spec.kind == "path_in" and not p.is_file():
                d.record("scope", name, False, f"'{spec_name}' does not exist: {p}")
                continue
            if spec.kind == "dir_out" and not any(
                    _inside(p, w) for w in perms.write_paths):
                d.record("scope", name, False,
                         f"'{spec_name}' is outside the permitted write paths")
                continue
            d.record("scope", name, True, f"'{spec_name}' in scope")


def validate(ctx: Context, sel: Selection) -> Decision:
    d = Decision(allowed=True)
    model_ok = ctx.permissions.model_allowed(sel.model)
    d.record("policy", "model", model_ok,
             f"model '{sel.model}' permitted" if model_ok
             else f"model '{sel.model}' is not permitted")
    certifying = any(ctx.tools[s].side_effect == "write" for s in sel.plan.steps)
    model = next(m for m in ctx.models if m.id == sel.model)
    if certifying and "no-certification" in model.policies:
        d.record("policy", "model", False,
                 f"model '{sel.model}' carries a no-certification policy")

    used: set[str] = set()
    for step in sel.plan.steps:
        tool = ctx.tools[step]
        step_args = {k: v for k, v in sel.args.items() if k in tool.args}
        used |= set(step_args)
        _validate_step(ctx, tool, step_args, d)
    stray = set(sel.args) - used
    if stray:
        d.record("scope", "args", False,
                 f"args not accepted by any plan step: {sorted(stray)}")
    return d
