"""CLI:  python3 -m harness run "<intent>" [--tool NAME] [--arg k=v ...]
        python3 -m harness plan "<intent>" [--tool NAME] [--arg k=v ...]
        python3 -m harness verify
        python3 -m harness context

Exit codes: 0 PASS, 1 WARN, 2 FAIL/ERROR, 3 REFUSED/UNSELECTED.
Run from the ccelam-pipeline directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .context import load_context
from .harness import Harness
from .selector import SelectionError, select
from .validation import validate

EXIT = {"PASS": 0, "WARN": 1, "FAIL": 2, "ERROR": 2,
        "REFUSED": 3, "UNSELECTED": 3}


def _args(pairs: list[str]) -> dict[str, str]:
    out = {}
    for p in pairs:
        k, sep, v = p.partition("=")
        if not sep:
            raise SystemExit(f"--arg expects key=value, got '{p}'")
        out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="harness")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "plan"):
        sp = sub.add_parser(name)
        sp.add_argument("intent")
        sp.add_argument("--tool")
        sp.add_argument("--arg", action="append", default=[])
    sub.add_parser("verify")
    sub.add_parser("context")
    a = ap.parse_args(argv)

    ctx = load_context(python=sys.executable)
    h = Harness(ctx)

    if a.cmd == "context":
        print(json.dumps({
            "models": [m.id for m in ctx.models],
            "tools": {n: {"kind": t.kind, "side_effect": t.side_effect,
                          "risk": t.risk} for n, t in ctx.tools.items()},
            "permissions": {
                "root": str(ctx.permissions.root),
                "allowed_tools": sorted(ctx.permissions.allowed_tools or ["*"]),
                "denied_tools": sorted(ctx.permissions.denied_tools),
                "max_risk": ctx.permissions.max_risk,
                "write_paths": [str(p) for p in ctx.permissions.write_paths]}},
            indent=2))
        return 0

    if a.cmd == "verify":
        ok, broken = h.evidence.verify()
        print(json.dumps({"evidence_log": str(h.evidence.path), "intact": ok,
                          "broken_at": broken,
                          "records": len(h.evidence.records())}))
        return 0 if ok else 2

    if a.cmd == "plan":        # dry run: select + validate, execute nothing
        try:
            sel = select(ctx, a.intent, _args(a.arg), a.tool)
        except SelectionError as exc:
            print(json.dumps({"status": "UNSELECTED", "reason": str(exc)}))
            return 3
        d = validate(ctx, sel)
        print(json.dumps({"selection": asdict(sel), "validation": asdict(d)},
                         indent=2))
        return 0 if d.allowed else 3

    report = h.run(a.intent, _args(a.arg), a.tool)
    print(report.to_json())
    return EXIT[report.status]


if __name__ == "__main__":
    sys.exit(main())
