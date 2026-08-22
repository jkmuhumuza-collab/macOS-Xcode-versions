"""CCELAM Project Cost Ledger — engine.

Operations on the append-only ledger. Every certified instrument is an
event; every figure in every downstream document is computed from the
event log, never re-keyed.

Usage sketch:
    eng = LedgerEngine.new(header, baseline)
    eng.post_variation(vo_ref="VO-01", ...)
    figs = eng.prepare_ipc(period_end="2026-06-30", measured={...})
    eng.certify_ipc(figs)                      # immutable from here
    eng.taking_over(toc_ref=..., date=...)     # releases first moiety
    eng.performance_certificate(...)           # releases second moiety
    eng.final_statement()
    eng.snapshot(rev=0, directory="out/")      # supersede, never overwrite
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ledger_schema import (Baseline, BOQLine, CertificateFigures, EventType,
                           LedgerEvent, LedgerHeader, LedgerState,
                           canonical_json, money)

GENESIS = "0" * 64


class LedgerError(Exception):
    pass


class LedgerEngine:

    def __init__(self, header: LedgerHeader, baseline: Baseline,
                 events: Optional[list[LedgerEvent]] = None):
        self.header = header
        self.baseline = baseline
        self.events: list[LedgerEvent] = events or []
        self._lines = {l.item_ref: l for l in baseline.lines}

    # ---------------------------------------------------------------- core

    @classmethod
    def new(cls, header: LedgerHeader, baseline: Baseline) -> "LedgerEngine":
        eng = cls(header, baseline)
        eng._append(EventType.BASELINE_LOCKED, {
            "boq_ref": baseline.boq_ref,
            "measurement_standard": baseline.measurement_standard,
            "line_count": len(baseline.lines),
            "measured_total": str(baseline.measured_total),
            "baseline_hash": eng._baseline_hash(),
        })
        return eng

    def _baseline_hash(self) -> str:
        import hashlib
        body = canonical_json([l.model_dump() for l in self.baseline.lines])
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _append(self, etype: EventType, payload: dict[str, Any]) -> LedgerEvent:
        prev = self.events[-1].hash if self.events else GENESIS
        ev = LedgerEvent(seq=len(self.events) + 1, type=etype,
                         payload=payload, prev_hash=prev)
        ev.hash = ev.compute_hash()
        self.events.append(ev)
        return ev

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """True if untampered; otherwise (False, first broken seq)."""
        prev = GENESIS
        for ev in self.events:
            if ev.prev_hash != prev or ev.compute_hash() != ev.hash:
                return False, ev.seq
            prev = ev.hash
        return True, None

    # ------------------------------------------------------------ posting

    def post_variation(self, vo_ref: str, sub_clause: str, description: str,
                       contractor_claim: Any, qs_assessment: Any,
                       approved_amount: Any, status: str = "approved",
                       new_lines: Optional[list[BOQLine]] = None) -> LedgerEvent:
        payload = {
            "vo_ref": vo_ref, "sub_clause": sub_clause,
            "description": description,
            "contractor_claim": str(money(contractor_claim)),
            "qs_assessment": str(money(qs_assessment)),
            "approved_amount": str(money(approved_amount)),
            "status": status,
            "new_lines": [l.model_dump() for l in (new_lines or [])],
        }
        ev = self._append(EventType.VARIATION, payload)
        for l in new_lines or []:
            self._lines[l.item_ref] = l
        return ev

    def post_claim(self, claim_ref: str, sub_clause: str, description: str,
                   amount_claimed: Any, amount_determined: Any,
                   status: str = "determined") -> LedgerEvent:
        return self._append(EventType.CLAIM, {
            "claim_ref": claim_ref, "sub_clause": sub_clause,
            "description": description,
            "amount_claimed": str(money(amount_claimed)),
            "amount_determined": str(money(amount_determined)),
            "status": status,
        })

    # -------------------------------------------------------- computation

    def _sum_events(self, etype: EventType, field: str,
                    where: Optional[dict[str, Any]] = None) -> Decimal:
        total = Decimal("0")
        for ev in self.events:
            if ev.type is not etype:
                continue
            if where and any(ev.payload.get(k) != v for k, v in where.items()):
                continue
            total += Decimal(ev.payload[field])
        return money(total)

    def approved_variations(self) -> Decimal:
        return self._sum_events(EventType.VARIATION, "approved_amount",
                                where={"status": "approved"})

    def determined_claims(self) -> Decimal:
        return self._sum_events(EventType.CLAIM, "amount_determined",
                                where={"status": "determined"})

    def revised_contract_sum(self) -> Decimal:
        return money(self.header.contract_sum + self.approved_variations()
                     + self.determined_claims())

    def _last_certificate(self) -> Optional[dict[str, Any]]:
        for ev in reversed(self.events):
            if ev.type is EventType.IPC_CERTIFIED:
                return ev.payload
        return None

    def prepare_ipc(self, period_end: str,
                    measured_todate: dict[str, Any],
                    variations_executed_todate: Any = "0",
                    materials_on_site: Any = "0") -> CertificateFigures:
        """Compute an IPC from cumulative measured quantities to date.

        measured_todate maps item_ref -> quantity executed to date.
        Quantities exceeding the billed quantity are certified as measured
        (remeasurement contract) but FLAGGED for the QS's review.
        """
        flags: list[str] = []
        work = Decimal("0")
        for ref, qty in measured_todate.items():
            line = self._lines.get(ref)
            if line is None:
                raise LedgerError(f"Unknown BOQ item ref: {ref}")
            q = Decimal(str(qty))
            if q > line.quantity:
                flags.append(
                    f"{ref}: measured {q} exceeds billed {line.quantity} "
                    f"{line.unit} — remeasure / VO check")
            work += q * line.rate
        work = money(work)

        vo_exec = money(variations_executed_todate)
        vo_cap = self.approved_variations()
        if vo_exec > vo_cap:
            flags.append(f"Variations executed {vo_exec} exceeds approved "
                         f"{vo_cap} — VO approval outstanding")
        mos = money(materials_on_site)
        gross = money(work + vo_exec + mos)

        h = self.header
        retention_raw = money(gross * h.retention_percent / Decimal("100"))
        retention_cap = money(self.revised_contract_sum()
                              * h.retention_limit_percent / Decimal("100"))
        retention = min(retention_raw, retention_cap)
        retention = money(retention - self._retention_released())
        if retention < 0:
            retention = Decimal("0.00")

        adv_rec_prev = self._advance_recovered_todate()
        if h.advance_payment > 0 and h.advance_recovery_percent > 0:
            rec_raw = money(gross * h.advance_recovery_percent / Decimal("100"))
            adv_rec = min(rec_raw, h.advance_payment)
        else:
            adv_rec = adv_rec_prev
        adv_rec = max(adv_rec, adv_rec_prev)   # recovery never reverses

        last = self._last_certificate()
        prev_net = (Decimal(last["net_certified_todate"])
                    if last else Decimal("0"))
        cert_no = (last["cert_no"] + 1) if last else 1

        net_todate = money(gross - retention - adv_rec)
        net_this = money(net_todate - prev_net)
        vat = (money(net_this * h.vat_percent / Decimal("100"))
               if h.apply_vat else Decimal("0.00"))

        return CertificateFigures(
            cert_no=cert_no, period_end=period_end,
            measured_work_todate=str(work),
            variations_todate=str(vo_exec),
            materials_on_site=str(mos),
            gross_todate=str(gross),
            retention_todate=str(retention),
            advance_recovery_todate=str(adv_rec),
            previous_net_certified=str(prev_net),
            net_this_certificate=str(net_this),
            vat_this_certificate=str(vat),
            payable_this_certificate=str(money(net_this + vat)),
            remeasure_flags=flags,
        )

    def certify_ipc(self, figs: CertificateFigures,
                    measured_todate: dict[str, Any]) -> LedgerEvent:
        """Lock the certificate into the chain. Immutable from here."""
        if self._final_statement_event() is not None:
            raise LedgerError("Final Statement issued — ledger is closed")
        payload = figs.model_dump()
        payload["net_certified_todate"] = str(
            money(Decimal(figs.previous_net_certified)
                  + Decimal(figs.net_this_certificate)))
        payload["measured_todate"] = {k: str(v)
                                      for k, v in measured_todate.items()}
        return self._append(EventType.IPC_CERTIFIED, payload)

    # ----------------------------------------------- completion / closure

    def _retention_released(self) -> Decimal:
        return self._sum_events(EventType.RETENTION_RELEASE, "amount")

    def _advance_recovered_todate(self) -> Decimal:
        last = self._last_certificate()
        return Decimal(last["advance_recovery_todate"]) if last else Decimal("0")

    def _retention_held(self) -> Decimal:
        last = self._last_certificate()
        return Decimal(last["retention_todate"]) if last else Decimal("0")

    def taking_over(self, toc_ref: str, toc_date: str,
                    outstanding_works_value: Any = "0",
                    section: Optional[str] = None) -> LedgerEvent:
        """Taking-Over Certificate (SC 10.1) — releases the first moiety
        of retention (half of the retention held), per SC 14.9."""
        first_moiety = money(self._retention_held() / Decimal("2"))
        ev = self._append(EventType.TAKING_OVER, {
            "toc_ref": toc_ref, "date": toc_date, "section": section,
            "outstanding_works_value": str(money(outstanding_works_value)),
            "first_moiety_released": str(first_moiety),
        })
        self._append(EventType.RETENTION_RELEASE, {
            "moiety": "first", "amount": str(first_moiety),
            "authority": toc_ref})
        return ev

    def performance_certificate(self, pc_ref: str, pc_date: str) -> LedgerEvent:
        """Performance Certificate (SC 11.9) — releases the balance of
        retention (second moiety), per SC 14.9."""
        if not any(e.type is EventType.TAKING_OVER for e in self.events):
            raise LedgerError("Performance Certificate before Taking-Over")
        balance = money(self._retention_held() - self._retention_released())
        ev = self._append(EventType.PERFORMANCE_CERTIFICATE, {
            "pc_ref": pc_ref, "date": pc_date,
            "second_moiety_released": str(balance)})
        self._append(EventType.RETENTION_RELEASE, {
            "moiety": "second", "amount": str(balance), "authority": pc_ref})
        return ev

    def _final_statement_event(self) -> Optional[LedgerEvent]:
        for ev in reversed(self.events):
            if ev.type is EventType.FINAL_STATEMENT:
                return ev
        return None

    def final_statement(self) -> LedgerEvent:
        """Final Statement (SC 14.11) — closing reconciliation. Every figure
        is a read of the chain; the balance is what reconciles."""
        if not any(e.type is EventType.PERFORMANCE_CERTIFICATE
                   for e in self.events):
            raise LedgerError("Final Statement before Performance Certificate")
        last = self._last_certificate()
        if last is None:
            raise LedgerError("No certificates on the ledger")
        gross = Decimal(last["gross_todate"])
        net_certified = Decimal(last["net_certified_todate"])
        retention_back = self._retention_released()
        final_sum = self.revised_contract_sum()
        # Cash reconciliation: contractor has received the advance plus the
        # net interim certificates (within which the advance was recovered).
        # Balance due on the Final Payment Certificate is the gross value
        # executed less everything already paid:
        balance_due = money(gross - net_certified - self.header.advance_payment)
        return self._append(EventType.FINAL_STATEMENT, {
            "final_contract_sum": str(final_sum),
            "gross_value_executed": str(gross),
            "net_certified_todate": str(net_certified),
            "retention_released": str(retention_back),
            "balance_due_on_final_certificate": str(balance_due),
            "out_turn_basis": "measured_todate of last IPC + approved VOs",
        })

    # ----------------------------------------------------------- reporting

    def state(self) -> LedgerState:
        last = self._last_certificate()
        return LedgerState(
            original_contract_sum=str(self.header.contract_sum),
            approved_variations=str(self.approved_variations()),
            determined_claims=str(self.determined_claims()),
            revised_contract_sum=str(self.revised_contract_sum()),
            gross_certified_todate=str(Decimal(last["gross_todate"])
                                       if last else Decimal("0.00")),
            retention_held=str(money(self._retention_held()
                                     - self._retention_released())),
            retention_released=str(self._retention_released()),
            advance_outstanding=str(money(self.header.advance_payment
                                          - self._advance_recovered_todate())),
            net_certified_todate=str(Decimal(last["net_certified_todate"])
                                     if last else Decimal("0.00")),
            certificates_issued=sum(1 for e in self.events
                                    if e.type is EventType.IPC_CERTIFIED),
            taking_over_achieved=any(e.type is EventType.TAKING_OVER
                                     for e in self.events),
            performance_certificate_issued=any(
                e.type is EventType.PERFORMANCE_CERTIFICATE
                for e in self.events),
            final_statement_issued=self._final_statement_event() is not None,
        )

    def out_turn_rates(self) -> list[dict[str, str]]:
        """Certified out-turn unit rates per item — the feedback dataset
        for the rate library. Available once a Final Statement is issued."""
        fs = self._final_statement_event()
        if fs is None:
            raise LedgerError("Out-turn rates require a Final Statement")
        last = self._last_certificate()
        rows = []
        for ref, qty in last["measured_todate"].items():
            line = self._lines[ref]
            q = Decimal(qty)
            if q == 0:
                continue
            rows.append({
                "item_ref": ref, "work_section": line.work_section,
                "description": line.description, "unit": line.unit,
                "final_quantity": str(q),
                "contract_rate": str(line.rate),
                "out_turn_rate": str(line.rate),  # rate-based contract:
                # rates hold; the out-turn evidence is the executed quantity
                # against rate. Star-rate VOs arrive via their own lines.
                "source_guid_count": str(len(line.source_guids)),
                "project_ref": self.header.project_ref,
                "currency": self.header.currency,
            })
        return rows

    # --------------------------------------------------------- persistence

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ccelam-ledger/1.0",
            "header": self.header.model_dump(mode="json"),
            "baseline": {
                "boq_ref": self.baseline.boq_ref,
                "measurement_standard": self.baseline.measurement_standard,
                "lines": [l.model_dump() for l in self.baseline.lines],
            },
            "events": [e.model_dump() for e in self.events],
        }

    @classmethod
    def load(cls, path: str | Path) -> "LedgerEngine":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        header = LedgerHeader(**data["header"])
        baseline = Baseline(
            boq_ref=data["baseline"]["boq_ref"],
            measurement_standard=data["baseline"]["measurement_standard"],
            lines=[BOQLine(**l) for l in data["baseline"]["lines"]])
        events = [LedgerEvent(**e) for e in data["events"]]
        eng = cls(header, baseline, events)
        ok, broken = eng.verify_chain()
        if not ok:
            raise LedgerError(f"Hash chain broken at event seq {broken} — "
                              f"ledger has been tampered with or corrupted")
        # replay VO lines into the working set
        for ev in events:
            if ev.type is EventType.VARIATION:
                for l in ev.payload.get("new_lines", []):
                    line = BOQLine(**l)
                    eng._lines[line.item_ref] = line
        return eng

    def snapshot(self, rev: int, directory: str | Path) -> Path:
        """Write a versioned snapshot. Supersede, never overwrite: an
        existing Rev file is protected; issue the next Rev instead."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        safe = self.header.ledger_ref.replace("/", "_")
        path = directory / f"{safe}_Rev_{rev}.json"
        if path.exists():
            raise LedgerError(
                f"{path.name} already issued — issue Rev {rev + 1} instead "
                f"(supersede, never overwrite)")
        self._append(EventType.SNAPSHOT_ISSUED, {
            "rev": rev, "file": path.name,
            "doc_ref": f"{self.header.ledger_ref} Rev {rev}"})
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str),
                        encoding="utf-8")
        return path
