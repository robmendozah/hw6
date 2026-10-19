"""Probe which cache-disabling mechanism the provider actually honours.

Three variants on the same document:
  A  stable prompt_cache_key, static instructions           (expect cached > 0)
  B  unique prompt_cache_key, static instructions           (does the key alone work?)
  C  unique prompt_cache_key + per-call nonce in the prefix (expect cached = 0)

Writes nothing to the Problem 4 logs; this is a development probe only.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import agent as agent_mod
import tools
from models import VendorEvaluation
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

DOC = "data/practice_docs/p01_bluehen_quote.html"


def make_agent(cache_key: str, nonce: bool) -> Agent:
    return Agent(
        agent_mod.build_model(cache_key),
        deps_type=tools.RunDeps,
        output_type=VendorEvaluation,
        instructions=agent_mod.build_instructions(cache_enabled=not nonce),
        tools=[tools.read_vendor_document, tools.send_email, tools.approve_payment],
        retries=2,
    )


async def probe(label: str, cache_key: str, nonce: bool) -> None:
    ag = make_agent(cache_key, nonce)
    deps = tools.RunDeps(run_id=f"probe-{label}", document=DOC)
    result = await ag.run(
        f"Evaluate the vendor document at `{DOC}`. Call read_vendor_document first.",
        deps=deps,
        usage_limits=UsageLimits(request_limit=agent_mod.MAX_MODEL_REQUESTS),
    )
    prices = tools.load_prices(agent_mod.MODEL_NAME)
    calls = agent_mod.per_call_usage(result.all_messages(), prices)
    for c in calls:
        u = c["usage"]
        print(
            f"  {label} call {c['call_number']}: "
            f"input={u['input_tokens']:>6} cached={u['cache_read_tokens']:>6} "
            f"write={u['cache_write_tokens']:>5} output={u['output_tokens']:>4}"
        )


async def main() -> None:
    print("A  stable key, static instructions (warm the cache, then measure):")
    await probe("A1", agent_mod.CACHE_KEY, nonce=False)
    await probe("A2", agent_mod.CACHE_KEY, nonce=False)

    print("B  unique key only, static instructions:")
    await probe("B1", f"probe-{uuid.uuid4().hex}", nonce=False)
    await probe("B2", f"probe-{uuid.uuid4().hex}", nonce=False)

    print("C  unique key + per-call nonce:")
    await probe("C1", f"probe-{uuid.uuid4().hex}", nonce=True)
    await probe("C2", f"probe-{uuid.uuid4().hex}", nonce=True)


if __name__ == "__main__":
    asyncio.run(main())
