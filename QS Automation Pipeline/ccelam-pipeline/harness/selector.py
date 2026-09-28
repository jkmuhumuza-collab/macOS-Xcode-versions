"""Selection: choose model + tool + plan from the context.

Selection never grants anything — it proposes. Host validation decides.
Model eligibility here is capability-only (cheapest capable model); the
permission check on the chosen model belongs to validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .context import Context, Model, Tool


class SelectionError(Exception):
    pass


@dataclass
class Plan:
    steps: list[str]              # tool names, preconditions first


@dataclass
class Selection:
    intent: str
    tool: str
    model: str
    plan: Plan
    args: dict[str, str]
    rationale: list[str] = field(default_factory=list)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9\-]*", text.lower()))


def pick_tool(ctx: Context, intent: str) -> tuple[Tool, int]:
    words = _tokens(intent)
    scored = sorted(
        ((len(words & set(t.intents)), t.name) for t in ctx.tools.values()),
        key=lambda s: (-s[0], s[1]))
    if not scored or scored[0][0] == 0:
        raise SelectionError(f"no tool matches intent '{intent}'")
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        raise SelectionError(
            f"intent '{intent}' is ambiguous between '{scored[0][1]}' and "
            f"'{scored[1][1]}' — name the tool explicitly")
    return ctx.tools[scored[0][1]], scored[0][0]


def pick_model(ctx: Context, requires: frozenset[str]) -> Model:
    capable = [m for m in ctx.models if requires <= m.capabilities]
    if not capable:
        raise SelectionError(f"no eligible model has capabilities {sorted(requires)}")
    return min(capable, key=lambda m: (m.cost_tier, m.id))


def build_plan(ctx: Context, tool: Tool) -> Plan:
    order: list[str] = []

    def visit(name: str, trail: tuple[str, ...]):
        if name in trail:
            raise SelectionError(f"precondition cycle: {' -> '.join(trail + (name,))}")
        if name not in ctx.tools:
            raise SelectionError(f"precondition '{name}' is not an available tool")
        for pre in ctx.tools[name].preconditions:
            visit(pre, trail + (name,))
        if name not in order:
            order.append(name)

    visit(tool.name, ())
    return Plan(order)


def select(ctx: Context, intent: str, args: dict[str, str] | None = None,
           tool: str | None = None) -> Selection:
    rationale = []
    if tool:
        if tool not in ctx.tools:
            raise SelectionError(f"tool '{tool}' is not available")
        chosen = ctx.tools[tool]
        rationale.append(f"tool '{tool}' named explicitly")
    else:
        chosen, score = pick_tool(ctx, intent)
        rationale.append(f"tool '{chosen.name}' matched {score} intent keyword(s)")
    plan = build_plan(ctx, chosen)
    requires = frozenset().union(*(ctx.tools[s].requires for s in plan.steps))
    model = pick_model(ctx, requires)
    rationale.append(f"model '{model.id}' is the lowest-cost model with "
                     f"{sorted(requires)}")
    if len(plan.steps) > 1:
        rationale.append(f"plan adds preconditions: {plan.steps[:-1]}")
    return Selection(intent, chosen.name, model.id, plan, dict(args or {}),
                     rationale)
