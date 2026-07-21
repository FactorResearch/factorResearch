# Load Proof Workloads

Run only against an approved staging environment with synthetic accounts/data and provider stubs. Never point certification traffic at live external market-data providers.

```bash
uv sync --frozen
locust -f load/locustfile.py --headless --host "$STAGING_URL" \
  --users 100 --spawn-rate 20 --run-time 60m \
  --csv artifacts/production-proof/02-performance/peak

PYTHONPATH=. python scripts/evaluate-load.py \
  artifacts/production-proof/02-performance/peak_stats.csv \
  --max-p95-ms 1500 --max-failure-rate 0.001 \
  --output artifacts/production-proof/02-performance/peak-verdict.json
```

## Required Profiles

| Profile | Users | Spawn | Duration | Purpose |
|---|---:|---:|---:|---|
| Baseline | 1 | 1/s | 10m | establish warm/cold single-user latency |
| Expected peak | 100 | 20/s | 60m | prove launch envelope |
| Stress | step 100 to failure | 20/s | 15m/step | identify first bottleneck and safe ceiling |
| Spike | 200 | 200/10s | 15m | prove overload/recovery behavior |
| Soak | 100 | 10/s | 12h | detect memory, connection, descriptor, and queue growth |
| Long soak | 25 | 5/s | 72h | prove stable long-lived workers |

Capture the application operational snapshot, hosting metrics, PostgreSQL statistics, Redis statistics, queue depth, and process/thread/descriptor counts throughout each run.
