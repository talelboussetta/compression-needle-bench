"""Summarise work/*.jsonl into RESULTS.md.

  python -m needle.report
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
KINDS = ["json_unique_status", "json_lookup", "json_near_duplicate", "log_error", "test_run", "csv_lookup"]


def rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def main():
    out = ["# Results\n"]
    comp = {p.stem.split("-", 1)[1]: rows(p) for p in sorted(WORK.glob("compressed-*.jsonl"))}
    order = [m for m in ("raw", "caveman", "headroom") if m in comp] + [m for m in comp if m not in ("raw", "caveman", "headroom")]

    out += ["## 1. Model-free: is the needed fact still in the compressed text?\n",
            "Cell = facts kept / tasks · tokens saved (o200k_base, summed over the kind's 20 tasks).\n",
            "| kind | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
    for k in KINDS:
        cells = []
        for m in order:
            rs = [r for r in comp[m] if r["kind"] == k]
            tb = sum(r["tokens_before"] for r in rs)
            ta = sum(r["tokens_after"] for r in rs)
            cells.append(f"{sum(r['kept'] for r in rs)}/{len(rs)} · {100 * (1 - ta / tb):.0f}%")
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    tot = []
    for m in order:
        rs = comp[m]
        tb = sum(r["tokens_before"] for r in rs)
        ta = sum(r["tokens_after"] for r in rs)
        tot.append(f"**{sum(r['kept'] for r in rs)}/{len(rs)} · {100 * (1 - ta / tb):.0f}%**")
    out += ["| all | " + " | ".join(tot) + " |", ""]

    ans = defaultdict(dict)
    for p in sorted(WORK.glob("answers-*.jsonl")):
        _, m, model = p.stem.split("-", 2)
        ans[model][m] = rows(p)
    for model, by_m in ans.items():
        ms = [m for m in order if m in by_m]
        out += [f"## 2. Model: does `{model}` answer correctly from the compressed text?\n",
                "Cell = correct / answered. No retrieval tool was offered.\n",
                "| kind | " + " | ".join(ms) + " |", "|---|" + "---|" * len(ms)]
        for k in KINDS:
            cells = []
            for m in ms:
                rs = [r for r in by_m[m] if r["kind"] == k and not r["err"]]
                cells.append(f"{sum(r['correct'] for r in rs)}/{len(rs)}")
            out.append(f"| {k} | " + " | ".join(cells) + " |")
        cells = []
        for m in ms:
            rs = [r for r in by_m[m] if not r["err"]]
            cells.append(f"**{sum(r['correct'] for r in rs)}/{len(rs)}**")
        out += ["| all | " + " | ".join(cells) + " |", ""]
        wrong = [r for m in ms for r in by_m[m] if not r["correct"] and not r["err"]]
        if wrong:
            out.append("Wrong answers:\n")
            out += [f"- {r['method']} · {r['id']}: answered `{r['answer'][:60]}`, gold `{r['gold']}`" for r in wrong[:40]]
            out.append("")
    (ROOT / "RESULTS.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
