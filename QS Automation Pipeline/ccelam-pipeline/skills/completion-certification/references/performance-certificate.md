# Performance Certificate — Structure and Clause Logic

FIDIC Red Book 1999 SC 11.9. The only certificate that constitutes
acceptance of the Works.

## Preconditions (verify before drafting)

1. The latest Defects Notification Period has expired (check ledger
   TAKING_OVER event date + DNP days, plus any SC 11.3 extensions).
2. All items on the Outstanding Works & Defects Schedule show Status =
   Verified (or formally resolved under 11.4 with the cost consequence
   posted to the ledger).
3. Contractor has supplied all Contractor's Documents and completed all
   testing/remedying obligations.
4. Issue within 28 days after the latest DNP expiry date.

## Document structure (.docx)

1. Header — ref `CCELAM/PC/[PROJECT]/[YEAR]/[SEQ] Rev [N]`, parties,
   contract particulars.
2. Recitals — TOC reference and date; DNP expiry date(s); defects
   schedule closure summary (items raised / remedied / resolved under 11.4).
3. Operative certification:
   > "Pursuant to Sub-Clause 11.9 of the Conditions of Contract, it is
   > hereby certified that the Contractor fulfilled the Contractor's
   > obligations under the Contract on [DATE]."
4. Consequences recorded:
   - Second moiety of retention released: **[amount from ledger event]**
     (14.9) — outstanding amounts may be withheld for 11.4 work
   - Performance Security to be returned within 21 days (4.2)
   - Contractor to clear Site (11.11)
   - Contractor may submit the draft Final Statement (14.11) — 56 days
5. Sign-off block.

## Ledger discipline

`eng.performance_certificate(...)` posts the event and the second-moiety
release BEFORE the document is drafted; the document quotes the event
amount. The Final Statement cannot be posted to the ledger until this
event exists (enforced in `ledger.py`).

## After issue

The Performance Certificate is the gate (G-level) into the project-closure
skill: Final Statement, discharge (14.12), Final Payment Certificate
(14.13), and the Project Closure Report.
