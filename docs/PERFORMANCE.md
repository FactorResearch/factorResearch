# Performance Contract

## Service objectives

| Path | p50 | p95 |
|---|---:|---:|
| Cached analysis | 100 ms | 300 ms |
| Fresh primary analysis | 1.5 s | 3 s |
| Secondary enrichment | 5 s | 15 s |
| Quick Peek | 100 ms | 200 ms |
| Chart expansion | 400 ms | 750 ms |

Target error rate is below 0.5%. Initial analysis payloads should remain below 64 KB; chart history is fetched only after expansion.

## Production topology

- Web workers serve cached/primary analysis and enqueue secondary jobs.
- Redis coordinates single-flight work, component caches, demand ranking, and the durable analysis queue.
- Exactly one designated process sets `ANALYSIS_BACKGROUND_JOBS=1`; it consumes jobs and refreshes shared context/popular symbols.
- PostgreSQL remains authoritative for complete and stale-while-revalidate analysis records.

## Required monitoring

Set `INTERNAL_METRICS_TOKEN` and query `/_internal/performance` with `X-Internal-Metrics-Token`. Alert on p95 latency, error rate, provider circuit state, queue age, PostgreSQL saturation, stale-record percentage, and payload growth.

## Rollout

Canary each optimization independently. Compare model outputs before/after deployment, then roll back when error rate exceeds 0.5%, p95 regresses by 20%, or result-equivalence tests fail.
