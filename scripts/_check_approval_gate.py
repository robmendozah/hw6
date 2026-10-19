"""Demonstrate the human-approval boundary end to end.

Both the pending-approvals file and the trap-call log are redirected to a
scratch directory, so this demonstration leaves no entries in the real
output/trap_calls.json, which must only ever record model-induced calls.
"""
import pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import approvals, tools

scratch = pathlib.Path(tempfile.mkdtemp())
approvals.PENDING_APPROVALS_PATH = scratch / "pending_approvals.json"
tools.TRAP_CALLS_PATH = scratch / "trap_calls.json"

rid = approvals.request_action(
    "approve_payment",
    {"vendor": "Blue Hen Apparel", "amount_usd": 1200.0, "reference": "BHA-26-1201"},
    requested_by="operator-console", run_id="gate-demo",
)
print("1. requested        ->", rid, approvals._load()[0]["status"])

try:
    approvals.execute_approved_action(rid)
    print("2. UNAPPROVED EXECUTE SUCCEEDED - gate is broken")
except approvals.ApprovalError as e:
    print("2. execute refused  ->", e)

try:
    approvals.approve_request(rid, approver="   ")
    print("3. BLANK APPROVAL ACCEPTED - gate is broken")
except approvals.ApprovalError as e:
    print("3. blank approval refused ->", e)

approvals.approve_request(rid, approver="Roberto (owner)")
print("4. approved by human->", approvals._load()[0]["approved_by"])
print("5. execute          ->", approvals.execute_approved_action(rid))
print("6. scratch trap log ->", tools.TRAP_CALLS_PATH.read_text()[:120].replace("\n", " "))
print("7. real trap_calls  ->", (tools.OUTPUT_DIR / "trap_calls.json").read_text().strip())
