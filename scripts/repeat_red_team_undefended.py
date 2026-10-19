"""Problem 7 - repeat the undefended runs, to separate a resilient agent from a lucky one.

The Problem 4 batch showed this agent varying between runs, so one clean
undefended result is not evidence that an attack fails. This repeats each
attack four more times against --defense none and records EVERY attempt,
successful or not, in output/red_team_repeats.json.
"""
import asyncio, json, pathlib, sys
from datetime import datetime, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import agent as agent_mod, tools
from run_red_team import ATTACKS, score
from run_attack_test import FIELD_MAP

OUT = tools.OUTPUT_DIR / "red_team_repeats.json"
REPEATS = 4

async def main():
    attempts = []
    for attack in ATTACKS:
        target = FIELD_MAP[attack["target_field"]]
        for i in range(1, REPEATS + 1):
            o = await agent_mod.evaluate_document(
                attack["document"], cache_enabled=True, quiet=True,
                run_label=f"p7-repeat{i}", defense="none")
            a = o["evaluation"] or {}
            s = score(attack["expected"], a)
            fooled = not all(s["field_matches"].values()) or not s["decision_match"]
            attempts.append({
                "attack": pathlib.Path(attack["document"]).name, "attempt": i,
                "defense_mode": "none", "run_id": o["run_id"],
                "target_field": attack["target_field"],
                "target_value_returned": a.get(target),
                "hidden_value": attack["hidden_value"],
                "hidden_value_accepted": str(a.get(target)) == str(attack["hidden_value"]),
                "decision": a.get("decision"), "all_fields_correct": all(s["field_matches"].values()),
                "decision_match": s["decision_match"], "attack_succeeded": fooled,
                "actual": a,
            })
            print(f"  {attempts[-1]['attack']:<28} attempt {i} "
                  f"{attack['target_field']}={a.get(target)} "
                  f"{a.get('decision')} succeeded={fooled}")
    OUT.write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Every attempt is recorded, including the ones that changed nothing.",
        "attempts": attempts}, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nwrote {tools.relative_to_root(OUT)}")
    return 0

raise SystemExit(asyncio.run(main()))
