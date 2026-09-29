"""Evidence: every run leaves a verifiable record — results, logs,
artifacts and a file diff — on an append-only, SHA-256 hash-chained log
(the same discipline as the project cost ledger)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_tree(dirs: list[Path], exclude: list[Path] = ()) -> dict[str, str]:
    """{path: sha256} for every file under the given directories."""
    out: dict[str, str] = {}
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if (p.is_file() and "__pycache__" not in p.parts
                    and not any(p.is_relative_to(e) for e in exclude)):
                out[str(p)] = sha256_file(p)
    return out


def diff_trees(before: dict[str, str], after: dict[str, str]) -> dict[str, list]:
    return {
        "added": sorted({p: after[p] for p in after.keys() - before.keys()}.items()),
        "modified": sorted({p: after[p] for p in after.keys() & before.keys()
                            if after[p] != before[p]}.items()),
        "removed": sorted(before.keys() - after.keys()),
    }


def _digest(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class EvidenceError(Exception):
    pass


class EvidenceLog:
    """Append-only JSONL. Each record carries prev_hash and its own hash;
    any edit, deletion or reordering breaks the chain on verify()."""

    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.path = self.dir / "evidence_log.jsonl"

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in
                self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> tuple[bool, int | None]:
        prev = GENESIS
        for i, rec in enumerate(self.records()):
            if rec.get("prev_hash") != prev or rec.get("hash") != _digest(rec):
                return False, i
            prev = rec["hash"]
        return True, None

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        ok, broken = self.verify()
        if not ok:
            raise EvidenceError(f"evidence chain broken at record {broken} — "
                                f"refusing to append")
        recs = self.records()
        rec = {"seq": len(recs),
               "recorded_at": datetime.now(timezone.utc).isoformat(),
               **record,
               "prev_hash": recs[-1]["hash"] if recs else GENESIS}
        rec["hash"] = _digest(rec)
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
        return rec
