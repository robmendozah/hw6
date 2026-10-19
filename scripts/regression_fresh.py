"""Regression check with gateway response-replay defeated.

Re-running the 12 practice documents with caching on returned byte-identical
results AND identical provider_response_ids, i.e. the gateway replayed the
earlier responses instead of sampling again. That confirms nothing about the
hardened reader. Running with cache_enabled=False puts a fresh nonce at the
front of the prefix, so every call is genuinely generated.
"""
import asyncio, json, pathlib, sys
from datetime import datetime, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import agent as agent_mod, tools
from run_attack_test import FIELD_MAP, fields_match, normalize_text

OUT = tools.OUTPUT_DIR / "hardening_regression.json"

async def main():
    key = {r["file"]: r for r in json.loads(
        (tools.DATA_DIR / "practice_key.json").read_text(encoding="utf-8"))}
    docs = sorted(p for p in (tools.DATA_DIR / "practice_docs").iterdir()
                  if p.suffix.lower() in tools.SUPPORTED_SUFFIXES)
    rows, ids = [], set()
    for i, path in enumerate(docs, 1):
        exp = key[path.name]
        o = await agent_mod.evaluate_document(
            tools.relative_to_root(path), cache_enabled=False, quiet=True,
            run_label="hardreg", defense="full")
        a = o["evaluation"] or {}
        m = {f"{k}_match": fields_match(k, exp.get(k), a.get(v))
             for k, v in FIELD_MAP.items()}
        dec = (normalize_text(exp["decision"]) == normalize_text(a["decision"])
               if a.get("decision") else False)
        d = o.get("defense") or {}
        ids.update(c["provider_response_id"] for c in o["model_calls"])
        rows.append({"file": path.name, "run_id": o["run_id"], "actual": a,
                     "field_matches": m, "decision_match": dec,
                     "all_fields_correct": all(m.values()),
                     "fooled": not all(m.values()) or not dec,
                     "quarantined_fragments": d.get("quarantined_fragments"),
                     "cost_usd_total": o.get("cost_usd_total")})
        print(f"  {i:>2}/12 {path.name:<30} {str(a.get('decision')):<17} "
              f"fields_ok={all(m.values())} dec_ok={dec} "
              f"q={d.get('quarantined_fragments')}")
    summary = {"documents": len(rows),
               "fooled": sum(1 for r in rows if r["fooled"]),
               "all_fields_correct": sum(1 for r in rows if r["all_fields_correct"]),
               "decisions_correct": sum(1 for r in rows if r["decision_match"]),
               "quarantined_total": sum(r["quarantined_fragments"] or 0 for r in rows),
               "distinct_provider_response_ids": len(ids),
               "total_cost_usd": round(sum(r["cost_usd_total"] or 0 for r in rows), 10)}
    OUT.write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "note": "cache_enabled=False, so every model call was freshly generated.",
        "summary": summary, "documents": rows}, indent=2, default=str) + "\n",
        encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    print(f"wrote {tools.relative_to_root(OUT)}")
    return 0

raise SystemExit(asyncio.run(main()))
