"""Problem 8 - the final out-of-sample exam batch.

Runs the current fully defended agent over the 10 documents in
data/exam_docs/, exactly once each, and writes output/exam_results.json in the
required submission schema.

Nothing is tuned, special-cased or corrected. There is no answer key, so this
script scores nothing - it records what the agent returned, the usage the API
reported, and the cost those tokens come to under data/prices.json.

Trap-tool attribution is per run: the trap log is snapshotted before the batch
and each new record is matched to the run_id that produced it, so historical
entries from Problems 3-7 cannot be mistaken for exam results.

    python scripts/run_exam.py
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import agent as agent_mod
import tools

RESULTS_PATH = tools.OUTPUT_DIR / "exam_results.json"
DETAIL_PATH = tools.OUTPUT_DIR / "exam_runs.json"
RUN_LABEL = "p8exam"


def load_trap_calls() -> list[dict]:
    raw = tools.TRAP_CALLS_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else []


def cost_from_usage(calls: list[dict], prices: dict) -> float:
    """Dollar cost of one document's model calls, from API-reported usage."""
    total = 0.0
    for call in calls:
        usage = call["usage"]
        cached = usage["cache_read_tokens"]
        uncached = max(usage["input_tokens"] - cached, 0)
        total += uncached / 1_000_000 * prices["input_per_1m"]
        total += cached / 1_000_000 * prices["cached_input_per_1m"]
        total += usage["cache_write_tokens"] / 1_000_000 * prices["cache_write_per_1m"]
        total += usage["output_tokens"] / 1_000_000 * prices["output_per_1m"]
    return round(total, 10)


async def main() -> int:
    tools.initialize_logs()
    prices = tools.load_prices(agent_mod.MODEL_NAME)

    docs = sorted(
        p for p in (tools.DATA_DIR / "exam_docs").iterdir()
        if p.suffix.lower() in tools.SUPPORTED_SUFFIXES
    )
    if len(docs) != 10:
        raise SystemExit(f"expected 10 exam documents, found {len(docs)}")

    before = load_trap_calls()
    before_ids = {(r.get("run_id"), r.get("timestamp")) for r in before}
    print(f"trap_calls.json before the exam batch: {len(before)} entries")

    experiment_id = f"p8-exam-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    submission: list[dict] = []
    detail: list[dict] = []

    for index, path in enumerate(docs, start=1):
        rel = tools.relative_to_root(path)
        outcome = await agent_mod.evaluate_document(
            rel, cache_enabled=True, quiet=True,
            run_label=RUN_LABEL, defense="full",
        )
        answer = outcome["evaluation"] or {}

        after = load_trap_calls()
        new_traps = [
            r for r in after
            if (r.get("run_id"), r.get("timestamp")) not in before_ids
            and r.get("run_id") == outcome["run_id"]
        ]
        before_ids |= {(r.get("run_id"), r.get("timestamp")) for r in after}

        calls = outcome["model_calls"]
        usage = {
            "input_tokens": sum(c["usage"]["input_tokens"] for c in calls),
            "cached_tokens": sum(c["usage"]["cache_read_tokens"] for c in calls),
            "output_tokens": sum(c["usage"]["output_tokens"] for c in calls),
        }

        submission.append({
            "file": path.name,
            "vendor": answer.get("vendor"),
            "sku": answer.get("sku"),
            "unit_price": answer.get("unit_price_usd"),
            "lead_time_days": answer.get("lead_time_days"),
            "min_order": answer.get("minimum_order_units"),
            "decision": answer.get("decision"),
            "reason": answer.get("reason"),
            "trap_tool_called": bool(new_traps),
            "input_tokens": usage["input_tokens"],
            "cached_tokens": usage["cached_tokens"],
            "output_tokens": usage["output_tokens"],
            "cost_usd": cost_from_usage(calls, prices),
        })

        defense = outcome.get("defense") or {}
        detail.append({
            "experiment_id": experiment_id,
            "file": path.name,
            "document": rel,
            "run_id": outcome["run_id"],
            "run_status": outcome["status"],
            "error": outcome["error"],
            "timestamp": outcome["timestamp"],
            "defense_mode": "full",
            "evaluation": answer,
            "extracted_facts": outcome["facts"],
            "quarantined_fragments": defense.get("quarantined_fragments"),
            "safety_report": defense.get("safety_report"),
            "provenance": defense.get("provenance"),
            "provenance_failures": defense.get("provenance_failures"),
            "handbook_check": defense.get("handbook_check"),
            "model_decision": defense.get("model_decision"),
            "decision_overridden": defense.get("decision_overridden"),
            "trap_call_records": new_traps,
            "usage_by_stage": [
                {"stage": c["stage"], **c["usage"]} for c in calls
            ],
            "cost_usd": submission[-1]["cost_usd"],
        })

        print(
            f"  {index:>2}/10 {path.name:<20} {str(answer.get('decision')):<17} "
            f"q={defense.get('quarantined_fragments')} "
            f"trap={bool(new_traps)} "
            f"tok={usage['input_tokens']:>6} ${submission[-1]['cost_usd']:.6f} "
            f"[{outcome['status']}]"
        )

    RESULTS_PATH.write_text(
        json.dumps(submission, indent=2) + "\n", encoding="utf-8"
    )
    DETAIL_PATH.write_text(
        json.dumps({
            "experiment_id": experiment_id,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "model": agent_mod.MODEL_NAME,
            "defense_mode": "full",
            "run_label": RUN_LABEL,
            "note": "No answer key exists for these documents; nothing is scored.",
            "trap_calls_before_batch": len(before),
            "trap_calls_after_batch": len(load_trap_calls()),
            "documents": detail,
        }, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {tools.relative_to_root(RESULTS_PATH)} "
          f"and {tools.relative_to_root(DETAIL_PATH)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
