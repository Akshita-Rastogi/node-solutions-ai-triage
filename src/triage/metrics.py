from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "triage_http_requests_total", "HTTP requests completed", ["method", "path", "status"]
)
LATENCY = Histogram(
    "triage_http_request_duration_seconds", "HTTP request latency", ["method", "path"]
)
DECISIONS = Counter(
    "triage_decisions_total", "Triage decisions produced", ["category", "priority", "source"]
)
