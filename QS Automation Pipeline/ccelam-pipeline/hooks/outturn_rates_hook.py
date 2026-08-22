#!/usr/bin/env python3
"""CCELAM out-turn rates feedback hook.

Closes the practice's OODA loop: when a project's Final Statement is on
the ledger, the certified out-turn evidence (final measured quantities
against contract and star rates, with GUID provenance counts) is exported
into the practice's out-turn evidence register, and — where a current
rate library is supplied — variances against library rates are flagged.

Governance discipline:
  * Evidence in, judgement stays with the QS. The hook never rewrites a
    library rate; it issues evidence and variance flags. Rate-setting is
    a reviewed act (the library's own Rev discipline).
  * Supersede, never overwrite: each run issues the next Rev of the
    evidence register; existing Revs are immutable.
  * Refuses to run on a ledger without a FINAL_STATEMENT event, or with
    a broken hash chain.

Run manually, from the project-closure skill, or as a PostToolUse hook on
ledger snapshot writes (see hook_settings_snippet.json):

    python3 outturn_rates_hook.py <ledger_snapshot.json> \
        --register-dir rates/ [--library rates/rate_library_kampala.csv] \
        [--variance-threshold 10]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ledger"))

from ledger import LedgerEngine, LedgerError  # noqa: E402

REGISTER_STEM = "outturn_evidence"
FIELDS = ["recorded_at", "project_ref", "ledger_ref", "item_ref",
          "work_section", "description", "unit", "final_quantity",
          "contract_rate", "out_turn_rate", "currency",
          "source_guid_count", "library_rate", "variance_pct", "flag"]


def latest_register(directory: Path) -> tuple[int, Path | None]:
    best, best_path = -1, None
    for p in directory.glob(f"{REGISTER_STEM}_Rev_*.csv"):
        m = re.search(r"_Rev_(\d+)\.csv$", p.name)
        if m and int(m.group(1)) > best:
            best, best_path = int(m.group(1)), p
    return best, best_path


def load_library(path: Path) -> dict[str, Decimal]:
    """Best-effort load of the rate library keyed on a key/item column."""
    rates: dict[str, Decimal] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        cols = {c.lower().strip(): c for c in reader.fieldnames or []}
        key_col = next((cols[c] for c in
                        ("rate_key", "key", "item_ref", "item")
                        if c in cols), None)
        rate_col = next((cols[c] for c in
                         ("rate", "rate_ugx", "unit_rate")
                         if c in cols), None)
        if not key_col or not rate_col:
            return rates
        for row in reader:
            try:
                rates[row[key_col].strip()] = Decimal(
                    str(row[rate_col]).replace(",", ""))
            except Exception:
                continue
    return rates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger_snapshot")
    ap.add_argument("--register-dir", default=".")
    ap.add_argument("--library", default=None)
    ap.add_argument("--variance-threshold", type=float, default=10.0)
    args = ap.parse_args()

    try:
        eng = LedgerEngine.load(args.ledger_snapshot)
    except LedgerError as exc:
        print(json.dumps({"hook": "outturn-rates", "status": "BLOCKED",
                          "reason": str(exc)}))
        return 2

    try:
        rows = eng.out_turn_rates()
    except LedgerError as exc:
        # No Final Statement yet — nothing to feed back; not an error
        # when running as a PostToolUse hook on interim snapshots.
        print(json.dumps({"hook": "outturn-rates", "status": "SKIPPED",
                          "reason": str(exc)}))
        return 0

    library = load_library(Path(args.library)) if args.library else {}
    now = datetime.now(timezone.utc).isoformat()
    flagged = 0
    out_rows = []
    for r in rows:
        lib_rate = library.get(r["item_ref"])
        variance_pct, flag = "", ""
        if lib_rate is not None and lib_rate != 0:
            v = (Decimal(r["out_turn_rate"]) - lib_rate) / lib_rate * 100
            variance_pct = f"{v:.1f}"
            if abs(v) >= Decimal(str(args.variance_threshold)):
                flag = (f"variance {variance_pct}% vs library — "
                        f"QS review for next library Rev")
                flagged += 1
        out_rows.append({
            "recorded_at": now,
            "project_ref": r["project_ref"],
            "ledger_ref": eng.header.ledger_ref,
            **{k: r[k] for k in ("item_ref", "work_section", "description",
                                 "unit", "final_quantity", "contract_rate",
                                 "out_turn_rate", "currency",
                                 "source_guid_count")},
            "library_rate": str(lib_rate) if lib_rate is not None else "",
            "variance_pct": variance_pct,
            "flag": flag,
        })

    reg_dir = Path(args.register_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    prev_rev, prev_path = latest_register(reg_dir)
    existing: list[dict] = []
    if prev_path is not None:
        with prev_path.open(newline="", encoding="utf-8") as fh:
            existing = list(csv.DictReader(fh))
        # Idempotency: never double-post the same ledger's evidence
        if any(e.get("ledger_ref") == eng.header.ledger_ref
               for e in existing):
            print(json.dumps({"hook": "outturn-rates", "status": "SKIPPED",
                              "reason": f"{eng.header.ledger_ref} already "
                                        f"in {prev_path.name}"}))
            return 0

    new_rev = prev_rev + 1
    new_path = reg_dir / f"{REGISTER_STEM}_Rev_{new_rev}.csv"
    if new_path.exists():
        print(json.dumps({"hook": "outturn-rates", "status": "BLOCKED",
                          "reason": f"{new_path.name} already issued — "
                                    f"supersede, never overwrite"}))
        return 2
    with new_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for row in existing + out_rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})

    print(json.dumps({
        "hook": "outturn-rates", "status": "ISSUED",
        "register": new_path.name, "register_rev": new_rev,
        "rows_added": len(out_rows), "variance_flags": flagged,
        "project_ref": eng.header.project_ref,
        "note": "Evidence issued; library rate changes remain a reviewed "
                "act for the QS at the next library Rev."}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
