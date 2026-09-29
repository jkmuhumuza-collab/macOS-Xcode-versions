"""Tests for the CCELAM coding harness: select -> validate -> run -> evidence.

Runs against a throwaway copy of the pipeline so the repository (rates,
fixtures, evidence) is never touched. Run: python3 tests/test_harness.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))

from harness import Harness, load_context, select, validate  # noqa: E402
from harness.context import Tool  # noqa: E402
from harness.evidence import EvidenceError, EvidenceLog  # noqa: E402
from harness.selector import SelectionError  # noqa: E402

PASS = 0


def check(label, got, want):
    global PASS
    assert got == want, f"{label}: got {got!r}, expected {want!r}"
    PASS += 1
    print(f"  ok  {label}: {got}")


_tmp = tempfile.TemporaryDirectory()
ROOT = Path(_tmp.name) / "pipeline"
shutil.copytree(SRC, ROOT, ignore=shutil.ignore_patterns(
    "__pycache__", "evidence", ".DS_Store"))
CONFIG = ROOT / "harness" / "config"
BASE_PERMS = json.loads((CONFIG / "permissions.json").read_text())
LEDGER = "fixtures/CCELAM_LEDGER_DEMO_2026_001_Rev_0.json"


def ctx_with(**overrides):
    perms = json.loads(json.dumps(BASE_PERMS))
    for layer, values in overrides.items():
        perms.setdefault(layer, {}).update(values)
    return load_context(CONFIG, perms, ROOT, sys.executable)


def harness(ctx, name):
    return Harness(ctx, Path(_tmp.name) / f"evidence_{name}")


ctx = ctx_with()

print("== Selection: model + tool + plan ==")
s = select(ctx, "validate the ifc model at intake", {"ifc": "fixtures/g1_good.ifc"})
check("intent picks tool", s.tool, "g1_intake_gate")
check("cheapest capable model", s.model, "claude-sonnet-5")
s = select(ctx, "issue out-turn rates register")
check("preconditions planned first", s.plan.steps,
      ["ledger_verify", "outturn_rates_hook"])
check("plan capability lifts model", s.model, "claude-opus-5-5")
try:
    select(ctx, "make me a sandwich")
    raise AssertionError("unmatched intent was selected")
except SelectionError as e:
    print(f"  ok  unmatched intent rejected: {e}")
    PASS += 1

print("== Host validation: selection is not permission ==")
denied = ctx_with(org={"deny_tools": ["g1_intake_gate"]})
r = harness(denied, "deny").run("validate ifc model",
                                 {"ifc": "fixtures/g1_good.ifc"})
check("org deny refuses a selected tool", r.status, "REFUSED")
check("nothing executed", r.steps, [])
check("refusal is still evidenced", r.evidence_seq, 0)

narrowed = ctx_with(user={"allow_tools": ["ledger_tests"]})
check("user layer narrows (intersect)",
      validate(narrowed, select(narrowed, "run ledger tests")).allowed, True)
check("user layer blocks the rest",
      validate(narrowed, select(narrowed, "validate ifc model",
                                {"ifc": "fixtures/g1_good.ifc"})).allowed, False)

low = ctx_with(org={"max_risk": "low"})
d = validate(low, select(low, "issue outturn rates register",
                         {"ledger": LEDGER, "register_dir": "rates"}))
check("risk ceiling refuses medium-risk write", d.allowed, False)

d = validate(ctx, select(ctx, "validate ifc model", {"ifc": "../../etc/passwd"}))
check("path escape refused", d.allowed, False)
d = validate(ctx, select(ctx, "issue outturn rates register",
                         {"ledger": LEDGER, "register_dir": "fixtures"}))
check("write outside write_paths refused", d.allowed, False)
d = validate(ctx, select(ctx, "validate ifc model", {"ifc": LEDGER}))
check("wrong file type refused", d.allowed, False)
d = validate(ctx, select(ctx, "validate ifc model",
                         {"ifc": "fixtures/g1_good.ifc", "rm": "-rf"}))
check("stray args refused", d.allowed, False)

print("== Boundary: provider-owned loops stay with the provider ==")
open_org = ctx_with(org={"deny_tools": []}, workspace={"allow_tools": ["*"]})
r = harness(open_org, "acp").run("sync external connector")
check("external ACP never executed", (r.status, r.steps), ("REFUSED", []))
check("boundary reason recorded",
      any("provider-owned" in x for x in r.validation["reasons"]), True)

print("== Tool runs + evidence ==")
h = harness(ctx, "runs")
r = h.run("validate ifc model", {"ifc": "fixtures/g1_bad.ifc"})
check("G1 bad model -> FAIL", r.status, "FAIL")
check("gate exit code captured", r.steps[0]["exit_code"], 2)
r = h.run("validate ifc model", {"ifc": "fixtures/g1_good.ifc"})
check("G1 good model -> PASS", r.status, "PASS")
check("gate log captured", '"status": "PASS"' in r.steps[0]["stdout"], True)
r = h.run("run the ledger regression tests")
check("ledger tests pass in harness", r.status, "PASS")
check("read-only run leaves no diff", r.diff["added"] + r.diff["modified"], [])

r = h.run("issue outturn rates register",
          {"ledger": LEDGER, "register_dir": "rates/closing",
           "library": "rates/rate_library_demo.csv"})
check("write plan passes", [(x["tool"], x["outcome"]) for x in r.steps],
      [("ledger_verify", "PASS"), ("outturn_rates_hook", "PASS")])
added = [Path(p).name for p, _ in r.diff["added"]]
check("diff shows issued register", added, ["outturn_evidence_Rev_0.csv"])
check("write within scope", r.scope_breaches, [])

print("== Post-run breach detection ==")
rogue = Tool(name="rogue", kind="local", side_effect="read", risk="low",
             requires=frozenset(), intents=("rogue",), args={},
             argv=("{python}", "-c",
                   "open('fixtures/rogue.txt','w').write('x')"),
             exit_codes={"0": "PASS"}, timeout_s=30)
ctx_rogue = ctx_with(workspace={"allow_tools": ["*"]})
ctx_rogue.tools["rogue"] = rogue
r = harness(ctx_rogue, "rogue").run("rogue")
check("undeclared write flagged", r.status, "FAIL")
check("breach path recorded", [Path(p).name for p in r.scope_breaches],
      ["rogue.txt"])

print("== Evidence chain ==")
log = EvidenceLog(Path(_tmp.name) / "evidence_runs")
check("chain verifies", log.verify(), (True, None))
check("one record per run", len(log.records()), 4)
lines = log.path.read_text().splitlines()
rec = json.loads(lines[0])
check("record 0 is the G1 FAIL", rec["status"], "FAIL")
rec["status"] = "PASS"                       # rewrite a FAIL as a PASS
lines[0] = json.dumps(rec, sort_keys=True)
log.path.write_text("\n".join(lines) + "\n")
check("tamper detected", log.verify(), (False, 0))
try:
    log.append({"kind": "harness-run"})
    raise AssertionError("append on a broken chain was permitted")
except EvidenceError as e:
    print(f"  ok  append blocked: {e}")
    PASS += 1

_tmp.cleanup()
print(f"\nALL {PASS} CHECKS PASSED")
