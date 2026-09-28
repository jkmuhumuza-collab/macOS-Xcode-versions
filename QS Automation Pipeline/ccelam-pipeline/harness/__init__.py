"""CCELAM coding harness — puts every decision back in context.

    context inputs  ->  select  ->  host validation  ->  tool runs  ->  evidence
    (models, tools,     (model +     (policy, safety,     (in the       (results, logs,
     permissions)        tool+plan)   scope)               harness)      artifacts, diff)

Selection is not permission: a plan can be selected and still refused
before any tool runs. Provider-owned internals (model runtime, provider
tool execution, telemetry, external ACP loops) stay outside the boundary.
"""

from .context import Context, load_context
from .evidence import EvidenceLog
from .harness import Harness, RunReport
from .selector import Plan, Selection, select
from .validation import Decision, validate

__all__ = ["Context", "load_context", "EvidenceLog", "Harness", "RunReport",
           "Plan", "Selection", "select", "Decision", "validate"]
