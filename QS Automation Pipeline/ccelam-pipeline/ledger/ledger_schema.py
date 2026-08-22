"""CCELAM Project Cost Ledger — data contract.

The ledger is the single source of truth for a project's commercial state:
the locked BOQ baseline, every variation, every certificate, every retention
movement, through to the Final Statement. Downstream documents (IPCs, VOs,
financial appraisals, completion certificates, final accounts) are computed
READS of this ledger — they never re-key figures.

Design rules
------------
1. Append-only event log with SHA-256 hash chaining (tamper-evident
   "golden thread" from model GlobalId to certified figure).
2. Issued instruments are immutable. Corrections supersede; they never
   overwrite (CCELAM protect-issued-documents discipline).
3. All money is decimal.Decimal quantised to 2 dp, ROUND_HALF_UP.
   Floats are never used for certified figures.
4. Versioned snapshots carry CCELAM document references:
   CCELAM/LEDGER/[PROJECT]/[YEAR]/[SEQ] Rev [N].

Ref: CCELAM/ARCH/CC365/2026 pipeline build — Stage 4 spine.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

TWO_DP = Decimal("0.01")


def money(value: Any) -> Decimal:
    """Coerce to Decimal at 2 dp, ROUND_HALF_UP (professional rounding)."""
    return Decimal(str(value)).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def canonical_json(obj: Any) -> str:
    """Deterministic JSON for hashing: sorted keys, str-encoded decimals."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


# --------------------------------------------------------------------------
# Header and baseline
# --------------------------------------------------------------------------

class LedgerHeader(BaseModel):
    ledger_ref: str                      # CCELAM/LEDGER/KAATC/2026/001
    project_ref: str
    project_title: str
    employer: str
    contractor: str
    engineer: str                        # Engineer / Employer's Representative
    consultant: str = "CCELAM NK & Associates"
    contract_form: str                   # e.g. "FIDIC Red Book 1999"
    currency: str = "UGX"
    contract_sum: Decimal                # Accepted Contract Amount, excl. VAT
    commencement_date: date
    time_for_completion_days: int
    dnp_days: int = 365                  # Defects Notification Period
    retention_percent: Decimal = Decimal("10")
    retention_limit_percent: Decimal = Decimal("5")   # of contract sum
    advance_payment: Decimal = Decimal("0")
    advance_recovery_percent: Decimal = Decimal("0")  # % of gross interim work
                                                      # deducted until repaid
    vat_percent: Decimal = Decimal("18")
    apply_vat: bool = False              # house rule: only on request

    @field_validator("contract_sum", "advance_payment", mode="before")
    @classmethod
    def _money(cls, v: Any) -> Decimal:
        return money(v)

    @field_serializer("contract_sum", "advance_payment", "retention_percent",
                      "retention_limit_percent", "advance_recovery_percent",
                      "vat_percent")
    def _ser_dec(self, v: Decimal, _info) -> str:
        return str(v)

    @field_serializer("commencement_date")
    def _ser_date(self, v: date, _info) -> str:
        return v.isoformat()


class BOQLine(BaseModel):
    """One measured item in the contract bill. source_guids carries the
    model-element provenance (the golden thread back to geometry)."""
    item_ref: str                        # e.g. "E.10.1"
    work_section: str                    # SMM7 section letter + title
    description: str
    unit: str                            # m2, m3, m, Nr, Item, Sum
    quantity: Decimal
    rate: Decimal
    source_guids: list[str] = Field(default_factory=list)
    provisional: bool = False

    @field_validator("quantity", "rate", mode="before")
    @classmethod
    def _money(cls, v: Any) -> Decimal:
        return Decimal(str(v))

    @property
    def amount(self) -> Decimal:
        return money(self.quantity * self.rate)

    @field_serializer("quantity", "rate")
    def _ser_dec(self, v: Decimal, _info) -> str:
        return str(v)


class Baseline(BaseModel):
    boq_ref: str                         # e.g. "CCELAM/BOQ/KAATC/2026/004 Rev 0"
    measurement_standard: str = "SMM7"
    lines: list[BOQLine]

    @property
    def measured_total(self) -> Decimal:
        return money(sum((l.amount for l in self.lines), Decimal("0")))


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------

class EventType(str, Enum):
    BASELINE_LOCKED = "BASELINE_LOCKED"
    VARIATION = "VARIATION"
    CLAIM = "CLAIM"
    IPC_CERTIFIED = "IPC_CERTIFIED"
    TAKING_OVER = "TAKING_OVER"
    PERFORMANCE_CERTIFICATE = "PERFORMANCE_CERTIFICATE"
    RETENTION_RELEASE = "RETENTION_RELEASE"
    FINAL_STATEMENT = "FINAL_STATEMENT"
    SNAPSHOT_ISSUED = "SNAPSHOT_ISSUED"
    NOTE = "NOTE"


class LedgerEvent(BaseModel):
    seq: int
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: EventType
    payload: dict[str, Any]
    prev_hash: str
    hash: str = ""

    def compute_hash(self) -> str:
        body = canonical_json({
            "seq": self.seq, "event_id": self.event_id,
            "timestamp": self.timestamp, "type": self.type.value,
            "payload": self.payload, "prev_hash": self.prev_hash,
        })
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Computed instruments (these are READS — they live in event payloads
# once certified, and become immutable there)
# --------------------------------------------------------------------------

class CertificateFigures(BaseModel):
    """Interim Payment Certificate computation (FIDIC SC 14.3 / 14.6),
    in the CCELAM three-column discipline: previous / this period / to date."""
    cert_no: int
    period_end: str
    # gross build-up, to date
    measured_work_todate: str
    variations_todate: str
    materials_on_site: str
    gross_todate: str
    # deductions
    retention_todate: str
    advance_recovery_todate: str
    # movement
    previous_net_certified: str
    net_this_certificate: str
    vat_this_certificate: str
    payable_this_certificate: str
    remeasure_flags: list[str] = Field(default_factory=list)


class LedgerState(BaseModel):
    """Running commercial position — recomputed from the event log."""
    original_contract_sum: str
    approved_variations: str
    determined_claims: str
    revised_contract_sum: str
    gross_certified_todate: str
    retention_held: str
    retention_released: str
    advance_outstanding: str
    net_certified_todate: str
    certificates_issued: int
    taking_over_achieved: bool
    performance_certificate_issued: bool
    final_statement_issued: bool
