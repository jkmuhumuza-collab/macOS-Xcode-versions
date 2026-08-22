# Final Account, Discharge and Final Payment Certificate

## Final Account workbook (.xlsx, house conventions)

Sheet order: Cover → Reconciliation Summary → Measured Works Final →
Variations Account → Claims Account → Certificates Register → Retention &
Advance Account → Traceability.

**Reconciliation Summary** (the page the Employer reads):

| Line | Source |
|---|---|
| Original Contract Sum | ledger header |
| Add: approved Variations (itemised ref + amount) | VARIATION events |
| Add: determined Claims (itemised) | CLAIM events |
| **Final Contract Sum** | `revised_contract_sum()` |
| Gross value of Works executed | last IPC `gross_todate` |
| Less: advance payment made / add: recovered | header + certificates |
| Less: net certified to date (certificates listed) | IPC events |
| Retention held / released (moieties, authorities) | RETENTION_RELEASE events |
| **Balance due on Final Payment Certificate** | FINAL_STATEMENT event |

Every figure is a formula or a ledger read — no typed constants. The
reconciliation must close to zero; if it does not, the account is wrong,
not the ledger.

**Measured Works Final**: per BOQ item — billed qty, final measured qty,
rate, final amount, variance qty and value, source GUID count. Over/under
measure variances above the practice threshold get a one-line explanation.

**Variations Account**: VO ref, Sub-Clause, description, contractor claim,
QS assessment, approved amount, status, ledger event seq.

**Traceability**: item ref → source GlobalIds → certificate(s) in which
certified — the golden thread closed.

## Final Statement narrative (.docx)

1. Header and recitals (Performance Certificate ref and date; 14.11 basis)
2. Account summary (mirrors the Reconciliation Summary)
3. Statement of agreement / determination of disputed items (if any, with
   the 14.11 second-paragraph machinery recorded)
4. Sign-off block

## Written discharge (14.12)

Short-form letter from the Contractor confirming the Final Statement
represents full and final settlement; record that it takes effect only
when the FPC amount is paid and the Performance Security returned. The QS
drafts it for the Contractor's execution; file the executed copy against
the ledger snapshot.

## Final Payment Certificate (14.13)

Operative clause certifies (a) the amount finally due, and (b) the balance
after crediting all previous payments and all deductions. Quote the
FINAL_STATEMENT event's `balance_due_on_final_certificate` verbatim.
Issue within 28 days of receiving the Final Statement and discharge;
Employer pays within 56 days (14.7(c)).
