"""Problem 6 - attribute the cost of each defense layer, from measurements.

Three layers, three different kinds of overhead:

* CODE   - deterministic and local. It makes no model call at all, so it adds
           0 model tokens by itself. What it does change is how much document
           text reaches the model, and that delta is measured here per
           document with tiktoken. It can be negative, and usually is: hidden
           fragments are withheld and replaced by a short notice.
* PROMPT - the defended prompt is longer than the Problem 3 prompt. Measured
           as the token difference between the two instruction prefixes.
* DESIGN - a second model call (the decision stage) that the undefended agent
           does not make. Measured from actual API-reported usage.

Undefended baseline comes from the Problem 4 with_cache batch, which ran the
same 12 documents through the undefended agent under the same cache setting.

    python scripts/measure_defense_overhead.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import tiktoken

import safe_reader
import tools

ENC = tiktoken.get_encoding("o200k_base")
OUT_PATH = tools.OUTPUT_DIR / "defense_overhead.json"


def count(text: str) -> int:
    return len(ENC.encode(text))


def prompt_layer() -> dict:
    """Instruction-prefix tokens, defended vs undefended."""
    p = tools.PROMPTS_DIR
    undef = count((p / "prompt_undefended.md").read_text(encoding="utf-8"))
    defended = count((p / "prompt.md").read_text(encoding="utf-8"))
    extraction = count((p / "extraction_prompt.md").read_text(encoding="utf-8"))
    decision = count((p / "decision_prompt.md").read_text(encoding="utf-8"))
    return {
        "undefended_prompt_tokens": undef,
        "defended_prompt_tokens": defended,
        "extraction_stage_prompt_tokens": extraction,
        "decision_stage_prompt_tokens": decision,
        "extraction_prefix_delta_tokens": defended + extraction - undef,
        "decision_prefix_delta_tokens": defended + decision - undef,
        "model_calls_added": 0,
        "note": (
            "The defended prompt replaces the undefended one; the delta is "
            "paid on the instruction prefix of every model call, which is "
            "also the part that caches."
        ),
    }


def code_layer() -> dict:
    """Document-text tokens the model receives, defended vs undefended."""
    rows = []
    for path in sorted((tools.DATA_DIR / "practice_docs").iterdir()):
        if path.suffix.lower() not in tools.SUPPORTED_SUFFIXES:
            continue
        undef_text = (
            tools.UNTRUSTED_HEADER.format(path=tools.relative_to_root(path))
            + tools.extract_document_text(path)
            + tools.UNTRUSTED_FOOTER
        )
        safe_doc = safe_reader.read_safely(path)
        safe_doc.path = tools.relative_to_root(path)
        rows.append(
            {
                "document": path.name,
                "undefended_document_tokens": count(undef_text),
                "defended_document_tokens": count(safe_doc.model_view()),
                "quarantined_fragments": len(safe_doc.quarantined),
            }
        )
    for row in rows:
        row["delta_tokens"] = (
            row["defended_document_tokens"] - row["undefended_document_tokens"]
        )
    total = sum(r["delta_tokens"] for r in rows)
    return {
        "model_calls_added": 0,
        "additional_model_tokens_from_the_layer_itself": 0,
        "documents": rows,
        "total_delta_tokens": total,
        "avg_delta_tokens_per_document": round(total / len(rows), 2),
        "note": (
            "The code layer is entirely local and deterministic: it makes no "
            "model call. The delta above is the change in how much document "
            "text is sent, which the extraction stage then pays for once."
        ),
    }


def main() -> int:
    defended = json.loads(
        (tools.OUTPUT_DIR / "defense_results.json").read_text(encoding="utf-8")
    )
    cache_test = json.loads(
        (tools.OUTPUT_DIR / "cache_test.json").read_text(encoding="utf-8")
    )
    baseline = cache_test["setup_totals"]["with_cache"]

    d = defended["summary"]
    docs = d["documents"]

    # Per-document costs, so the median can be reported alongside the mean:
    # one cache miss can move a 12-document mean a long way.
    defended_costs = sorted(e["cost_usd_total"] for e in defended["documents"])
    undef_costs = sorted(
        row["total_cost_usd"] for row in cache_test["document_totals"]["with_cache"]
    )

    def median(values):
        n = len(values)
        return (
            values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
        )

    design = {
        "model_calls_added_per_document": 1,
        "stage": "decision",
        "input_tokens_total": d["decision_input_tokens"],
        "avg_input_tokens_per_document": round(d["decision_input_tokens"] / docs, 2),
        "cost_usd_total": d["decision_cost_usd"],
        "avg_cost_per_document_usd": round(d["decision_cost_usd"] / docs, 10),
        "note": (
            "The decision stage is a second model call that the undefended "
            "agent never makes. It carries the handbook again, which is why "
            "it is the largest single component of the overhead."
        ),
    }

    payload = {
        "baseline": {
            "source": "output/cache_test.json -> setup_totals.with_cache",
            "description": "undefended Problem 3 agent, same 12 documents, cache on",
            "documents": baseline["documents"],
            "model_calls": baseline["model_calls"],
            "input_tokens": baseline["input_tokens"],
            "output_tokens": baseline["output_tokens"],
            "total_cost_usd": baseline["cost_usd"]["total_usd"],
            "avg_input_tokens_per_document": round(
                baseline["input_tokens"] / baseline["documents"], 2
            ),
            "avg_cost_per_document_usd": baseline["cost_per_document_usd"],
            "median_cost_per_document_usd": round(median(undef_costs), 10),
        },
        "defended": {
            "source": "output/defense_results.json",
            "documents": docs,
            "model_calls": d["documents"] and sum(
                len(e["model_calls"]) for e in defended["documents"]
            ),
            "input_tokens": d["input_tokens"],
            "output_tokens": d["output_tokens"],
            "total_cost_usd": d["total_cost_usd"],
            "avg_input_tokens_per_document": d["avg_input_tokens_per_document"],
            "avg_cost_per_document_usd": d["avg_cost_per_document_usd"],
            "median_cost_per_document_usd": round(median(defended_costs), 10),
            "extraction_stage_cost_usd": d["extraction_cost_usd"],
            "decision_stage_cost_usd": d["decision_cost_usd"],
        },
        "layers": {
            "code": code_layer(),
            "prompt": prompt_layer(),
            "design": design,
        },
    }

    totals = payload["defended"]
    base = payload["baseline"]
    payload["incremental"] = {
        "extra_input_tokens_per_document": round(
            totals["avg_input_tokens_per_document"]
            - base["avg_input_tokens_per_document"],
            2,
        ),
        "extra_cost_per_document_usd": round(
            totals["avg_cost_per_document_usd"] - base["avg_cost_per_document_usd"], 10
        ),
        "extra_cost_per_document_usd_median_basis": round(
            totals["median_cost_per_document_usd"]
            - base["median_cost_per_document_usd"],
            10,
        ),
        "total_incremental_cost_12_documents_usd": round(
            totals["total_cost_usd"] - base["total_cost_usd"], 10
        ),
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {tools.relative_to_root(OUT_PATH)}\n")
    print(json.dumps(
        {k: v for k, v in payload.items() if k != "layers"}, indent=2
    ))
    print("\ncode layer:", json.dumps(
        {k: v for k, v in payload["layers"]["code"].items() if k != "documents"},
        indent=2,
    ))
    print("prompt layer:", json.dumps(payload["layers"]["prompt"], indent=2))
    print("design layer:", json.dumps(design, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
