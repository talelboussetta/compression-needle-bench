"""Compress every task's tool output with each method and check, without any model,
whether the needed fact survived.

  python -m needle.compress --methods raw,caveman,headroom

Writes work/compressed-<method>.jsonl. Token counts use one tokenizer for every method
(tiktoken o200k_base), so the numbers compare like with like; they are not any vendor's
billing count.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
ENC = tiktoken.get_encoding("o200k_base")


def ntok(s: str) -> int:
    return len(ENC.encode(s, disallowed_special=()))


def kept(text: str, gold: str, key: str, window: int = 300) -> bool:
    """The fact is kept if gold and its key still sit close together."""
    golds = [m.start() for m in re.finditer(re.escape(gold), text)]
    keys = [m.start() for m in re.finditer(re.escape(key), text)]
    return any(abs(g - k) < window for g in golds for k in keys)


# --- methods -------------------------------------------------------------------------------


def m_raw(task):
    return task["tool_output"], {}


CAVEMAN = str(ROOT / "tools" / "node_modules" / ".bin" / ("caveman.cmd" if os.name == "nt" else "caveman"))


def m_caveman(task):
    p = subprocess.run([CAVEMAN, "compress"], input=task["tool_output"].encode(), capture_output=True, timeout=180)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="replace")[-300:])
    meta = {}
    for line in p.stderr.decode(errors="replace").splitlines():
        if line.startswith("{"):
            try:
                meta = json.loads(line)
            except json.JSONDecodeError:
                pass
    return p.stdout.decode(errors="replace"), {k: meta.get(k) for k in ("method", "content_type", "lossless_to_model")}


_headroom = None


def m_headroom(task):
    """Headroom compresses tool results inside a chat transcript, so give it one."""
    global _headroom
    if _headroom is None:
        from headroom import compress

        _headroom = compress
    messages = [
        {"role": "user", "content": task["question"]},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "run_tool", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": task["tool_output"]},
    ]
    r = _headroom(messages, model="gpt-4o")
    out = r.messages[-1]["content"]
    if isinstance(out, list):  # content blocks
        out = "".join(b.get("text", "") for b in out if isinstance(b, dict))
    return out, {"ratio": getattr(r, "compression_ratio", None)}


METHODS = {"raw": m_raw, "caveman": m_caveman, "headroom": m_headroom}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="raw,caveman,headroom")
    ap.add_argument("--tasks", default=str(ROOT / "tasks.jsonl"))
    a = ap.parse_args()
    tasks = [json.loads(l) for l in open(a.tasks, encoding="utf-8")]
    WORK.mkdir(exist_ok=True)
    for name in a.methods.split(","):
        fn = METHODS[name]
        path = WORK / f"compressed-{name}.jsonl"
        n_kept = 0
        with path.open("w", encoding="utf-8") as f:
            for t in tasks:
                t0 = time.perf_counter()
                err = None
                try:
                    text, meta = fn(t)
                except Exception as e:
                    text, meta, err = "", {}, f"{type(e).__name__}: {str(e)[:200]}"
                row = {
                    "id": t["id"], "kind": t["kind"], "method": name,
                    "tokens_before": ntok(t["tool_output"]), "tokens_after": ntok(text),
                    "kept": kept(text, t["gold"], t["key"]) if text else False,
                    "ms": round((time.perf_counter() - t0) * 1000), "err": err, "meta": meta,
                    "text": text,
                }
                n_kept += row["kept"]
                f.write(json.dumps(row) + "\n")
        print(f"{name}: kept {n_kept}/{len(tasks)}")


if __name__ == "__main__":
    main()
