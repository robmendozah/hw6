# Handbook Token and Cost Estimate

## Token count

- **Handbook token count: 10,058 tokens** (`data/shop_handbook.md`, 28,903 characters as read in UTF-8)
- **Method used:** `tiktoken` v0.14.0 in `hw6/.venv`, via `hw6/scripts/estimate_handbook.py`. The script first calls `tiktoken.encoding_for_model("gpt-6-luna")`; that raises `KeyError` because no encoding is registered for this model name, so it falls back to the **`o200k_base`** encoding and counts `len(enc.encode(handbook))`. The handbook was opened read-only and not modified.
- **Limitation / assumption:** This count is **NOT exact for GPT-6-Luna.** No public GPT-6-Luna tokenizer is available, so `o200k_base` — the encoding used by the current OpenAI model families — is used as the closest proxy. If GPT-6-Luna ships a different vocabulary, the true count will differ, most likely by a few percent. The figure also counts the handbook text alone: no chat-message framing, role tokens, or per-message overhead is included, as instructed.

## GPT-6-Luna pricing

| Item | Value |
| --- | --- |
| Uncached input price | $0.10 per 1,000,000 input tokens |
| Cached input price | $0.01 per 1,000,000 input tokens |
| Pricing unit | USD per 1,000,000 tokens (`input_per_1m`, `cached_input_per_1m`) |
| Source | `data/prices.json` (`"OpenAI Standard pricing, per 1M tokens (MGT 409 Lecture 11)"`) |

`prices.json` also lists `cache_write_per_1m` ($0.125) and `output_per_1m` ($0.50). Neither is used here: this problem covers input cost only, and the four requested scenarios do not include the one-time cache-write charge.

## Cost of the handbook alone

Prices are quoted per 1,000,000 tokens, so:

```
cost per call = (handbook tokens / 1,000,000) × price per 1M tokens
handbook tokens / 1,000,000 = 10,058 / 1,000,000 = 0.010058
```

**1 call — uncached**

```
0.010058 × $0.10 = $0.0010058
≈ $0.00101 (about one tenth of a cent)
```

**1 call — cached**

```
0.010058 × $0.01 = $0.00010058
≈ $0.000101 (about one hundredth of a cent)
```

**1,000 calls — uncached**

```
$0.0010058 × 1,000 = $1.0058
≈ $1.01
```

**1,000 calls — cached**

```
$0.00010058 × 1,000 = $0.10058
≈ $0.10
```

### Comparison

| Scenario | Input tokens billed | Cost |
| --- | ---: | ---: |
| 1 call — uncached | 10,058 | $0.0010058 |
| 1 call — cached | 10,058 | $0.0001006 |
| 1,000 calls — uncached | 10,058,000 | $1.0058 |
| 1,000 calls — cached | 10,058,000 | $0.1006 |

Caching the handbook cuts its input cost by a factor of 10 — a saving of about **$0.91 per 1,000 calls** — because the cached rate is one tenth of the standard rate. At scale this is the whole argument for keeping a large, unchanging system document in a prompt cache rather than re-sending it cold on every call.

## Note for Problem 4

These are **pre-run estimates**, computed before any agent call was made. They rest on a proxy tokenizer (`o200k_base`) and on the handbook text in isolation. In **Problem 4** they will be compared against the **actual usage and cost data** reported by the API for real runs, which will also include the rest of the system prompt, user messages, tool schemas, and output tokens.
