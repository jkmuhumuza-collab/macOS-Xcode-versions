"""Full-lifecycle test of the CCELAM Project Cost Ledger.

Demonstration project (fictional figures, hand-verified arithmetic):
  Contract sum UGX 900,000,000 | retention 10% capped at 5% | advance
  UGX 120,000,000 recovered at 15% of gross | FIDIC Red Book 1999.
"""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ledger"))

from ledger import LedgerEngine, LedgerError
from ledger_schema import Baseline, BOQLine, LedgerHeader

PASS = 0


def check(label, got, want):
    global PASS
    assert str(got) == str(want), f"{label}: got {got}, expected {want}"
    PASS += 1
    print(f"  ok  {label}: {got}")


header = LedgerHeader(
    ledger_ref="CCELAM/LEDGER/DEMO/2026/001",
    project_ref="DEMO-INFRA-01",
    project_title="Demonstration Infrastructure Project",
    employer="Demonstration Employer Ltd",
    contractor="Demonstration Contractor Ltd",
    engineer="CCELAM NK & Associates",
    contract_form="FIDIC Red Book 1999",
    contract_sum="900000000",
    commencement_date=date(2026, 1, 5),
    time_for_completion_days=365,
    retention_percent="10", retention_limit_percent="5",
    advance_payment="120000000", advance_recovery_percent="15",
)

baseline = Baseline(boq_ref="CCELAM/BOQ/DEMO/2026/001 Rev 0", lines=[
    BOQLine(item_ref="A.1.1", work_section="A — Preliminaries",
            description="Preliminaries and general conditions",
            unit="Item", quantity="1", rate="250000000"),
    BOQLine(item_ref="E.10.1", work_section="E — In-situ concrete",
            description="RC grade C30 in columns and beams", unit="m3",
            quantity="400", rate="850000",
            source_guids=["2N1$demoGUIDcol01", "2N1$demoGUIDbm02"]),
    BOQLine(item_ref="F.10.2", work_section="F — Masonry",
            description="Blockwork 200 mm thick in cement mortar 1:3",
            unit="m2", quantity="2500", rate="95000",
            source_guids=["3M2$demoGUIDwall1"]),
])

print("== Baseline ==")
eng = LedgerEngine.new(header, baseline)
check("measured total", baseline.measured_total, "827500000.00")

print("== IPC No. 1 ==")
m1 = {"E.10.1": "150", "F.10.2": "800", "A.1.1": "0.3"}
f1 = eng.prepare_ipc("2026-03-31", m1)
# work = 150*850000 + 800*95000 + 0.3*250000000 = 278,500,000
check("IPC1 gross to date", f1.gross_todate, "278500000.00")
check("IPC1 retention (10%, under cap)", f1.retention_todate, "27850000.00")
check("IPC1 advance recovery (15%)", f1.advance_recovery_todate, "41775000.00")
check("IPC1 net this certificate", f1.net_this_certificate, "208875000.00")
eng.certify_ipc(f1, m1)

print("== Variation VO-01 ==")
eng.post_variation(
    vo_ref="VO-01", sub_clause="13.3", description="Additional drainage works",
    contractor_claim="64000000", qs_assessment="50000000",
    approved_amount="50000000",
    new_lines=[BOQLine(item_ref="R.12.1", work_section="R — Disposal systems",
                       description="VO-01 additional drainage (star rate)",
                       unit="Sum", quantity="1", rate="50000000")])
check("revised contract sum", eng.revised_contract_sum(), "950000000.00")

print("== IPC No. 2 (with over-measure flag) ==")
m2 = {"E.10.1": "400", "F.10.2": "2600", "A.1.1": "0.8", "R.12.1": "0.6"}
f2 = eng.prepare_ipc("2026-06-30", m2, materials_on_site="10000000")
# work = 340,000,000 + 2600*95000=247,000,000 + 200,000,000 + 30,000,000
#      = 817,000,000 ; gross = + MOS 10,000,000 = 827,000,000
check("IPC2 gross to date", f2.gross_todate, "827000000.00")
# retention raw 82.7M -> capped at 5% x 950M = 47,500,000
check("IPC2 retention capped at 5%", f2.retention_todate, "47500000.00")
# advance recovery 15% x 827M = 124.05M -> capped at advance 120M
check("IPC2 advance fully recovered", f2.advance_recovery_todate,
      "120000000.00")
check("IPC2 net this certificate", f2.net_this_certificate, "450625000.00")
assert any("F.10.2" in fl for fl in f2.remeasure_flags), "over-measure flag"
PASS += 1
print(f"  ok  over-measure flagged: {f2.remeasure_flags[0][:60]}...")
eng.certify_ipc(f2, m2)

print("== Taking-Over (SC 10.1) and first moiety (SC 14.9) ==")
eng.taking_over(toc_ref="CCELAM/TOC/DEMO/2026/001", toc_date="2026-07-15",
                outstanding_works_value="4500000")
check("first moiety released", eng._retention_released(), "23750000.00")

print("== Performance Certificate (SC 11.9) and second moiety ==")
eng.performance_certificate(pc_ref="CCELAM/PC/DEMO/2026/001",
                            pc_date="2027-07-15")
check("retention fully released", eng._retention_released(), "47500000.00")

print("== Final Statement (SC 14.11) ==")
fs = eng.final_statement()
# cash to contractor so far: advance 120M + net certs 659.5M = 779.5M
# entitlement gross 827M -> balance due 47.5M (the released retention)
check("balance due on final certificate",
      fs.payload["balance_due_on_final_certificate"], "47500000.00")

print("== State, out-turn rates, chain ==")
st = eng.state()
check("net certified to date", st.net_certified_todate, "659500000.00")
check("certificates issued", st.certificates_issued, 2)
rates = eng.out_turn_rates()
check("out-turn rate rows", len(rates), 4)
ok, _ = eng.verify_chain()
check("hash chain verifies", ok, True)

print("== Snapshot versioning (supersede, never overwrite) ==")
out = Path("/home/claude/ccelam-pipeline/fixtures")
p0 = eng.snapshot(rev=0, directory=out)
print(f"  ok  issued {p0.name}")
PASS += 1
try:
    eng.snapshot(rev=0, directory=out)
    raise AssertionError("Rev 0 overwrite was permitted")
except LedgerError as e:
    print(f"  ok  overwrite blocked: {e}")
    PASS += 1

print("== Round-trip load + tamper detection ==")
eng2 = LedgerEngine.load(p0)
check("reloaded state matches", eng2.state().net_certified_todate,
      "659500000.00")
import json
data = json.loads(p0.read_text())
data["events"][3]["payload"]["approved_amount"] = "99999999.00"
tampered = out / "tampered.json"
tampered.write_text(json.dumps(data, default=str))
try:
    LedgerEngine.load(tampered)
    raise AssertionError("tampered ledger loaded")
except LedgerError as e:
    print(f"  ok  tamper detected: {e}")
    PASS += 1
tampered.unlink()

print(f"\nALL {PASS} CHECKS PASSED")
