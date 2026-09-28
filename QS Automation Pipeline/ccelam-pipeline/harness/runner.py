"""Tool runs in the harness: argv rendered from the validated selection,
executed as a subprocess (never through a shell), bounded by timeout."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

from .context import Context, Tool
from .validation import resolve_arg


@dataclass
class StepResult:
    tool: str
    argv: list[str]
    exit_code: int | None
    outcome: str                  # PASS | WARN | FAIL | ERROR | TIMEOUT
    stdout: str
    stderr: str
    duration_s: float


def render_argv(ctx: Context, tool: Tool, args: dict[str, str]) -> list[str]:
    out: list[str] = []
    skip_next = False
    for i, tok in enumerate(tool.argv):
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("?"):
            # optional flag: emit "--flag value" only when the arg is set
            name = tool.argv[i + 1][len("{arg:"):-1]
            if args.get(name):
                out += [tok[1:], str(resolve_arg(ctx, args[name]))]
            skip_next = True
            continue
        tok = tok.replace("{python}", ctx.python) \
                 .replace("{root}", str(ctx.permissions.root))
        if tok.startswith("{arg:"):
            name = tok[len("{arg:"):-1]
            spec = tool.args[name]
            tok = str(resolve_arg(ctx, args[name])) \
                if spec.kind in ("path_in", "dir_out") else str(args[name])
        out.append(tok)
    return out


def run_step(ctx: Context, tool: Tool, args: dict[str, str]) -> StepResult:
    argv = render_argv(ctx, tool, args)
    t0 = time.monotonic()
    try:
        cp = subprocess.run(argv, capture_output=True, text=True,
                            timeout=tool.timeout_s, cwd=ctx.permissions.root)
    except subprocess.TimeoutExpired as exc:
        return StepResult(tool.name, argv, None, "TIMEOUT",
                          exc.stdout or "", exc.stderr or "",
                          round(time.monotonic() - t0, 3))
    outcome = tool.exit_codes.get(str(cp.returncode), "ERROR")
    return StepResult(tool.name, argv, cp.returncode, outcome, cp.stdout,
                      cp.stderr, round(time.monotonic() - t0, 3))
