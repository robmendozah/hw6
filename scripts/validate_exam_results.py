"""Mechanically validate output/exam_results.json against the required schema."""
import json, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
import tools

REQUIRED = ["file","vendor","sku","unit_price","lead_time_days","min_order",
            "decision","reason","trap_tool_called","input_tokens",
            "cached_tokens","output_tokens","cost_usd"]
NUMERIC_OPT = ["unit_price","lead_time_days","min_order"]
NUMERIC_REQ = ["input_tokens","cached_tokens","output_tokens","cost_usd"]

path = tools.OUTPUT_DIR / "exam_results.json"
checks, ok = [], True

def check(label, passed, detail=""):
    global ok
    ok = ok and passed
    checks.append((label, passed, detail))

try:
    rows = json.loads(path.read_text(encoding="utf-8"))
    check("1. valid JSON", True)
except Exception as e:
    check("1. valid JSON", False, str(e)); rows = []

check("2. exactly 10 entries", len(rows) == 10, f"{len(rows)} found")

exam = sorted(p.name for p in (tools.DATA_DIR/"exam_docs").iterdir()
              if p.suffix.lower() in tools.SUPPORTED_SUFFIXES)
files = [r.get("file") for r in rows]
check("3. every exam filename exactly once", sorted(files) == exam,
      f"missing/extra: {set(exam) ^ set(files) or 'none'}")

practice = {p.name for p in (tools.DATA_DIR/"practice_docs").iterdir()}
attacks = {p.name for p in (tools.DATA_DIR/"my_attacks").iterdir()}
check("4. no practice or attack document present",
      not (set(files) & (practice | attacks)))

missing = {r.get("file"): [k for k in REQUIRED if k not in r] for r in rows}
missing = {f: m for f, m in missing.items() if m}
check("5. all required fields present", not missing, str(missing))

bad_dec = [r["file"] for r in rows
           if r.get("decision") not in ("recommend","do_not_recommend")]
check("6. decision in the two allowed values", not bad_dec, str(bad_dec))

bad_num = []
for r in rows:
    for k in NUMERIC_OPT:
        if r.get(k) is not None and not isinstance(r[k], (int, float)):
            bad_num.append(f"{r['file']}.{k}={r[k]!r}")
    for k in NUMERIC_REQ:
        if not isinstance(r.get(k), (int, float)) or isinstance(r.get(k), bool):
            bad_num.append(f"{r['file']}.{k}={r.get(k)!r}")
check("7. numeric fields are numbers, not strings", not bad_num, str(bad_num))

bad_bool = [r["file"] for r in rows if not isinstance(r.get("trap_tool_called"), bool)]
check("8. trap_tool_called is a JSON boolean", not bad_bool, str(bad_bool))

# 9: token counts must equal the API-reported usage in exam_runs.json
detail = json.loads((tools.OUTPUT_DIR/"exam_runs.json").read_text(encoding="utf-8"))
by_file = {d["file"]: d for d in detail["documents"]}
mismatch = []
for r in rows:
    stages = by_file[r["file"]]["usage_by_stage"]
    if (sum(s["input_tokens"] for s in stages) != r["input_tokens"]
        or sum(s["cache_read_tokens"] for s in stages) != r["cached_tokens"]
        or sum(s["output_tokens"] for s in stages) != r["output_tokens"]):
        mismatch.append(r["file"])
check("9. token counts match API-reported usage", not mismatch, str(mismatch))

# 10: recompute cost independently from prices.json
prices = tools.load_prices("gpt-6-luna")
bad_cost = []
for r in rows:
    stages = by_file[r["file"]]["usage_by_stage"]
    total = 0.0
    for s in stages:
        cached = s["cache_read_tokens"]
        total += max(s["input_tokens"] - cached, 0)/1e6 * prices["input_per_1m"]
        total += cached/1e6 * prices["cached_input_per_1m"]
        total += s["cache_write_tokens"]/1e6 * prices["cache_write_per_1m"]
        total += s["output_tokens"]/1e6 * prices["output_per_1m"]
    if abs(round(total, 10) - r["cost_usd"]) > 1e-9:
        bad_cost.append(f"{r['file']}: {r['cost_usd']} vs {round(total,10)}")
check("10. cost_usd recomputes from data/prices.json", not bad_cost, str(bad_cost))

load_dotenv(tools.HW6_ROOT/".env")
key = os.environ.get("PORTKEY_API_KEY", "\0no-key\0")
text = path.read_text(encoding="utf-8")
leaked = key in text or "PORTKEY" in text or "sk-" in text
check("11. no secrets, keys or prompts in the file", not leaked)

check("12. decisions came from the agent, not edited",
      all(r["decision"] == by_file[r["file"]]["evaluation"].get("decision")
          and r["reason"] == by_file[r["file"]]["evaluation"].get("reason")
          and r["unit_price"] == by_file[r["file"]]["evaluation"].get("unit_price_usd")
          for r in rows))

for label, passed, detail_text in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}"
          + (f"  -> {detail_text}" if not passed and detail_text else ""))
print("\nSCHEMA VALIDATION:", "PASSED" if ok else "FAILED")
raise SystemExit(0 if ok else 1)
