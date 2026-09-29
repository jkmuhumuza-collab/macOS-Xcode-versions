"""The control plane: select -> validate -> execute -> evidence.

The harness decides what to run, validates it, and captures evidence.
It records which model a plan was selected for, but never performs
inference or calls a provider: those internals stay with the provider.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .context import Context
from .evidence import EvidenceLog, diff_trees, snapshot_tree
from .runner import StepResult, run_step
from .selector import Selection, SelectionError, select
from .validation import validate

LOG_TAIL = 4000   # characters of stdout/stderr kept per step in evidence


@dataclass
class RunReport:
    status: str                   # PASS | WARN | FAIL | REFUSED | UNSELECTED | ERROR
    intent: str
    selection: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    diff: dict[str, list] | None = None
    scope_breaches: list[str] = field(default_factory=list)
    evidence_seq: int | None = None
    evidence_hash: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


_RANK = {"PASS": 0, "WARN": 1, "FAIL": 2, "ERROR": 3, "TIMEOUT": 3}


class Harness:
    def __init__(self, ctx: Context, evidence_dir: Path | None = None):
        self.ctx = ctx
        self.evidence = EvidenceLog(
            evidence_dir or ctx.permissions.root / "evidence")

    def run(self, intent: str, args: dict[str, str] | None = None,
            tool: str | None = None) -> RunReport:
        # 1. select: model + tool + plan (a proposal, not a permission)
        try:
            sel = select(self.ctx, intent, args, tool)
        except SelectionError as exc:
            return self._close(RunReport("UNSELECTED", intent,
                                         validation={"reasons": [str(exc)]}))
        report = RunReport("PASS", intent, selection=asdict(sel))

        # 2. host validation: policy, safety, scope — before any tool runs
        decision = validate(self.ctx, sel)
        report.validation = asdict(decision)
        if not decision.allowed:
            report.status = "REFUSED"
            return self._close(report)

        # 3. tool runs in the harness, with a before/after tree for the diff
        root = self.ctx.permissions.root
        exclude = [self.evidence.dir]
        before = snapshot_tree([root], exclude)
        for step in sel.plan.steps:
            t = self.ctx.tools[step]
            res = run_step(self.ctx, t, {k: v for k, v in sel.args.items()
                                         if k in t.args})
            report.steps.append(self._step_record(res))
            if _RANK[res.outcome] > _RANK[report.status]:
                report.status = "ERROR" if res.outcome == "TIMEOUT" else res.outcome
            if res.outcome not in ("PASS", "WARN"):
                break     # a failed precondition stops the plan
        after = snapshot_tree([root], exclude)

        # 4. evidence: results, logs, artifacts, diff — and a breach check
        report.diff = diff_trees(before, after)
        report.scope_breaches = self._breaches(sel, report.diff)
        if report.scope_breaches:
            report.status = "FAIL"
        return self._close(report)

    def _breaches(self, sel: Selection, diff: dict[str, list]) -> list[str]:
        writes = any(self.ctx.tools[s].side_effect == "write"
                     for s in sel.plan.steps)
        allowed = self.ctx.permissions.write_paths if writes else ()
        changed = [p for p, _ in diff["added"]] + \
                  [p for p, _ in diff["modified"]] + list(diff["removed"])
        return [p for p in changed
                if not any(Path(p).is_relative_to(w) for w in allowed)]

    @staticmethod
    def _step_record(res: StepResult) -> dict[str, Any]:
        rec = asdict(res)
        rec["stdout"] = res.stdout[-LOG_TAIL:]
        rec["stderr"] = res.stderr[-LOG_TAIL:]
        return rec

    def _close(self, report: RunReport) -> RunReport:
        body = asdict(report)
        body.pop("evidence_seq"), body.pop("evidence_hash")
        rec = self.evidence.append({"kind": "harness-run", **body})
        report.evidence_seq, report.evidence_hash = rec["seq"], rec["hash"]
        return report
