"""Count tokens in the Campus Customs shop handbook and price them for gpt-6-luna.

Reads data/shop_handbook.md and data/prices.json; writes nothing (prints a JSON blob).
The handbook is opened read-only and never modified.
"""
import json
import pathlib

import tiktoken

HERE = pathlib.Path(__file__).resolve().parent.parent
MODEL = "gpt-6-luna"

handbook = (HERE / "data" / "shop_handbook.md").read_text(encoding="utf-8")
prices = json.loads((HERE / "data" / "prices.json").read_text(encoding="utf-8"))[MODEL]

# Prefer an exact tokenizer registered for the model; fall back to the newest
# OpenAI encoding if tiktoken does not know this model name.
try:
    enc = tiktoken.encoding_for_model(MODEL)
    exact = True
except KeyError:
    enc = tiktoken.get_encoding("o200k_base")
    exact = False

tokens = len(enc.encode(handbook))
per_1m = tokens / 1_000_000

print(json.dumps({
    "tokenizer": enc.name,
    "exact_for_model": exact,
    "tiktoken_version": tiktoken.__version__,
    "chars": len(handbook),
    "tokens": tokens,
    "input_per_1m": prices["input_per_1m"],
    "cached_input_per_1m": prices["cached_input_per_1m"],
    "uncached_1_call": per_1m * prices["input_per_1m"],
    "cached_1_call": per_1m * prices["cached_input_per_1m"],
    "uncached_1000_calls": per_1m * prices["input_per_1m"] * 1000,
    "cached_1000_calls": per_1m * prices["cached_input_per_1m"] * 1000,
}, indent=2))
