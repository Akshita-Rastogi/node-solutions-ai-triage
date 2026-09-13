import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_URL = os.getenv("API_URL", "http://localhost:8100")
API_KEY = os.getenv("API_KEY", "demo-key")


def main() -> None:
    """Run the challenge golden set through the real API and write a reproducible report."""
    cases = json.loads((ROOT / "data" / "evaluation.json").read_text(encoding="utf-8"))
    results = []
    with httpx.Client(timeout=90, headers={"X-API-Key": API_KEY}) as client:
        for case in cases:
            response = client.post(f"{API_URL}/v1/triage", json={
                "request_text": case["request_text"], "source": "web",
                "idempotency_key": f"evaluation-{case['id']}-{uuid4()}",
            })
            response.raise_for_status()
            actual = response.json()
            checks = {field: actual[field] == case[f"expected_{field}"]
                      for field in ("category", "priority", "owner")}
            results.append({"id": case["id"], "expected": case, "actual": actual,
                            "checks": checks, "passed": all(checks.values())})
    report = {"passed": sum(row["passed"] for row in results),
              "total": len(results), "results": results}
    destination = ROOT / "output" / "evaluation-results.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Golden evaluation: {report['passed']}/{report['total']} passed")
    print(f"Detailed evidence: {destination}")


if __name__ == "__main__":
    main()
