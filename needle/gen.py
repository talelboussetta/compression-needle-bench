"""Generate needle-in-tool-output tasks.

Each task is a realistic tool output (JSON, logs, test run, CSV) with one fact an agent
would need, a question about it, the exact gold answer, and a key: a string next to the answer in the
original (the order id, "ERROR", "FAILED"...). The model-free check counts the fact as kept
only if gold and key still appear within 300 characters of each other. The haystacks are what
compressors are good at shrinking: repetitive records and log lines. The needle is the
one thing a lossy compressor must not drop.

  python -m needle.gen --per-kind 20 --out tasks.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import string
from datetime import datetime, timedelta

NAMES = ["amira", "youssef", "sami", "leila", "omar", "ines", "karim", "nour", "hedi", "salma"]
CITIES = ["Tunis", "Sfax", "Sousse", "Lyon", "Paris", "Marseille", "Algiers", "Oran"]


def rid(rnd, prefix, n=6):
    return prefix + "".join(rnd.choice(string.ascii_uppercase + string.digits) for _ in range(n))


def json_unique_status(rnd):
    """300 orders, exactly one refunded. Q: id of the refunded order."""
    rows, target = [], rnd.randrange(40, 260)
    for i in range(300):
        rows.append({
            "id": rid(rnd, "ORD-"), "customer": rnd.choice(NAMES), "city": rnd.choice(CITIES),
            "status": "refunded" if i == target else rnd.choice(["delivered", "delivered", "shipped", "pending"]),
            "amount": round(rnd.uniform(10, 400), 2), "items": rnd.randint(1, 5),
        })
    return json.dumps(rows, indent=1), "What is the id of the only order whose status is refunded?", rows[target]["id"], "refunded"


def json_lookup(rnd):
    """300 orders. Q: amount of one named order from the middle of the list."""
    rows = [{"id": rid(rnd, "ORD-"), "customer": rnd.choice(NAMES), "status": rnd.choice(["delivered", "shipped"]),
             "amount": round(rnd.uniform(10, 400), 2)} for _ in range(300)]
    t = rows[rnd.randrange(60, 240)]
    return json.dumps(rows, indent=1), f"What is the amount of order {t['id']}? Answer with the number only.", f"{t['amount']}", t["id"]


def json_near_duplicate(rnd):
    """250 identical config objects except one, which has a different timeout. Q: that timeout."""
    base = {"service": "worker", "region": "eu-west-1", "retries": 3, "timeout_ms": 30000, "tls": True}
    target = rnd.randrange(30, 220)
    odd = rnd.choice([31000, 29500, 45000, 30500, 12000])
    rows = []
    for i in range(250):
        r = dict(base, id=f"w-{i:03d}")
        if i == target:
            r["timeout_ms"] = odd
        rows.append(r)
    return (json.dumps(rows, indent=1),
            "One worker has a timeout_ms different from all the others. What is its id?",
            f"w-{target:03d}", str(odd))


def log_error(rnd):
    """2,000 log lines, one ERROR with a code. Q: the code."""
    t0 = datetime(2026, 11, 3, 9, 0, 0)
    target = rnd.randrange(300, 1700)
    code = "E" + str(rnd.randrange(1000, 9999))
    lines = []
    for i in range(2000):
        ts = (t0 + timedelta(milliseconds=137 * i)).isoformat(timespec="milliseconds")
        if i == target:
            lines.append(f"{ts} ERROR payment-svc charge failed code={code} attempt=1")
        else:
            lvl = rnd.choice(["INFO", "INFO", "DEBUG"])
            lines.append(f"{ts} {lvl} http GET /api/v1/items/{rnd.randrange(1, 500)} 200 {rnd.randrange(3, 90)}ms")
    return "\n".join(lines), "What error code does the single ERROR line in this log report?", code, "ERROR"


def test_run(rnd):
    """A pytest run: 300 passes, one failure. Q: the failing test's name."""
    mods = ["test_cart", "test_orders", "test_auth", "test_search", "test_payments"]
    names = [f"tests/{rnd.choice(mods)}.py::test_{rid(rnd, '', 5).lower()}" for _ in range(301)]
    target = rnd.randrange(50, 280)
    out = ["============================= test session starts =============================",
           "platform linux -- Python 3.12.4, pytest-8.3.2", "collected 301 items", ""]
    for i, n in enumerate(names):
        out.append(f"{n} {'FAILED' if i == target else 'PASSED'}")
    exp = rnd.randrange(10, 99)
    out += ["", "=================================== FAILURES ===================================",
            f"___ {names[target].split('::')[1]} ___", f"    assert total == {exp}",
            f"E   assert {exp - 1} == {exp}", "", f"=== 1 failed, 300 passed in 41.2s ==="]
    return "\n".join(out), "Which test failed? Give the test function name only.", names[target].split("::")[1], "FAILED"


def csv_lookup(rnd):
    """500 product rows. Q: price of one SKU."""
    rows = ["sku,name,category,price,stock"]
    skus = []
    for _ in range(500):
        s = rid(rnd, "SKU-", 5)
        skus.append(s)
        rows.append(f"{s},basket {rnd.choice(['small','medium','large'])},{rnd.choice(['home','bags','decor'])},"
                    f"{rnd.randrange(15, 90)}.{rnd.choice(['00','50','90'])},{rnd.randrange(0, 40)}")
    i = rnd.randrange(100, 400)
    price = rows[i + 1].split(",")[3]
    return "\n".join(rows), f"What is the price of {skus[i]}? Answer with the number only.", price, skus[i]


KINDS = {
    "json_unique_status": json_unique_status,
    "json_lookup": json_lookup,
    "json_near_duplicate": json_near_duplicate,
    "log_error": log_error,
    "test_run": test_run,
    "csv_lookup": csv_lookup,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-kind", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--out", default="tasks.jsonl")
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    with open(a.out, "w", encoding="utf-8") as f:
        for kind, fn in KINDS.items():
            for i in range(a.per_kind):
                text, q, gold, key = fn(rnd)
                f.write(json.dumps({"id": f"{kind}-{i:02d}", "kind": kind, "tool_output": text,
                                    "question": q, "gold": gold, "key": key}) + "\n")
    print(f"wrote {a.per_kind * len(KINDS)} tasks to {a.out}")


if __name__ == "__main__":
    main()
