# Homework 6 — Vendor Desk Agent

A PydanticAI agent for **Campus Customs**, an independent Yale merchandise shop. It reads one vendor
document at a time — HTML quote, PDF quote, or `.eml` email — extracts the commercial terms, and
drafts a buy / don't-buy recommendation against the Campus Customs Shop Handbook.

- **Model:** `gpt-6-luna`, reached through an OpenAI-compatible gateway (Portkey).
- **Decision authority:** `data/shop_handbook.md`, sent to the model on every call and never modified.
- **Documents:** HTML, PDF and `.eml`, read through an agent tool.
- **Security:** three layers of defense against hostile vendor documents — a visibility-aware reader,
  a two-stage trust boundary with a deterministic handbook guard, and explicit prompt trust rules.
  `send_email` and `approve_payment` exist as no-side-effect trap tools and are held by no agent;
  consequential actions require named human approval.
- **Logging:** every run appends real API usage and dollar cost (priced from `data/prices.json`) plus
  an audit trail of tool calls and final answers.

## Setup

```bash
git clone <this-repository-url>
cd hw6
python -m venv .venv
```

Activate it — `\.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on macOS/Linux — then:

```bash
pip install -r requirements.txt
```

Copy the environment template and add your own key:

```bash
cp .env.example .env
```

Then edit `.env` and set `PORTKEY_API_KEY` to your key. The real `.env` is gitignored and is not in
this repository. Nothing in the code hard-codes a key, and no key is written to any output file.

## Run the agent

From the repository root (`hw6/`):

```bash
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

That runs the **defended** pipeline — the final system. Paths are resolved relative to the project, so
the same command works on any machine.

### Modes

| Command | What it runs |
| --- | --- |
| `python agent.py --doc <path> --defense full` | The final three-layer defended agent (Problem 6 + post-Problem-7 hardening). |
| `python agent.py --doc <path>` | **Defaults to `--defense none`** — the original, deliberately undefended Problem 3 agent, preserved so the Problem 7 before/after comparison can be reproduced. |
| `python agent.py --doc <path> --no-cache` | Disables prompt caching (the Problem 4 control condition). |

To see the defenses do something, compare the two modes on a booby-trapped document:

```bash
python agent.py --doc data/practice_docs/p12_bluehen_quote.pdf --defense none
python agent.py --doc data/practice_docs/p12_bluehen_quote.pdf --defense full
```

The undefended run reads an off-page price of `$17.44` and recommends the quote; the defended run
quarantines that hidden line, reads the printed `$27.72`, and refuses it.

Any supported file works: `data/practice_docs/`, `data/exam_docs/`, or `data/my_attacks/`.

### Reproducing the experiments

The scripts in `scripts/` re-run each problem's batch; they append to the existing logs rather than
replacing them.

```bash
python scripts/estimate_handbook.py        # Problem 2 — handbook token + cost estimate
python scripts/run_cache_experiment.py     # Problem 4 — cached vs uncached, 12 docs x 2
python scripts/run_attack_test.py          # Problem 5 — undefended agent vs 12 practice docs
python scripts/run_defense_test.py         # Problem 6 — defended agent vs the same 12
python scripts/run_red_team.py             # Problem 7 — our own attack documents
python scripts/run_exam.py                 # Problem 8 — the 10 exam documents
python scripts/build_report.py             # Problem 9 — rebuilds output/hw6_report.html
```

## Important outputs

| File | What it holds |
| --- | --- |
| [`output/hw6_report.html`](output/hw6_report.html) | **The final results page (Problem 9).** A single self-contained HTML file — inline CSS and SVG, no external files or network access. Open it by double-clicking. |
| [`output/handbook_estimate.md`](output/handbook_estimate.md) | Problem 2 — handbook token count and projected cost. |
| [`output/cache_test.md`](output/cache_test.md) | Problem 4 — cached vs uncached economics, with the arithmetic. |
| [`output/attack_results.md`](output/attack_results.md) | Problem 5 — how the undefended agent was fooled, and by what. |
| [`output/defense_results.md`](output/defense_results.md) | Problem 6 — the three defense layers, before/after, and their measured cost. |
| [`output/red_team.md`](output/red_team.md) | Problem 7 — our own attacks, including the round that failed and the two that beat the defenses. |
| [`output/hardening_v2.md`](output/hardening_v2.md) | What was fixed after the red team, and what is still open. |
| [`output/exam_results.json`](output/exam_results.json) | Problem 8 — the 10 exam documents in the required submission schema. |
| [`output/harness.md`](output/harness.md) | Models, tools, and the Safety section describing each defense. |
| `output/usage_log.json`, `output/audit_trail.json`, `output/trap_calls.json` | Append-only logs across every run in the project. `trap_calls.json` is empty: no run ever triggered a forbidden tool. |

[`AI_prompts.md`](AI_prompts.md) is the running log of the prompts actually used to build this project.

## Layout

```
agent.py             CLI and orchestration; defended and undefended pipelines
tools.py             agent tools, path validation, append-only logging
safe_reader.py       the code-level defense: visibility-aware document reader
handbook_rules.py    the handbook's four purchasing checks, parsed and applied in code
approvals.py         the human-approval gate for consequential actions
models.py            Pydantic types for answers, facts, usage and audit records
prompts/             defended prompt, the two stage prompts, and the original Problem 3 prompt
data/                handbook, prices, practice / exam / red-team documents
output/              every result, log and report
scripts/             experiment runners and verification checks
```

`data/practice_key.json` is evaluation data only. It is used by the scoring scripts after a run and is
never shown to the agent.
