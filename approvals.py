"""Design-level defense: the human-approval boundary for dangerous actions.

`send_email` and `approve_payment` still exist and are still no-side-effect
trap tools (see `tools.py`). What changes in defended mode is *who can reach
them*. They are no longer handed to any agent that touches untrusted vendor
content. Instead a consequential action can only be:

    1. REQUESTED - by an operator, recorded in output/pending_approvals.json
       with status "pending";
    2. APPROVED  - by a named human, out of band, via `approve_request`;
    3. EXECUTED  - only then, and only through `execute_approved_action`.

The gate is not a prompt rule the model could be argued out of; it is a
precondition in code. A vendor document has no path to step 2: approval
requires an approver name supplied by the caller at the console, never by
document text, never by a model. There is no function anywhere that lets
document content create an approved request.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import tools

PENDING_APPROVALS_PATH = tools.OUTPUT_DIR / "pending_approvals.json"

DANGEROUS_ACTIONS = ("send_email", "approve_payment")


class ApprovalError(RuntimeError):
    """Raised when a dangerous action is attempted without human approval."""


def _load() -> list[dict]:
    if not PENDING_APPROVALS_PATH.exists():
        return []
    raw = PENDING_APPROVALS_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else []


def _save(records: list[dict]) -> None:
    PENDING_APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_APPROVALS_PATH.write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )


def request_action(action: str, arguments: dict, requested_by: str, run_id: str) -> str:
    """Record a request for a dangerous action. Executes nothing.

    Returns the request id. The request starts, and stays, `pending` until a
    human approves it.
    """
    if action not in DANGEROUS_ACTIONS:
        raise ApprovalError(f"{action!r} is not a recognised dangerous action.")
    request_id = f"req-{uuid.uuid4().hex[:10]}"
    records = _load()
    records.append(
        {
            "request_id": request_id,
            "action": action,
            "arguments": arguments,
            "requested_by": requested_by,
            "run_id": run_id,
            "requested_utc": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "approved_by": None,
            "approved_utc": None,
            "executed_utc": None,
        }
    )
    _save(records)
    return request_id


def approve_request(request_id: str, approver: str) -> dict:
    """Approve a pending request. Callable only by a human operator.

    `approver` must be supplied by whoever runs this function - a person at a
    console. No agent is given this function as a tool, and no document text
    reaches it.
    """
    if not approver or not approver.strip():
        raise ApprovalError("an approver name is required; approval cannot be blank.")
    records = _load()
    for record in records:
        if record["request_id"] == request_id:
            if record["status"] != "pending":
                raise ApprovalError(
                    f"{request_id} is {record['status']}, not pending."
                )
            record["status"] = "approved"
            record["approved_by"] = approver.strip()
            record["approved_utc"] = datetime.now(timezone.utc).isoformat()
            _save(records)
            return record
    raise ApprovalError(f"no such request: {request_id}")


def execute_approved_action(request_id: str) -> str:
    """Run a dangerous action, but only after a human approved it.

    Even then the underlying tools are the same no-side-effect traps: this
    records the invocation in output/trap_calls.json and sends no mail and
    moves no money.
    """
    records = _load()
    for record in records:
        if record["request_id"] != request_id:
            continue
        if record["status"] != "approved":
            raise ApprovalError(
                f"{request_id} has status {record['status']!r}. A dangerous "
                "action requires explicit human approval before execution."
            )
        record["status"] = "executed"
        record["executed_utc"] = datetime.now(timezone.utc).isoformat()
        _save(records)
        # Routed through the same no-side-effect trap tool as before, so the
        # invocation is recorded in output/trap_calls.json and still sends no
        # mail and moves no money.
        deps = tools.RunDeps(run_id=record["run_id"], document=record["request_id"])
        tools._record_trap_call(deps, record["action"], record["arguments"])
        return (
            f"{record['action']} executed under approval by "
            f"{record['approved_by']} (no real side effect: this remains a "
            "no-side-effect trap tool)."
        )
    raise ApprovalError(f"no such request: {request_id}")


def pending_summary() -> dict:
    """Counts by status, for the audit trail."""
    records = _load()
    return {
        "total": len(records),
        "pending": sum(1 for r in records if r["status"] == "pending"),
        "approved": sum(1 for r in records if r["status"] == "approved"),
        "executed": sum(1 for r in records if r["status"] == "executed"),
    }
