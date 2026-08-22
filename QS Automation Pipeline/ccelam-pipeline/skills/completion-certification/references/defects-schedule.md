# Outstanding Works & Defects Schedule and DNP Instruments

## Defects schedule (.xlsx, CCELAM house workbook conventions)

Sheet 1 — Summary: counts and values by trade/work section; grand total of
reinstatement value; cross-sheet formulas (never hard-coded totals).

Sheet 2 — Schedule, one row per item:

| Column | Content |
|---|---|
| Item No. | DEF-001, DEF-002 ... |
| Location | Block / level / room / gridline |
| Description | Defect or outstanding work, SMM7 description discipline |
| Trade / Section | SMM7 work section letter |
| Source GUID(s) | Model element provenance where applicable |
| Unit / Qty | Measured reinstatement quantity |
| Rate | From the project rate library (same rates as the bill) |
| Value | Qty × Rate (formula) |
| Classification | Outstanding work / Defect / Damage (11.2 attribution) |
| Target date | Per SC 11.1 — within DNP or as instructed |
| Status | Open / Remedied / Verified / Carried to PC |
| Photo ref | Photographic record cross-reference |

Sheet 3 — Photographic schedule placeholders (one row per photo ref).

## Pricing discipline

Reinstatement values are priced from the SAME rate library that priced the
contract bill. If a defect requires work with no bill rate, build a star
rate and mark it; these star rates feed the out-turn hook like any other.

## Attribution (11.2)

Cost attribution matters: work attributable to design (for which the
Contractor is responsible), workmanship, or materials = Contractor's cost;
any other cause = treated as a Variation (13.3). Record the attribution per
item in the Classification column — it determines who pays.

## DNP instruments

- **Notice of defect (11.1)**: Employer/Engineer may notify defects up to
  DNP expiry. Each notice gets a register entry and a remedy target date.
- **Extension of DNP (11.3)**: maximum two years; only where the Works
  cannot be used for their intended purpose by reason of the defect.
- **Failure to remedy (11.4)**: options — others execute at Contractor's
  cost, accept with price reduction, or (extreme) terminate the relevant
  part. Quantify each option before recommending.
- **Clearance certificate practice**: on remedying, the verifying
  inspection closes the item (Status = Verified) with date and inspector.
