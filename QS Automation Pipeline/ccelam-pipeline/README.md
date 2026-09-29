# CCELAM Drawings-to-Closure Pipeline — Build 1

CCELAM NK & Associates | Kampala, Uganda | CCELAM@outlook.com | www.CCELAM.com

Four deliverables completing the spine of the drawings-to-closure pipeline,
in the agreed priority order. All tested; demonstration figures are
fictional and hand-verified.

## 1. Project Cost Ledger — the spine (`ledger/`)

- `ledger_schema.py` — pydantic v2 data contract: header, BOQ baseline
  with `source_guids` provenance, append-only events, certificate figures.
  All money is `Decimal` at 2 dp ROUND_HALF_UP; floats never touch a
  certified figure.
- `ledger.py` — engine: lock baseline → post VOs/claims → prepare and
  certify IPCs (CCELAM previous / this period / to date discipline, FIDIC
  SC 14.3/14.6 logic: 10% retention capped at 5%, advance recovery capped
  at the advance) → Taking-Over (first moiety, SC 10.1/14.9) →
  Performance Certificate (second moiety, SC 11.9) → Final Statement
  (SC 14.11 cash reconciliation) → `out_turn_rates()`.
- SHA-256 hash-chained events: tampering is detected on load. Snapshots
  are versioned `CCELAM/LEDGER/[PROJECT]/[YEAR]/[SEQ] Rev [N]` and an
  issued Rev can never be overwritten — supersede only.
- `tests/test_ledger.py` — full lifecycle, 22 checks, all passing,
  including the over-measure flag, retention/advance caps, moiety
  releases, round-trip load, and tamper detection.

Run: `python3 tests/test_ledger.py` (snapshots go to a temporary
directory, so the suite can be re-run)

## 2. Two new skills (`skills/`)

- `completion-certification/` — Taking-Over Certificate (10.1/10.2 with
  the 28-day deemed-taking-over trap diarised), Outstanding Works &
  Defects Schedule (priced from the project rate library, 11.2
  attribution), DNP instruments, Performance Certificate (11.9). Retention
  consequences are read from ledger events, never re-keyed.
- `project-closure/` — Final Account/Final Statement (14.11), discharge
  (14.12), Final Payment Certificate (14.13), and the CCELAM Project
  Closure Report; the 56/28/56-day machinery diarised; reconciliation
  must close to zero against the ledger.

Install: copy each folder into `.claude/skills/` (or `~/.claude/skills/`),
joining the 26-skill library as items 27 and 28.

## 3. Intake (`intake/`)

- `archicad-translator-preset.md` — the "CCELAM QS Export" translator
  specification for design teams (IFC4, Base Quantities ON, property and
  classification mapping, stable GlobalIds), issued with the EIR per
  ISO 19650-2.
- `g1_intake_gate.py` — six-check acceptance gate (schema, units,
  GlobalId integrity, measurable content, BaseQuantities coverage, Pset
  coverage). Exit 0 PASS / 1 WARN / 2 FAIL. Verified against generated
  good and bad IFC4 fixtures (`fixtures/g1_good.ifc`, `g1_bad.ifc`).

## 4. Out-turn feedback hook (`hooks/`)

- `outturn_rates_hook.py` — on a closed ledger (Final Statement present,
  chain verified), issues the next Rev of the out-turn evidence register
  with library variance flags. Evidence in; rate-setting remains the
  QS's reviewed act. Idempotent per ledger; supersede, never overwrite.
- `hook_settings_snippet.json` — PostToolUse wiring (fires on ledger
  snapshot writes; safely SKIPs interim snapshots) and a PreToolUse G1
  wiring for measurement runs. Adjust paths on installation.

## 5. Coding harness (`harness/`)

Every pipeline tool runs through one control plane: context inputs
(models, tools, layered permissions) → selection (model + tool + plan) →
host validation (policy, safety, scope) → tool runs → evidence (results,
logs, SHA-256 workspace diff, hash-chained evidence log). Selection is not
permission, and provider-owned internals and external ACP loops stay
outside the boundary. See `harness/README.md`.

Run: `python3 -m harness run "validate ifc model" --arg ifc=fixtures/g1_good.ifc`
Tests: `python3 tests/test_harness.py` (33 checks)

## Dependencies

`pip install pydantic ifcopenshell` (built against pydantic 2.13,
ifcopenshell 0.8.5 — same as the Quantify platform).

## Pipeline position

Stage 1 gate (intake) → Stage 2–3 (Quantify, existing) → **ledger locks
the contract baseline** → Stage 4 instruments post events → Stage 5
(completion-certification) → Stage 6 (project-closure) → out-turn hook
closes the loop back into the rate library.

---

| Prepared by | Signature | Official Stamp | Date |
|---|---|---|---|
| Dr John Muhumuza Kakitahi, FISU, SRB No. 305 | | | |

All issued figures remain subject to the registered Quantity Surveyor's
review.
