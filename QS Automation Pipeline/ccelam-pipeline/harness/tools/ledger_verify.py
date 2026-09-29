#!/usr/bin/env python3
"""Read-only integrity check of a ledger snapshot: loads it (which
verifies the SHA-256 event chain) and reports its state.

Exit 0 = chain intact, 2 = broken or unreadable.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ledger"))

from ledger import LedgerEngine, LedgerError  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ledger_verify.py <ledger_snapshot.json>")
        return 2
    try:
        eng = LedgerEngine.load(sys.argv[1])
    except (LedgerError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"tool": "ledger_verify", "status": "FAIL",
                          "reason": str(exc)}))
        return 2
    print(json.dumps({"tool": "ledger_verify", "status": "PASS",
                      "ledger_ref": eng.header.ledger_ref,
                      "events": len(eng.events),
                      "revised_contract_sum": str(eng.revised_contract_sum())},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
