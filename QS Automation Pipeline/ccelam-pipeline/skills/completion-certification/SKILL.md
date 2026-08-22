---
name: completion-certification
description: >
  Produce professional completion certification documents under FIDIC contract
  frameworks: Taking-Over Certificates (Sub-Clause 10.1, including sections or
  parts under 10.2), Outstanding Works & Defects Schedules, Defects Notification
  Period instruments (11.1–11.4), Performance Certificates (11.9), and the
  associated retention moiety releases (14.9). Use this skill whenever the user
  asks to certify, prepare, assess, or document practical completion, taking
  over, substantial completion, defects, snagging, the defects liability or
  notification period, final completion, or a performance certificate. Also
  trigger when the user mentions "Taking-Over Certificate", "TOC", "practical
  completion", "PC certificate", "defects schedule", "snag list", "punch list",
  "DNP", "defects liability period", "DLP", "retention release", "first
  moiety", "second moiety", "Sub-Clause 10.1", "Sub-Clause 11.9", or any
  reference to completion or handover certification. Trigger even for informal
  requests like "the contractor says they're done — prepare the certificate",
  "draft the snag list from these site notes", or "release the retention".
---

# Completion Certification Skill

Produces the completion-stage instruments of the CCELAM drawings-to-closure
pipeline: Taking-Over Certificate, Outstanding Works & Defects Schedule, and
Performance Certificate, with the retention consequences computed from the
project cost ledger — never re-keyed.

---

## Step 0: Establish Context

Confirm or collect (use memory/prior context before asking):

- **Contract form and edition** (FIDIC Red/Yellow/Silver, 1999 or 2017 —
  note 2017 renumbering where relevant)
- **Ledger file** for the project (`CCELAM/LEDGER/[PROJECT]/...Rev N.json`).
  If a ledger exists, ALL retention and value figures come from it via
  `ledger.py` (`taking_over()`, `performance_certificate()`, `state()`).
  If none exists, collect contract sum, retention %, retention held, and
  certificates to date — and recommend establishing the ledger.
- **Whether completion is of the whole of the Works or a Section/part**
  (SC 10.2 — partial taking over changes retention and delay damages
  apportionment)
- **Site inspection evidence**: inspection date, attendees, photographic
  record availability

## Step 1: Identify the Instrument

| Instrument | Key Sub-Clauses (1999) | Output | Reference file |
|---|---|---|---|
| Taking-Over Certificate | 10.1, 10.2, 9.1 (tests) | Word (.docx) + PDF | `references/taking-over-certificate.md` |
| Outstanding Works & Defects Schedule | 10.1, 11.1 | Excel (.xlsx) | `references/defects-schedule.md` |
| DNP instruction / notice | 11.1, 11.2, 11.4 | Word (.docx) | `references/defects-schedule.md` |
| Performance Certificate | 11.9, 14.9 | Word (.docx) + PDF | `references/performance-certificate.md` |

Read the relevant reference file BEFORE producing output.

## Step 2: Decision Tests (apply before certifying)

A Taking-Over Certificate is issued only when the Works (or Section) have
been **completed in accordance with the Contract** except for minor
outstanding work and defects which will not substantially affect the use of
the Works for their intended purpose (SC 10.1). The QS/Engineer must record:

1. Tests on Completion passed (SC 9.1) — cite the test certificates
2. The deemed-taking-over trap: if the Engineer neither issues the
   certificate nor rejects the application within 28 days, the Works are
   DEEMED taken over — diarise the 28-day clock in the notice register
3. Outstanding works valued and listed (priced from the project rate
   library, same rates that priced the bill)
4. Consequences triggered: first retention moiety release (14.9), risk
   transfer (17.2), insurance changeover, delay damages cease, DNP starts

A Performance Certificate is issued within 28 days after the latest of the
DNP expiry dates, once the Contractor has completed all defects remedying
(SC 11.9). Only this certificate constitutes acceptance of the Works.

## Step 3: Ledger Integration

```python
from ledger import LedgerEngine
eng = LedgerEngine.load("CCELAM_LEDGER_<PROJECT>_Rev_N.json")
eng.taking_over(toc_ref=..., toc_date=..., outstanding_works_value=...)
#   -> appends TAKING_OVER + first-moiety RETENTION_RELEASE events
eng.performance_certificate(pc_ref=..., pc_date=...)
#   -> appends PERFORMANCE_CERTIFICATE + second-moiety release
eng.snapshot(rev=N+1, directory=...)   # supersede, never overwrite
```

The certificate documents quote the moiety amounts FROM these events.
If the document figure and the ledger event ever disagree, the ledger is
correct and the document is reissued at the next Rev.

## Step 4: House Standards

- CCELAM brand: Arial, A4 portrait, navy #1B2A4A / crimson #8B1A2B /
  gold #C8A951 / teal #1A7A6D; British English; third-person passive voice
- Document reference: `CCELAM/[TOC|DEF|PC]/[PROJECT]/[YEAR]/[SEQ] Rev [N]`
- Mandatory sign-off block: blank signature box, official stamp placement
  box, date field
- Read `/mnt/skills/public/docx/SKILL.md` and `/mnt/skills/public/xlsx/SKILL.md`
  before producing files; hooks `arithmetic_verify` and
  `british_english_check` apply to all outputs

## Step 5: Quality Check

- [ ] Sub-Clause citations match the contract edition in use
- [ ] Retention moiety equals the ledger event amount exactly
- [ ] Defects schedule items each carry: location, description, trade,
      SMM7-priced reinstatement value, target date, status
- [ ] 28-day deemed-taking-over clock entered in the notice register
- [ ] DNP expiry date computed and diarised
- [ ] Partial taking over: retention proportion and delay damages
      reduction computed and stated
