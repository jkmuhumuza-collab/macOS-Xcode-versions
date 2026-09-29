# CCELAM Coding Harness

The harness sits between what someone asks for and what actually runs.
It works out the right action from the current state and keeps
verifiable evidence of what happened.

```
CONTEXT INPUTS          HARNESS CONTROL PLANE                         OUTCOME
eligible models ─┐
available tools ─┼─► select ──► host validation ──► tool runs ──► build, test, diff
permissions ─────┘   model +    policy · safety ·   in the         results · logs ·
                     tool+plan  scope               harness        artifacts
```

**Selection is not permission.** The selector can choose a model, tool and
plan, and host validation can still refuse it before any tool runs.
Validation checks every step of the plan first. If any step is refused, the
whole plan is refused (fail closed).

| Stage | Module | What it does |
|---|---|---|
| Context inputs | `context.py`, `config/*.json` | Models (capabilities, cost tier, policies), tools (argv, arg kinds, risk, side effect, preconditions), and permissions layered org › workspace › user. Allow-lists are intersected and deny-lists combined, so the most restrictive layer wins. |
| Select | `selector.py` | Matches the intent to a tool by keyword, or takes the tool you name. Adds any preconditions to the plan (for example, `outturn_rates_hook` needs `ledger_verify` first). Picks the lowest-cost model that has the capabilities the plan needs. |
| Host validation | `validation.py` | **Policy:** is the tool allowed or denied, and is the model allowed (a `no-certification` model cannot run a write plan)? **Safety:** is the tool within the risk ceiling, and does a write tool declare its output scope? **Scope:** paths stay inside the workspace root, outputs stay inside the write paths, file types match, and stray arguments are refused. |
| Tool runs | `runner.py` | Runs the command as a subprocess with no shell and a timeout. Exit codes map to PASS / WARN / FAIL. |
| Evidence | `evidence.py`, `harness.py` | Records stdout/stderr, exit codes, and a before/after SHA-256 diff of the workspace. It also checks after the run for breaches: a write outside the declared scope turns the run into a FAIL. Every run, including refusals, is appended to a hash-chained `evidence/evidence_log.jsonl`. Edits are detected, and appending to a broken chain is blocked. |

**The boundary.** Provider-owned internals stay outside the harness: model
runtime, provider tool execution, telemetry, and external ACP loops. The
harness records which model a plan was selected for, but it never runs
inference. A tool with `kind: external_acp` can be selected, but it is
always refused for execution here.

## Usage (from `ccelam-pipeline/`)

```
python3 -m harness context                       # what is available, effective permissions
python3 -m harness plan "validate ifc model" --arg ifc=fixtures/g1_good.ifc   # dry run
python3 -m harness run  "validate ifc model" --arg ifc=fixtures/g1_good.ifc
python3 -m harness run  "run the ledger regression tests"
python3 -m harness run  "issue outturn rates register" \
    --arg ledger=fixtures/CCELAM_LEDGER_DEMO_2026_001_Rev_0.json \
    --arg register_dir=rates --arg library=rates/rate_library_demo.csv
python3 -m harness verify                        # check the evidence chain
```

Exit codes: 0 PASS · 1 WARN · 2 FAIL/ERROR · 3 REFUSED/UNSELECTED.

To add a tool, register it in `config/tools.json` with its argv, argument
kinds, risk, side effect and exit-code map. Then allow it in
`config/permissions.json`. No code change is needed.

Tests: `python3 tests/test_harness.py` (33 checks; they run on a temporary
copy of the pipeline, so the repository is never touched).

**Limit:** the diff covers the workspace root only. The harness cannot
observe writes a tool makes outside the root. Scope validation stops paths
you supply from pointing outside, but a tool that writes to a hard-coded
external path won't show up in the diff.
