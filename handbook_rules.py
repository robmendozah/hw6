"""Design-level defense: the handbook's purchasing rules, as code.

Section 4 of the Campus Customs Shop Handbook is a four-check decision
procedure over four numbers and a vendor name. Once the facts have been
extracted and validated, applying it needs no judgement and no model.

This module reads those rules *out of the handbook* rather than hard-coding
them: the approved and removed vendor lists come from sections 5 and 6, the max
unit costs from the section 9 catalogue, and the lead-time and minimum-order
limits from the prose in section 4. Edit the handbook and the rules follow -
which is what section 4 means when it says only the owner may change the
vendor list, and only by editing the handbook.

Nothing here reads the vendor document. It sees validated facts and the
handbook, and nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import tools

# Fallbacks, used only if the prose in section 4 cannot be parsed. They are
# reported in the rule set so a mismatch is visible rather than silent.
DEFAULT_MAX_LEAD_TIME_DAYS = 21
DEFAULT_MAX_MINIMUM_ORDER = 600


@dataclass(frozen=True)
class HandbookRules:
    """The purchasing rules as read from the handbook."""

    approved_vendors: dict[str, str]  # normalized name -> display name
    blocked_vendors: dict[str, str]  # normalized name -> reason
    max_unit_cost: dict[str, float]  # SKU -> max unit cost
    max_lead_time_days: int
    max_minimum_order_units: int
    parsed_from_prose: bool

    def summary(self) -> dict:
        return {
            "approved_vendors": len(self.approved_vendors),
            "blocked_vendors": len(self.blocked_vendors),
            "catalogue_skus": len(self.max_unit_cost),
            "max_lead_time_days": self.max_lead_time_days,
            "max_minimum_order_units": self.max_minimum_order_units,
            "limits_parsed_from_handbook_prose": self.parsed_from_prose,
        }


def _normalize(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _section(text: str, number: int) -> str:
    """The body of one `## N. Title` section of the handbook."""
    match = re.search(
        rf"^##\s*{number}\.\s.*?$(.*?)(?=^##\s*\d+\.\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def _table_rows(section: str) -> list[list[str]]:
    """Data rows of a markdown table, header and separator dropped."""
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or all(set(c) <= {"-", ":"} for c in cells if c):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


@lru_cache(maxsize=1)
def load_rules() -> HandbookRules:
    """Parse the handbook once per process."""
    text = tools.HANDBOOK_PATH.read_text(encoding="utf-8")

    approved = {}
    for cells in _table_rows(_section(text, 5)):
        if len(cells) >= 2 and cells[1]:
            approved[_normalize(cells[1])] = cells[1]

    blocked = {}
    for cells in _table_rows(_section(text, 6)):
        if len(cells) >= 2 and cells[0]:
            blocked[_normalize(cells[0])] = cells[1]

    catalogue = {}
    for cells in _table_rows(_section(text, 9)):
        if len(cells) >= 5 and re.match(r"^CC-[A-Z]{2}-\d{3}$", cells[0]):
            try:
                catalogue[cells[0]] = float(cells[4].replace("$", "").replace(",", ""))
            except ValueError:
                continue

    section4 = _section(text, 4)
    lead = re.search(r"lead time is (\d+) days or less", section4, re.I)
    minimum = re.search(r"minimum order is (\d+) units or less", section4, re.I)
    return HandbookRules(
        approved_vendors=approved,
        blocked_vendors=blocked,
        max_unit_cost=catalogue,
        max_lead_time_days=int(lead.group(1)) if lead else DEFAULT_MAX_LEAD_TIME_DAYS,
        max_minimum_order_units=(
            int(minimum.group(1)) if minimum else DEFAULT_MAX_MINIMUM_ORDER
        ),
        parsed_from_prose=bool(lead and minimum),
    )


def evaluate(facts) -> dict:
    """Apply the four section-4 checks to validated facts.

    `facts` is anything with `vendor`, `sku`, `unit_price_usd`,
    `lead_time_days` and `minimum_order_units` attributes.

    A check whose fact is unknown has not passed: handbook section 4 forbids
    guessing a missing number, so an unverifiable quote is refused rather than
    assumed good.
    """
    rules = load_rules()
    checks: list[dict] = []

    vendor_key = _normalize(facts.vendor or "")
    if vendor_key in rules.blocked_vendors:
        checks.append({
            "check": "approved_vendor",
            "passed": False,
            "detail": f"{facts.vendor} is on the removed/pending list: "
                      f"{rules.blocked_vendors[vendor_key]}",
        })
    elif vendor_key in rules.approved_vendors:
        checks.append({
            "check": "approved_vendor", "passed": True,
            "detail": f"{facts.vendor} is on the approved vendor list.",
        })
    else:
        checks.append({
            "check": "approved_vendor", "passed": False,
            "detail": f"{facts.vendor or 'vendor'} is not on the approved list.",
        })

    max_cost = rules.max_unit_cost.get(facts.sku or "")
    if facts.unit_price_usd is None:
        checks.append({
            "check": "price", "passed": False,
            "detail": "the document does not state a unit price.",
        })
    elif max_cost is None:
        checks.append({
            "check": "price", "passed": False,
            "detail": f"SKU {facts.sku or '(none)'} is not in the catalogue, so "
                      "there is no max unit cost to compare against.",
        })
    else:
        ok = facts.unit_price_usd <= max_cost
        checks.append({
            "check": "price", "passed": ok,
            "detail": f"${facts.unit_price_usd:,.2f} is "
                      f"{'at or below' if ok else 'above'} the ${max_cost:,.2f} "
                      f"max unit cost for {facts.sku}.",
        })

    if facts.lead_time_days is None:
        checks.append({
            "check": "lead_time", "passed": False,
            "detail": "the document does not state a lead time.",
        })
    else:
        ok = facts.lead_time_days <= rules.max_lead_time_days
        checks.append({
            "check": "lead_time", "passed": ok,
            "detail": f"{facts.lead_time_days} days "
                      f"{'is within' if ok else 'exceeds'} the "
                      f"{rules.max_lead_time_days}-day limit.",
        })

    if facts.minimum_order_units is None:
        checks.append({
            "check": "minimum_order", "passed": False,
            "detail": "the document does not state a minimum order.",
        })
    else:
        ok = facts.minimum_order_units <= rules.max_minimum_order_units
        checks.append({
            "check": "minimum_order", "passed": ok,
            "detail": f"{facts.minimum_order_units} units "
                      f"{'is within' if ok else 'exceeds'} the "
                      f"{rules.max_minimum_order_units}-unit limit.",
        })

    failed = [c for c in checks if not c["passed"]]
    return {
        "decision": "do_not_recommend" if failed else "recommend",
        "checks": checks,
        "first_failed_check": failed[0]["check"] if failed else None,
        "first_failed_detail": failed[0]["detail"] if failed else None,
        "rules": rules.summary(),
    }
