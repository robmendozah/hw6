# Cache Test — With and Without Cached Tokens

Experiment id: **`p4-cache-20261018T194921Z`**
Raw per-model-call data: `output/cache_test.json`
Model: `gpt-6-luna` via the Portkey OpenAI-compatible gateway
Prices: `data/prices.json`

---

# 1. Experimental setup

All **12** documents in `data/practice_docs/` were run through the **same** vendor desk agent built in
Problem 3, twice: once with prompt caching enabled and once with it disabled. That is 24 document runs.
Each document run needed **2 model calls** (one to decide to read the document, one to answer after the
tool result), so the experiment records **48 model calls** — 24 per condition.

Held constant across both conditions: the model `gpt-6-luna`, `prompts/prompt.md`, the handbook text, the
`VendorEvaluation` output type, all three tools, the document parsers, and the decision rules. There is
one agent class and one code path; `build_agent(cache_enabled)` flips a single flag.

### How the cache-enabled setup was configured

Static instructions. `build_instructions(cache_enabled=True)` returns a constant string — `prompt.md`
followed by the full handbook — so every model call of every run starts with a byte-identical prefix. A
stable `prompt_cache_key` (`campus-customs-vendor-desk-v1`) is passed through
`OpenAIChatModelSettings.openai_prompt_cache_key`, routing that prefix to the same cache.

### How the no-cache setup was configured

The provider offers no "caching off" switch, so the cache had to be defeated by the only mechanism that
actually works: making the prefix unmatchable. `build_instructions(cache_enabled=False)` returns a
*function* rather than a string. pydantic-ai re-evaluates instruction functions on every model request,
so each call gets a fresh one-line nonce (`<!-- cache-bust <uuid> -->`) at the very front of the prefix.
A different first token means no cached prefix can match. A unique `prompt_cache_key` per run is set as
well.

**A mechanism that was tested and rejected.** The obvious approach — a unique `prompt_cache_key` and
nothing else — was probed first (`scripts/_probe_cache.py`) and **failed validation**. With a unique key
but an unchanged prefix, call 1 reported 0 cached tokens but call 2 of the same run still reported
**11,631 cached tokens**. The key alone does not prevent reuse within a run. Only the per-call nonce
produced zero cached tokens on every call, so that is the mechanism used.

The handbook itself was never modified or rewritten. The nonce is a single comment line in front of the
prompt; it costs roughly 26 extra input tokens per call, which is why the without-cache input totals are
about 576 tokens higher across 24 calls.

### How the conditions were verified

Nothing is taken on trust from the configuration. `scripts/run_cache_experiment.py` reads the token
counts the API returned for each individual model call and refuses to mark the batch valid unless:

- **every** `without_cache` model call reports `cache_read_tokens == 0`, and
- the `with_cache` batch reports cached tokens at all,
- and all 12 documents ran successfully in both conditions.

**The without-cache runs were accepted only because the API reported zero cached tokens on all 24 of
their model calls.** Validation passed on the batch reported here.

---

# 2. With-cache results

| Metric | Value |
| --- | ---: |
| Documents | 12 |
| Model calls | 24 |
| Input tokens (total, cached included) | 285,418 |
| Cached input tokens | 267,445 |
| Uncached input tokens | 17,973 |
| Cache-write tokens | 14,949 |
| Output tokens | 1,410 |
| Total tokens | 286,828 |
| Reasoning tokens | 0 |
| **Total cost** | **$0.007045375** |
| **Average cost per document** | **$0.0005871146** |

Cost by category: uncached input $0.0017973 + cached input $0.00267445 + cache write $0.001868625 +
output $0.000705.

**93.7 %** of all input tokens were served from cache (267,445 / 285,418). The pattern is consistent: the
first model call of every document hit **11,604** cached tokens — the shared instruction prefix — and the
second call hit roughly **11,654**. One exception: the second call of `p03_ivyprint_catalog.html` reported
0 cached tokens, a single cache miss out of 24 calls.

---

# 3. Without-cache results

| Metric | Value |
| --- | ---: |
| Documents | 12 |
| Model calls | 24 |
| Input tokens (total) | 285,994 |
| **Cached input tokens** | **0** |
| Uncached input tokens | 285,994 |
| Cache-write tokens | 282,970 |
| Output tokens | 1,374 |
| Total tokens | 287,368 |
| Reasoning tokens | 0 |
| **Total cost** | **$0.06465765** |
| **Average cost per document** | **$0.0053881375** |

Cost by category: uncached input $0.0285994 + cached input $0.00 + cache write $0.03537125 +
output $0.000687.

**Cached tokens are zero for this validated setup** — all 24 model calls, confirmed from the
API-reported counts, not from the configuration.

Note the cache-write line. Because every call presents a prefix the provider has never seen, every call
*writes* a new cache entry (282,970 tokens at $0.125/1M = $0.0354) that nothing ever reads. That write
charge is more than half the no-cache bill. It is reported here because it is what the API returned and
`prices.json` defines the category; section 4 also shows the comparison without it.

---

# 4. Direct comparison

| Metric | With cache | Without cache |
| --- | ---: | ---: |
| Documents | 12 | 12 |
| Model calls | 24 | 24 |
| Input tokens | 285,418 | 285,994 |
| Cached tokens | 267,445 | 0 |
| Output tokens | 1,410 | 1,374 |
| Total cost | $0.007045375 | $0.06465765 |
| Cost per document | $0.0005871146 | $0.0053881375 |

### Savings arithmetic

```
Savings $ = $0.06465765 − $0.007045375
          = $0.057612275

Savings % = ($0.06465765 − $0.007045375) / $0.06465765 × 100
          = $0.057612275 / $0.06465765 × 100
          = 0.89103571 × 100
          = 89.10 %
```

Caching the handbook cut the bill for the same 12 documents by **89.10 %**.

### The same comparison without the cache-write charge

The no-cache condition pays a large write charge for entries it can never reuse, which arguably flatters
the saving. Counting only input and output tokens:

```
With cache    : $0.0017973 + $0.00267445 + $0.000705 = $0.00517675   ($0.00043140 / document)
Without cache : $0.0285994 + $0.00       + $0.000687 = $0.02928640   ($0.00244053 / document)

Savings % = ($0.02928640 − $0.00517675) / $0.02928640 × 100 = 82.32 %
```

So the saving is **82 % at minimum and 89 % as actually billed**. Either way the conclusion is the same:
the repeated handbook dominates this workload's cost, and caching it removes most of that cost.

---

# 5. Comparison with Problem 2

Problem 2 priced the **handbook alone**: 10,058 tokens, $0.0010058 per uncached call, $0.0001006 per
cached call. Problem 4 measures **complete agent calls**, which also carry `prompts/prompt.md`, the
pydantic-ai system framing, the tool schemas for three tools, the task message, the document text
returned by the tool, and the output tokens — and each document needs two model calls, not one. The two
numbers are not meant to match.

**Was the handbook token estimate close to the observed cache behaviour?** Yes, strikingly so. The
cached prefix measured **11,604 tokens**. The Problem 2 estimate for the handbook was **10,058** tokens
and `prompt.md` adds **1,148** by the same tokenizer, giving **11,206** — within **398 tokens (3.4 %)** of
what the provider actually cached. The remainder is the tool schemas and system framing, which sit inside
the cached prefix but were deliberately excluded from the Problem 2 estimate. For a count produced with a
proxy tokenizer (`o200k_base`, since no exact GPT-6-Luna tokenizer exists), that is a good result and
suggests the proxy is close to the real vocabulary.

**Are the predicted savings visible?** Yes. Problem 2 predicted a 10× reduction on handbook input tokens,
from $0.10 to $0.01 per 1M. That ratio shows up directly: 267,445 tokens that would have cost $0.0267 at
the standard rate cost $0.0027 instead. The end-to-end saving lands at 82–89 % rather than the full 90 %
precisely because of the tokens Problem 2 excluded.

**What explains the gap between the handbook-only estimate and the real cost?** Per document:

| Component | Tokens per document (with cache) | Notes |
| --- | ---: | --- |
| Problem 2 handbook estimate, 1 call | 10,058 | What Problem 2 priced. |
| Cached prefix actually sent, per call | ~11,604 | Handbook + prompt.md + tool schemas + framing. |
| Total input, both calls | ~23,785 | The prefix is re-sent on the second model call. |
| Uncached input, both calls | ~1,498 | Document text, task message, tool result, nonce. |
| Output | ~118 | The structured answer. |

The single largest multiplier is simply that **the prefix is paid for twice** — the read-then-answer loop
means two model calls per document, so roughly 23,800 input tokens rather than 10,058. Caching is what
makes the second pass nearly free.

---

# 6. Projection: 1,000 documents/day for 30 days

30,000 documents, using the observed average cost per document from each validated setup.

```
With cache    : $0.0005871146 × 30,000 = $17.61
Without cache : $0.0053881375 × 30,000 = $161.64

Projected savings $ = $161.64 − $17.61 = $144.03
Projected savings % = $144.03 / $161.64 × 100 = 89.10 %
```

Excluding the unreusable cache-write charge, the same projection gives **$12.94 with cache** against
**$73.22 without**, a saving of **$60.27 (82.32 %)**.

This projection assumes future calls behave like the 12-document test: the same two model calls per
document, documents of similar length, an unchanged handbook, and a cache that stays warm under
continuous traffic. At 1,000 documents a day the cache would in practice be warmer than in this short
batch, so the with-cache figure is more likely to improve than to worsen.

---

# 7. What surprised me?

### The numbers, for reference

- Cost per document: **$0.000587** cached vs **$0.005388** uncached — a **9.2×** difference.
- Savings: **89.10 %** as billed, **82.32 %** counting input and output only.
- **93.7 %** of all input tokens came from cache in the cached condition.
- The cached prefix was **11,604 tokens**; the Problem 2 handbook estimate was **10,058**, and
  `prompt.md` accounts for **1,148** more — the estimate was within **3.4 %** of the real cached prefix.
- Non-cacheable tokens were small: about **1,498 uncached input tokens** and **118 output tokens** per
  document, against roughly **23,785** total input tokens.
- Every document took exactly **2 model calls**; token totals per document varied by under 0.5 %
  (23,757–23,861), so no document was meaningfully more expensive than another.
- One cache miss in 24 cached calls (`p03_ivyprint_catalog.html`, second call).
- A unique `prompt_cache_key` alone did **not** disable caching; the per-call nonce was required.
- **Two documents got different decisions in the two conditions** (see the note below).

### My reflection

*(To be written by Roberto.)*

- Was the savings percentage larger or smaller than I expected?

  &nbsp;

- Did cached tokens correspond closely to the handbook token estimate?

  &nbsp;

- Were there meaningful non-handbook tokens that could not be cached?

  &nbsp;

- Did some documents require more model calls or tokens than others?

  &nbsp;

---

## An honest note on two inconsistent decisions

This does not affect the token or cost analysis, but it should not be buried. Two documents came out
differently in the two conditions, and in each case the *without-cache* run was wrong:

| Document | With cache | Without cache |
| --- | --- | --- |
| `p02_elmcity_quote.html` | `do_not_recommend` — "$9.83 exceeds the catalogue maximum of $8.51" | `recommend` — "the quoted $9.83 price is within the $8.51 catalogue max" |
| `p08_chapelst_email.eml` | `recommend` — "$4.27 is within the $5.34 catalogue maximum" | `do_not_recommend` — "$4.27 exceeds the catalogue maximum of $5.34?" |

Both no-cache reasons contradict their own arithmetic. This is model non-determinism in the comparison
step, not a caching effect — caching changes what is billed, not what the model is asked. It is recorded
here rather than re-rolled, because rerunning until the two conditions agree would be exactly the kind of
result-shaping the assignment warns against. It is worth knowing that at `reasoning_effort: none` this
agent gets a straightforward numeric comparison wrong roughly 2 times in 24.

Separately, `p02` contains a line claiming a "revised price" that supersedes the quoted table — the
with-cache run correctly declined to treat it as the quoted price.
