#!/usr/bin/env python3
"""CCELAM G1 intake validation gate.

Reject a bad model the way a QS rejects an unscaled drawing — before any
measurement happens. Runs as a standalone check or as a PreToolUse gate
(same convention as gate_sequence.py): exit 0 = PASS, 1 = PASS WITH
WARNINGS (proceed, flags recorded), 2 = FAIL (block quantification).

Checks
------
G1.1  File parses; schema is IFC4 / IFC4X3 (IFC2X3 = warning: BaseQuantity
      coverage is typically poorer and Qto_* names differ)
G1.2  Project length unit declared (metre or millimetre)
G1.3  GlobalId integrity: present and unique on every product
G1.4  Measurable content: at least one element of a measurable class
G1.5  BaseQuantities coverage: % of measurable elements carrying an
      IfcElementQuantity (threshold default 80% warn, 40% fail)
G1.6  Property coverage: % of measurable elements with at least one Pset
      (classification evidence for the rules engine)

Usage
-----
    python3 g1_intake_gate.py model.ifc [--report out.json]
        [--warn-quant 80] [--fail-quant 40]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import ifcopenshell

MEASURABLE = (
    "IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcBeam", "IfcColumn",
    "IfcFooting", "IfcPile", "IfcDoor", "IfcWindow", "IfcStair",
    "IfcStairFlight", "IfcRamp", "IfcRoof", "IfcCovering",
    "IfcCurtainWall", "IfcMember", "IfcPlate", "IfcRailing",
    "IfcBuildingElementProxy",
)


def gate(path: str, warn_quant: float = 80.0,
         fail_quant: float = 40.0) -> dict:
    checks: list[dict] = []
    status = "PASS"

    def record(ref: str, name: str, result: str, detail: str):
        nonlocal status
        checks.append({"check": ref, "name": name,
                       "result": result, "detail": detail})
        if result == "FAIL":
            status = "FAIL"
        elif result == "WARN" and status != "FAIL":
            status = "WARN"

    p = Path(path)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()

    # G1.1 parse + schema
    try:
        model = ifcopenshell.open(str(p))
    except Exception as exc:
        record("G1.1", "File parses", "FAIL", f"ifcopenshell error: {exc}")
        return _report(p, sha, "FAIL", checks)
    schema = model.schema
    if schema in ("IFC4", "IFC4X3", "IFC4X3_ADD2"):
        record("G1.1", "Schema", "PASS", f"{schema}")
    elif schema == "IFC2X3":
        record("G1.1", "Schema", "WARN",
               "IFC2X3 accepted but IFC4 is the practice standard — "
               "re-export with the CCELAM translator preset")
    else:
        record("G1.1", "Schema", "FAIL", f"Unsupported schema {schema}")

    # G1.2 units
    unit_name = None
    try:
        for ua in model.by_type("IfcUnitAssignment"):
            for u in ua.Units:
                if u.is_a("IfcSIUnit") and u.UnitType == "LENGTHUNIT":
                    unit_name = (u.Prefix or "") + u.Name
        if unit_name in ("METRE", "MILLIMETRE"):
            record("G1.2", "Length unit declared", "PASS", unit_name)
        elif unit_name:
            record("G1.2", "Length unit declared", "WARN",
                   f"{unit_name} — confirm scale before measurement")
        else:
            record("G1.2", "Length unit declared", "FAIL",
                   "No SI length unit on the project")
    except Exception as exc:
        record("G1.2", "Length unit declared", "FAIL", str(exc))

    # G1.3 GlobalId integrity
    products = model.by_type("IfcProduct")
    gids = [pr.GlobalId for pr in products]
    missing = sum(1 for g in gids if not g)
    dupes = len(gids) - len(set(gids))
    if missing == 0 and dupes == 0:
        record("G1.3", "GlobalId integrity", "PASS",
               f"{len(gids)} products, all unique")
    else:
        record("G1.3", "GlobalId integrity", "FAIL",
               f"{missing} missing, {dupes} duplicated — the golden "
               f"thread cannot anchor to this model")

    # G1.4 measurable content
    elements = [e for e in products if e.is_a() in MEASURABLE]
    if elements:
        record("G1.4", "Measurable content", "PASS",
               f"{len(elements)} measurable elements")
    else:
        record("G1.4", "Measurable content", "FAIL",
               "No elements of a measurable class")
        return _report(p, sha, "FAIL", checks)

    # G1.5 BaseQuantities coverage
    def has_quantities(el) -> bool:
        for rel in getattr(el, "IsDefinedBy", []) or []:
            if rel.is_a("IfcRelDefinesByProperties"):
                d = rel.RelatingPropertyDefinition
                if d is not None and d.is_a("IfcElementQuantity"):
                    return True
        return False

    def has_pset(el) -> bool:
        for rel in getattr(el, "IsDefinedBy", []) or []:
            if rel.is_a("IfcRelDefinesByProperties"):
                d = rel.RelatingPropertyDefinition
                if d is not None and d.is_a("IfcPropertySet"):
                    return True
        return False

    q_cov = 100.0 * sum(map(has_quantities, elements)) / len(elements)
    if q_cov >= warn_quant:
        record("G1.5", "BaseQuantities coverage", "PASS", f"{q_cov:.1f}%")
    elif q_cov >= fail_quant:
        record("G1.5", "BaseQuantities coverage", "WARN",
               f"{q_cov:.1f}% (< {warn_quant}%) — geometry-derived "
               f"fallback will apply; flag in the BOQ assumptions")
    else:
        record("G1.5", "BaseQuantities coverage", "FAIL",
               f"{q_cov:.1f}% (< {fail_quant}%) — re-export with "
               f"'Derive BIM data from model geometry' enabled")

    p_cov = 100.0 * sum(map(has_pset, elements)) / len(elements)
    if p_cov >= 50.0:
        record("G1.6", "Property set coverage", "PASS", f"{p_cov:.1f}%")
    else:
        record("G1.6", "Property set coverage", "WARN",
               f"{p_cov:.1f}% — classification rules may fall back to "
               f"element class only; expect more review flags")

    return _report(p, sha, status, checks,
                   extra={"schema": schema, "length_unit": unit_name,
                          "products": len(gids),
                          "measurable_elements": len(elements),
                          "quantity_coverage_pct": round(q_cov, 1),
                          "pset_coverage_pct": round(p_cov, 1)})


def _report(p: Path, sha: str, status: str, checks: list,
            extra: dict | None = None) -> dict:
    rep = {"gate": "G1-INTAKE", "file": p.name, "sha256": sha,
           "checked_at": datetime.now(timezone.utc).isoformat(),
           "status": status, "checks": checks}
    if extra:
        rep.update(extra)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ifc_file")
    ap.add_argument("--report", default=None)
    ap.add_argument("--warn-quant", type=float, default=80.0)
    ap.add_argument("--fail-quant", type=float, default=40.0)
    args = ap.parse_args()

    rep = gate(args.ifc_file, args.warn_quant, args.fail_quant)
    text = json.dumps(rep, indent=2)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text)
    return {"PASS": 0, "WARN": 1, "FAIL": 2}[rep["status"]]


if __name__ == "__main__":
    sys.exit(main())
