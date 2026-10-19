"""Structured types for the Campus Customs vendor desk agent.

Everything the agent is allowed to return is defined here. The model's reply
is validated against `VendorEvaluation` before it reaches the terminal or any
log file, so a malformed or out-of-vocabulary answer fails loudly instead of
being written out as if it were a real recommendation.

Facts the vendor document does not state are represented as `None` ("unknown")
rather than guessed. Handbook section 4 requires this.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# The only two decisions the vendor desk may issue. Handbook section 4.
Decision = Literal["recommend", "do_not_recommend"]

# Campus Customs SKUs look like CC-HD-006 / CC-PG-010.
SKU_PATTERN = re.compile(r"^CC-[A-Z]{2}-\d{3}$")


class VendorEvaluation(BaseModel):
    """One vendor document, reduced to the fields handbook section 13 asks for."""

    model_config = {"extra": "forbid"}

    vendor: str = Field(
        min_length=1,
        max_length=120,
        description="Vendor name exactly as the document states it.",
    )
    sku: str | None = Field(
        default=None,
        description="Campus Customs SKU quoted in the document, or null if absent.",
    )
    unit_price_usd: float | None = Field(
        default=None,
        gt=0,
        description="Quoted price per unit in USD, or null if the document omits it.",
    )
    lead_time_days: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Lead time converted to days, or null if the document omits it.",
    )
    minimum_order_units: int | None = Field(
        default=None,
        ge=0,
        description="Minimum order in units, or null if the document omits it.",
    )
    decision: Decision = Field(
        description="recommend only if all four handbook section 4 checks pass.",
    )
    reason: str = Field(
        min_length=10,
        max_length=300,
        description="One sentence naming the handbook check that decided it.",
    )

    @field_validator("vendor", "reason")
    @classmethod
    def _single_line(cls, value: str) -> str:
        """Collapse whitespace so a log line cannot be broken up by the model."""
        return " ".join(value.split())

    @field_validator("sku")
    @classmethod
    def _sku_shape(cls, value: str | None) -> str | None:
        """Accept only well-formed Campus Customs SKUs; anything else is unknown."""
        if value is None:
            return None
        candidate = value.strip().upper()
        if not SKU_PATTERN.match(candidate):
            raise ValueError(
                f"{value!r} is not a Campus Customs SKU (expected CC-XX-000). "
                "Use null if the document does not state one."
            )
        return candidate

    @model_validator(mode="after")
    def _reason_is_one_sentence(self) -> VendorEvaluation:
        """Handbook section 13 asks for a one-sentence reason, so enforce it."""
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", self.reason.strip()) if s]
        if len(sentences) > 1:
            raise ValueError(
                "reason must be exactly one sentence; "
                f"got {len(sentences)}: {self.reason!r}"
            )
        return self


class ToolCallRecord(BaseModel):
    """One tool invocation, as reconstructed from the run's message history."""

    tool_name: str = Field(description="Name of the tool the model called.")
    arguments: dict = Field(
        default_factory=dict,
        description="Sanitized call arguments; document text is never copied here.",
    )
    result_summary: str = Field(
        default="",
        max_length=400,
        description="Short description of what the tool returned, not its full text.",
    )


class UsageRecord(BaseModel):
    """Actual API usage and the dollar cost derived from data/prices.json."""

    run_id: str = Field(description="Ties this record to the audit trail entry.")
    timestamp: str = Field(description="UTC ISO-8601 time the run finished.")
    document: str = Field(description="Repository-relative path of the document.")
    model: str = Field(description="Model actually called.")
    requests: int = Field(ge=0, description="Model HTTP requests made in the run.")
    input_tokens_total: int = Field(
        ge=0, description="Total prompt tokens the API reported, cached ones included."
    )
    cached_input_tokens: int = Field(
        ge=0, description="Prompt tokens served from cache, billed at the cached rate."
    )
    uncached_input_tokens: int = Field(
        ge=0, description="Prompt tokens billed at the standard input rate."
    )
    cache_write_tokens: int = Field(
        ge=0, description="Tokens written into the cache, billed at the write rate."
    )
    output_tokens: int = Field(ge=0, description="Completion tokens the API reported.")
    tool_calls: int = Field(ge=0, description="Tool calls the model made in the run.")
    usage_details: dict = Field(
        default_factory=dict,
        description="Any further counters the provider returned, kept verbatim.",
    )
    cost_usd: dict = Field(
        description="Per-category and total cost, priced from data/prices.json.",
    )


class AuditRecord(BaseModel):
    """What happened in one run, without any hidden reasoning."""

    run_id: str = Field(description="Unique id for this run.")
    timestamp: str = Field(description="UTC ISO-8601 time the run finished.")
    document: str = Field(description="Repository-relative path of the document.")
    model: str = Field(description="Model actually called.")
    status: Literal["success", "failure"] = Field(
        description="Whether the run produced a valid structured evaluation."
    )
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list, description="Every tool call, in the order made."
    )
    final_answer: dict | None = Field(
        default=None, description="The validated VendorEvaluation, or null on failure."
    )
    error: str | None = Field(
        default=None, max_length=500, description="Short failure message, if any."
    )


# ------------------------------------------------- Problem 6: defended path


class VendorFacts(BaseModel):
    """Stage 1 output: facts extracted from the human-visible document only.

    This is the trust boundary. Raw document text stops here; only these
    validated fields travel on to the decision stage. Each fact must be
    accompanied by the visible line it came from, which the code then checks
    really appears in the visible text - so a value the model invented, or one
    it drew from quarantined content, fails validation instead of becoming a
    purchasing fact.
    """

    model_config = {"extra": "forbid"}

    vendor: str = Field(min_length=1, max_length=120)
    sku: str | None = Field(default=None)
    unit_price_usd: float | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    minimum_order_units: int | None = Field(default=None, ge=0)
    evidence: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "field name -> the exact line of visible document text it came "
            "from. Required for every non-null field."
        ),
    )

    @field_validator("vendor")
    @classmethod
    def _single_line(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("sku")
    @classmethod
    def _sku_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip().upper()
        if not SKU_PATTERN.match(candidate):
            raise ValueError(
                f"{value!r} is not a Campus Customs SKU (expected CC-XX-000). "
                "Use null if the visible document does not state one."
            )
        return candidate


class FieldProvenance(BaseModel):
    """Whether one extracted fact is actually supported by visible text."""

    field_name: str
    value: str | None
    evidence: str | None = None
    found_in_visible_text: bool = False
    note: str = ""


class DefenseMetadata(BaseModel):
    """Which defenses ran, and what they saw."""

    mode: Literal["none", "full"]
    code_defense: bool
    design_defense: bool
    prompt_defense: bool
    reader: str
    quarantined_fragments: int = 0
    safety_report: dict = Field(default_factory=dict)
    provenance: list[FieldProvenance] = Field(default_factory=list)
    provenance_failures: list[str] = Field(default_factory=list)
    handbook_check: dict = Field(default_factory=dict)
    model_decision: str | None = None
    decision_overridden: bool = False
    dangerous_tools_exposed_to_agent: list[str] = Field(default_factory=list)
    approvals: dict = Field(default_factory=dict)
