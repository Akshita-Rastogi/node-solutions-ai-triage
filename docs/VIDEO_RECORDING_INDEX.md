# Recording Guide

Use these three scripts as a coordinated submission set:

1. [`VIDEO_1_PRODUCT_DEMO_SCRIPT.md`](VIDEO_1_PRODUCT_DEMO_SCRIPT.md) — all twelve scenarios, one custom
   example, evaluation, technology choices, guardrails, and brownie features.
2. [`VIDEO_2_REDIS_POSTGRES_SCRIPT.md`](VIDEO_2_REDIS_POSTGRES_SCRIPT.md) — RedisInsight, Redis CLI,
   DBeaver, durable review evidence, idempotency, logs, and metrics.
3. [`VIDEO_3_CODE_ARCHITECTURE_SCRIPT.md`](VIDEO_3_CODE_ARCHITECTURE_SCRIPT.md) — file-by-file code flow,
   LangGraph branching, model boundary, security, tests, outputs, and architecture decisions.

Record Video 1 first because it defines the user-visible problem and explicitly directs reviewers to the two
deeper videos. Record Video 2 immediately after generating demo traffic so PostgreSQL has records and Redis
TTL keys can be captured. Record Video 3 last with VS Code prepared and the technical conditional graph open.

Before recording:

```bash
docker compose up -d --build
docker compose ps
curl -s http://localhost:8100/health/ready | python -m json.tool
docker compose exec api pytest -q
docker compose exec api python scripts/evaluate.py
```

Open the required screens:

```bash
open http://localhost:8601
open http://localhost:8100/docs
code .
```

