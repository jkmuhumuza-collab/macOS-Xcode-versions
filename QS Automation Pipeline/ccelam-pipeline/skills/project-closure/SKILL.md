---
name: project-closure
description: >
  Produce project closure documentation under FIDIC frameworks: Final Account /
  Final Statement (Sub-Clause 14.11), written discharge (14.12), Final Payment
  Certificate (14.13), and the CCELAM Project Closure Report (cost performance
  analysis, variation and claims history, out-turn rate analysis, lessons
  learned, archive and handover schedule). Use this skill whenever the user
  asks to close out, finalise, reconcile, or wrap up a project commercially.
  Also trigger when the user mentions "final account", "final statement",
  "final certificate", "FPC", "Sub-Clause 14.11", "14.13", "discharge",
  "close-out report", "closure report", "project close-out", "out-turn cost",
  "cost performance report", "reconciliation of the account", "agree the final
  account", or any reference to settling the contract sum at completion.
  Trigger even for informal requests like "let's close the account on this
  job", "what did the project finally cost", or "prepare the close-out pack".
---

# Project Closure Skill

Produces the closing instruments of the CCELAM drawings-to-closure pipeline.
The Final Account is a closing READ of the project cost ledger: every line
reconciles to a certificate, every certificate to a BOQ item, every item to
its source GlobalIds. Nothing is re-keyed.

---

## Step 0: Preconditions

- Performance Certificate issued (the ledger enforces this — a
  FINAL_STATEMENT event cannot be appended without it)
- Ledger loads cleanly and `verify_chain()` passes; a broken chain stops
  everything until investigated
- All VOs at status approved/rejected (none left "proposed"); all claims
  determined or formally withdrawn; all retention release events posted

## Step 1: Identify the Instrument

| Instrument | Key Sub-Clauses (1999) | Output | Reference file |
|---|---|---|---|
| Final Account / Final Statement | 14.11 | Excel (.xlsx) + Word (.docx) | `references/final-account.md` |
| Written discharge | 14.12 | Word (.docx) | `references/final-account.md` |
| Final Payment Certificate | 14.13 | Word (.docx) + PDF | `references/final-account.md` |
| Project Closure Report | — (CCELAM instrument) | Word (.docx) + PDF | `references/closure-report.md` |

Read the relevant reference file BEFORE producing output.

## Step 2: Ledger Integration

```python
from ledger import LedgerEngine
eng = LedgerEngine.load("CCELAM_LEDGER_<PROJECT>_Rev_N.json")
ok, broken = eng.verify_chain()        # must be (True, None)
fs = eng.final_statement()             # posts the FINAL_STATEMENT event
state = eng.state()                    # closing commercial position
rates = eng.out_turn_rates()           # feedback dataset for rate library
eng.snapshot(rev=N+1, directory=...)   # the closing snapshot
```

After the closing snapshot, run the out-turn rates hook
(`hooks/outturn_rates_hook.py`) so the certified rates flow back to the
Kampala rate library — this is what closes the practice's OODA loop:
this project's certified out-turn becomes the next project's pricing
evidence.

## Step 3: The 56/28-Day Machinery (diarise all of it)

- Draft Final Statement from the Contractor: within **56 days** of the
  Performance Certificate (14.11)
- Agreement or the Engineer's determination of any disputed parts
- Written discharge from the Contractor (14.12) — effective when the Final
  Payment Certificate amount is paid and the Performance Security returned
- Final Payment Certificate: within **28 days** of receiving the Final
  Statement and discharge (14.13)
- Employer payment: within **56 days** of the FPC (14.7(c))

Enter every deadline in the notice register on the day the trigger occurs.

## Step 4: House Standards

- CCELAM brand and document conventions as per practice standard; document
  refs `CCELAM/[FA|FPC|CLO]/[PROJECT]/[YEAR]/[SEQ] Rev [N]`; mandatory
  sign-off block; British English, third-person passive voice
- Read `/mnt/skills/public/docx/SKILL.md` and `/mnt/skills/public/xlsx/SKILL.md`
  before producing files; `arithmetic_verify` applies to every workbook

## Step 5: Quality Check

- [ ] Final contract sum = original sum + approved VOs + determined claims,
      and equals the ledger's `revised_contract_sum()` exactly
- [ ] Reconciliation closes to zero: gross executed − (advance + Σ net
      certificates + balance due) = 0
- [ ] Every VO and claim in the account traces to its ledger event ref
- [ ] Out-turn rates exported and the rate library revision issued
- [ ] Closure report cost-performance figures match the Final Account
- [ ] Archive schedule lists the closing ledger snapshot Rev and its hash
