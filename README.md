# compression-needle-bench

**Does compressing an agent's tool output keep the one fact the agent needs?**

Tool-output compressors (headroom, caveman and others) cut tokens by shrinking what tools
return before the model reads it: JSON arrays, logs, test runs, CSV. Their published evals
mostly measure question-answering benchmarks (GSM8K, TruthfulQA, SQuAD) or whole agent
sessions. This repo measures something narrower and harder for a lossy compressor: a
**needle** that a real agent would need, buried in a repetitive tool output.

| task kind | haystack | the needle |
|---|---|---|
| `json_unique_status` | 300 order records | the id of the only `refunded` order |
| `json_lookup` | 300 order records | the amount of one named order |
| `json_near_duplicate` | 250 identical config objects | the one object with a different `timeout_ms` |
| `log_error` | 2,000 INFO/DEBUG lines | the code on the single ERROR line |
| `test_run` | 300 PASSED lines | the name of the failing test |
| `csv_lookup` | 500 product rows | the price of one SKU |

20 tasks per kind, 120 in all, generated from a fixed seed (`needle/gen.py`).

## Results (2026-11-15)

### 1. Model-free: is the fact still in the compressed text?

A fact counts as kept only if the answer and its key (the order id, `ERROR`, `FAILED`, ...)
still appear within 300 characters of each other. Tokens are counted with one tokenizer
(tiktoken `o200k_base`) for every method, so they compare like with like.

Cell = facts kept / tasks · tokens saved.

| kind | caveman 4.1.0 | headroom 0.44.0 |
|---|---|---|
| json_unique_status | 20/20 · 41% | 20/20 · 62% |
| json_lookup | 20/20 · 0% | 20/20 · 58% |
| json_near_duplicate | 20/20 · 97% | 20/20 · 66% |
| log_error | 20/20 · 100% | 20/20 · 100% |
| test_run | 20/20 · 0% | 20/20 · 0% |
| csv_lookup | 20/20 · 0% | 20/20 · 0% |
| **all** | **120/120 · 70%** | **120/120 · 75%** |

What this shows:

- **Neither tool lost a single needle.** On this set, both compressors are safe: they cut
  where the content is repetitive and leave it alone where it is not.
- **They save in different places.** headroom rewrites JSON arrays into a compact table
  (one header row, then one comma-separated row per record), which is lossless and saves
  ~60% even when every record is unique. caveman leaves unique records alone and elides
  repetition, which wins on near-duplicates (97%) and logs.
- **The "all" figure is mostly the logs.** A 2,000-line log is ~60,000 tokens and both tools
  cut it to a few hundred while keeping the ERROR line. Don't read 70–75% as typical.
- **Plain test output and CSV were not compressed by either.** For caveman this depends on the
  entry point: the same real `pytest -v` run is cut 95% by `caveman shrink -- pytest -v` but
  passed through at 0% by `caveman compress` on stdin, where it is classified as `text`
  (reported upstream: [JuliusBrussee/caveman#1536](https://github.com/JuliusBrussee/caveman/issues/1536)).

### 2. With a model: does it still answer correctly?

Pending. `needle/answer.py` asks Claude each question from the compressed text only, with no
retrieval tool, and scores the answer exactly. A fact that is present can still be harder to
read in a new format, so this is the step that tests headroom's table format and caveman's
elision markers.

## Run it

```bash
python -m venv .venv && .venv/Scripts/pip install "headroom-ai==0.44.0" tiktoken   # (bin/ on Linux/macOS)
npm i --prefix tools @caveman-ai/cli@4.1.0
# caveman's compressor needs its engine: download caveman-engine_<os>_<arch> from the
# bin-v4.1.0 release, check it against checksums.txt, and point CAVEMAN_ENGINE_BIN at it.

python -m needle.gen --per-kind 20 --out tasks.jsonl
python -m needle.compress --methods raw,caveman,headroom
python -m needle.answer --methods raw,caveman,headroom --model haiku   # needs the Claude Code CLI signed in
python -m needle.report
```

## Limits

- Synthetic haystacks. They are shaped like real tool output but are cleaner than most.
  Messy, nested, real-world JSON is the next thing to add.
- One needle per task, and the question is asked *after* compression. Neither tool sees the
  question, but headroom is given it in the transcript, as it would be in a real agent.
- caveman was run with its engine only (`caveman compress`), not as the proxy or Claude Code
  plugin. headroom was run as the Python library (`headroom.compress`), not as the proxy.
- Both tools offer a way to retrieve the original bytes. This benchmark tests the case they
  both aim for: answering from the compressed view alone.

## License

MIT
