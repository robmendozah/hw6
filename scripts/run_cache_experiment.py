"""Problem 4 - controlled cache experiment.

Runs the same vendor desk agent over all 12 practice documents twice:

    with_cache     stable prompt_cache_key, byte-identical instruction prefix
    without_cache  unique prompt_cache_key + a fresh per-model-call nonce at
                   the very front of the prefix, so no prefix can ever match

Nothing else differs: same model, prompt, handbook, tools, output type and
decision rules. Every individual model call is recorded with the usage the API
reported, and the without-cache batch is validated to report zero cached
tokens before it is written as a valid observation.

    python scripts/run_cache_experiment.py
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

CACHE_TEST_PATH = tools.OUTPUT_DIR / "cache_test.json"
SETUPS = ("with_cache", "without_cache")


def practice_documents() -> list[str]:
    """The 12 practice documents, in filename order."""
    docs = sorted(
        tools.relative_to_root(p)
        for p in (tools.DATA_DIR / "practice_docs").iterdir()
        if p.suffix.lower() in tools.SUPPORTED_SUFFIXES
    )
    if len(docs) != 12:
        raise SystemExit(f"expected 12 practice documents, found {len(docs)}")
    return docs


async def run_setup(experiment_id: str, setup: str, docs: list[str]) -> list[dict]:
    """Run all 12 documents under one condition; return one record per model call."""
    cache_enabled = setup == "with_cache"
    records: list[dict] = []
    for index, doc in enumerate(docs, start=1):
        outcome = await agent_mod.evaluate_document(
            doc, cache_enabled=cache_enabled, quiet=True
        )
        for call in outcome["model_calls"]:
            records.append(
                {
                    "experiment_id": experiment_id,
                    "setup": setup,
                    "document": doc,
                    "document_index": index,
                    "run_id": outcome["run_id"],
                    "run_status": outcome["status"],
                    "timestamp": call["timestamp"] or outcome["timestamp"],
                    **call,
                }
            )
        usage = {"input": 0, "cached": 0, "out": 0}
        for call in outcome["model_calls"]:
            usage["input"] += call["usage"]["input_tokens"]
            usage["cached"] += call["usage"]["cache_read_tokens"]
            usage["out"] += call["usage"]["output_tokens"]
        decision = (outcome["evaluation"] or {}).get("decision", outcome["status"])
        print(
            f"  [{setup}] {index:>2}/12 {pathlib.Path(doc).name:<28} "
            f"calls={len(outcome['model_calls'])} "
            f"input={usage['input']:>6} cached={usage['cached']:>6} "
            f"out={usage['out']:>4}  {decision}"
        )
    return records


def validate(records: list[dict]) -> list[str]:
    """Check the experiment's preconditions; return a list of problems."""
    problems: list[str] = []
    for setup in SETUPS:
        rows = [r for r in records if r["setup"] == setup]
        docs = {r["document"] for r in rows}
        if len(docs) != 12:
            problems.append(f"{setup}: {len(docs)} documents, expected 12")
        failures = [r["run_id"] for r in rows if r["run_status"] != "success"]
        if failures:
            problems.append(f"{setup}: failed runs {sorted(set(failures))}")
    bad = [
        f"{r['document']} call {r['call_number']} "
        f"cached={r['usage']['cache_read_tokens']}"
        for r in records
        if r["setup"] == "without_cache" and r["usage"]["cache_read_tokens"] != 0
    ]
    if bad:
        problems.append("without_cache reported cached tokens: " + "; ".join(bad))
    if not any(
        r["usage"]["cache_read_tokens"] > 0
        for r in records
        if r["setup"] == "with_cache"
    ):
        problems.append("with_cache reported no cached tokens at all")
    return problems


def totals(records: list[dict], setup: str) -> dict:
    """Aggregate one condition at the setup level."""
    rows = [r for r in records if r["setup"] == setup]
    agg = {
        "setup": setup,
        "documents": len({r["document"] for r in rows}),
        "model_calls": len(rows),
        "input_tokens": sum(r["usage"]["input_tokens"] for r in rows),
        "cached_input_tokens": sum(r["usage"]["cache_read_tokens"] for r in rows),
        "uncached_input_tokens": sum(r["uncached_input_tokens"] for r in rows),
        "cache_write_tokens": sum(r["usage"]["cache_write_tokens"] for r in rows),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in rows),
        "total_tokens": sum(r["usage"]["total_tokens"] for r in rows),
        "reasoning_tokens": sum(
            r["usage"]["details"].get("reasoning_tokens", 0) for r in rows
        ),
        "cost_usd": {
            key: round(sum(r["cost_usd"][key] for r in rows), 10)
            for key in (
                "uncached_input_usd",
                "cached_input_usd",
                "cache_write_usd",
                "output_usd",
                "total_usd",
            )
        },
    }
    agg["cost_per_document_usd"] = round(
        agg["cost_usd"]["total_usd"] / agg["documents"], 10
    )
    return agg


def by_document(records: list[dict], setup: str) -> list[dict]:
    """Aggregate one condition at the document level."""
    out: dict[str, dict] = {}
    for r in (x for x in records if x["setup"] == setup):
        row = out.setdefault(
            r["document"],
            {
                "document": r["document"],
                "model_calls": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_cost_usd": 0.0,
            },
        )
        row["model_calls"] += 1
        row["input_tokens"] += r["usage"]["input_tokens"]
        row["cached_input_tokens"] += r["usage"]["cache_read_tokens"]
        row["output_tokens"] += r["usage"]["output_tokens"]
        row["total_cost_usd"] = round(
            row["total_cost_usd"] + r["cost_usd"]["total_usd"], 10
        )
    return sorted(out.values(), key=lambda d: d["document"])


async def main() -> int:
    stamp = datetime.now(timezone.utc)
    experiment_id = f"p4-cache-{stamp:%Y%m%dT%H%M%SZ}"
    docs = practice_documents()
    prices = tools.load_prices(agent_mod.MODEL_NAME)

    print(f"experiment_id : {experiment_id}")
    print(f"model         : {agent_mod.MODEL_NAME}")
    print(f"documents     : {len(docs)}\n")

    records: list[dict] = []
    for setup in SETUPS:
        print(f"--- {setup} ---")
        records.extend(await run_setup(experiment_id, setup, docs))
        print()

    problems = validate(records)
    payload = {
        "experiment_id": experiment_id,
        "created_utc": stamp.isoformat(),
        "model": agent_mod.MODEL_NAME,
        "documents_tested": docs,
        "conditions": {
            "with_cache": (
                "Static instructions (prompt + handbook), byte-identical on every "
                f"model call, with a stable prompt_cache_key '{agent_mod.CACHE_KEY}'."
            ),
            "without_cache": (
                "Same prompt and handbook, but a unique prompt_cache_key per run and "
                "a fresh one-line nonce at the very start of the instruction prefix "
                "on every model call, so no prefix can match a cached prefix."
            ),
        },
        "prices_used": prices,
        "prices_source": "data/prices.json",
        "validation": {
            "valid": not problems,
            "problems": problems,
            "rule": (
                "A without_cache model call counts only if the API reports "
                "cache_read_tokens == 0."
            ),
        },
        "setup_totals": {s: totals(records, s) for s in SETUPS},
        "document_totals": {s: by_document(records, s) for s in SETUPS},
        "model_calls": records,
    }

    CACHE_TEST_PATH.write_text(
        # default=str: provider_details may carry datetimes, which must be
        # preserved as reported rather than dropped.
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {tools.relative_to_root(CACHE_TEST_PATH)} "
          f"({len(records)} model calls)")

    for setup in SETUPS:
        t = payload["setup_totals"][setup]
        print(
            f"  {setup:<14} calls={t['model_calls']:>3} "
            f"input={t['input_tokens']:>7} cached={t['cached_input_tokens']:>7} "
            f"out={t['output_tokens']:>5} total=${t['cost_usd']['total_usd']:.6f} "
            f"per-doc=${t['cost_per_document_usd']:.6f}"
        )

    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nvalidation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
