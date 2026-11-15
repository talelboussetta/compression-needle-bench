"""Ask a model each question from the compressed tool output, and score the answer.

  python -m needle.answer --methods raw,caveman,headroom --model haiku

Uses the Claude Code CLI in print mode (`claude -p`), with tools disabled and a fixed
system prompt, so it runs on whatever Claude plan or key the CLI is signed in with.
The model sees only the compressed view: no retrieval tool is offered, which is the
"answer from this view" case both compressors are designed for.

Writes work/answers-<method>-<model>.jsonl. Resumable: finished ids are skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
CWD = WORK / "claude-cwd"  # an empty folder, so no project instructions are picked up
SYSTEM = "You answer a question about a tool output. Reply with the answer only: no explanation, no quotes."


def norm(s: str) -> str:
    return re.sub(r"[\s`'\"*.]+$", "", re.sub(r"^[\s`'\"*]+", "", s.strip())).lower()


def correct(answer: str, gold: str) -> bool:
    a, g = norm(answer), gold.lower()
    if a == g:
        return True
    try:  # numbers: 158 == 158.0 == 158.00
        return abs(float(a) - float(g)) < 1e-9
    except ValueError:
        pass
    return g in a and len(a) <= len(g) + 40  # short answer that contains the gold


def ask(prompt: str, model: str) -> tuple[str, dict]:
    p = subprocess.run(
        ["claude", "-p", "--model", model, "--tools", "", "--system-prompt", SYSTEM, "--output-format", "json"],
        input=prompt.encode(), capture_output=True, cwd=CWD, timeout=300,
    )
    out = p.stdout.decode(errors="replace").strip().splitlines()
    d = json.loads(out[0]) if out else {}
    if d.get("is_error") or d.get("terminal_reason") == "api_error":
        raise RuntimeError(str(d.get("result") or d.get("terminal_reason"))[:200])
    u = d.get("usage", {})
    return d.get("result", ""), {
        "input_tokens": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
        + (u.get("cache_creation_input_tokens") or 0),
        "output_tokens": u.get("output_tokens"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="raw,caveman,headroom")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--tasks", default=str(ROOT / "tasks.jsonl"))
    a = ap.parse_args()
    CWD.mkdir(parents=True, exist_ok=True)
    tasks = {t["id"]: t for t in map(json.loads, open(a.tasks, encoding="utf-8"))}
    for m in a.methods.split(","):
        comp = [json.loads(l) for l in open(WORK / f"compressed-{m}.jsonl", encoding="utf-8")]
        out = WORK / f"answers-{m}-{a.model}.jsonl"
        done = {json.loads(l)["id"] for l in open(out, encoding="utf-8")} if out.exists() else set()
        n_ok = n = 0
        with out.open("a", encoding="utf-8") as f:
            for c in comp:
                if c["id"] in done:
                    continue
                t = tasks[c["id"]]
                prompt = f"Tool output:\n<tool_output>\n{c['text']}\n</tool_output>\n\nQuestion: {t['question']}"
                try:
                    ans, usage = ask(prompt, a.model)
                    err = None
                except Exception as e:
                    ans, usage, err = "", {}, f"{type(e).__name__}: {str(e)[:200]}"
                    if "authenticate" in str(e) or "OAuth" in str(e):
                        raise SystemExit(f"CLI not signed in: {e}")
                row = {"id": c["id"], "kind": c["kind"], "method": m, "model": a.model, "answer": ans,
                       "gold": t["gold"], "correct": correct(ans, t["gold"]) if not err else False,
                       "err": err, **usage}
                f.write(json.dumps(row) + "\n")
                f.flush()
                n += 1
                n_ok += row["correct"]
        print(f"{m}: {n_ok}/{n} correct this pass")


if __name__ == "__main__":
    main()
