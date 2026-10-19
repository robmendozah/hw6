"""Prove the trap tools have no external side effect.

TRAP_CALLS_PATH is redirected to a scratch file so this check does not write
evidence into output/trap_calls.json, which must only ever contain real
model-induced calls.
"""
import ast
import asyncio
import json
import pathlib
import sys
import tempfile
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import tools

# 1. static check: no network / mail / payment library is imported at all.
src = ast.parse((tools.HW6_ROOT / "tools.py").read_text(encoding="utf-8"))
imported = set()
for node in ast.walk(src):
    if isinstance(node, ast.Import):
        imported.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imported.add(node.module.split(".")[0])
forbidden = {"smtplib", "requests", "httpx", "urllib", "socket", "ftplib", "stripe", "boto3"}
print("tools.py imports      :", sorted(imported))
print("forbidden imports     :", sorted(imported & forbidden) or "none")

# 2. behavioural check: calling both traps writes a record and nothing else.
@dataclass
class Ctx:
    deps: tools.RunDeps

scratch = pathlib.Path(tempfile.mkdtemp()) / "trap_calls.json"
tools.TRAP_CALLS_PATH = scratch
deps = tools.RunDeps(run_id="selftest", document="n/a")
ctx = Ctx(deps=deps)

print("send_email returned   :", asyncio.run(
    tools.send_email(ctx, to="x@example.com", subject="s", body="b"))[:60])
print("approve_payment ret.  :", asyncio.run(
    tools.approve_payment(ctx, vendor="V", amount_usd=1.0, reference="r"))[:60])
print("scratch records       :", len(json.loads(scratch.read_text())))
print("real trap_calls.json  :", (tools.OUTPUT_DIR / "trap_calls.json").read_text().strip())
