# Results

## 1. Model-free: is the needed fact still in the compressed text?

Cell = facts kept / tasks · tokens saved (o200k_base, summed over the kind's 20 tasks).

| kind | raw | caveman | headroom |
|---|---|---|---|
| json_unique_status | 20/20 · 0% | 20/20 · 41% | 20/20 · 62% |
| json_lookup | 20/20 · 0% | 20/20 · 0% | 20/20 · 58% |
| json_near_duplicate | 20/20 · 0% | 20/20 · 97% | 20/20 · 66% |
| log_error | 20/20 · 0% | 20/20 · 100% | 20/20 · 100% |
| test_run | 20/20 · 0% | 20/20 · 0% | 20/20 · 0% |
| csv_lookup | 20/20 · 0% | 20/20 · 0% | 20/20 · 0% |
| all | **120/120 · 0%** | **120/120 · 70%** | **120/120 · 75%** |
