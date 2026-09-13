from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

import asyncpg
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from triage.config import get_settings
from triage.database import Database
from triage.graph import build_graph
from triage.logging import configure_logging
from triage.metrics import DECISIONS, LATENCY, REQUESTS
from triage.models import ReviewRequest, TriageRequest, TriageResult
from triage.ollama import OllamaClient
from triage.rate_limit import RateLimiter
from triage.security import require_api_key
from triage.service import TriageService

configure_logging()
logger = structlog.get_logger("triage.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared clients once and close them cleanly on termination."""
    database = Database(settings.database_url)
    limiter = RateLimiter(settings.redis_url, settings.rate_limit_per_minute)
    ollama = OllamaClient(settings.ollama_url, settings.ollama_model,
                          settings.ollama_timeout_seconds)
    await database.connect()
    app.state.database = database
    app.state.limiter = limiter
    app.state.ollama = ollama
    app.state.service = TriageService(build_graph(ollama), database, settings.ollama_model)
    logger.info("service_started", environment=settings.app_env)
    yield
    await limiter.close()
    await database.close()


app = FastAPI(title="Node Solutions AI Request Triage", version="1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach correlation IDs and structured latency logs to every API request."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:100]
    started = perf_counter()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_request_error", path=request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    response.headers["X-Request-ID"] = request_id
    route = request.scope.get("route")
    path = route.path if route else request.url.path
    duration = perf_counter() - started
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(duration)
    logger.info("request_completed", method=request.method, path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2))
    structlog.contextvars.clear_contextvars()
    return response


@app.get("/health/live")
async def live() -> dict:
    """Liveness only confirms that the API process can serve requests."""
    return {"status": "alive"}


@app.get("/health/ready")
async def ready(request: Request, response: Response) -> dict:
    """Readiness checks every dependency required for a fully capable request."""
    dependencies = {
        "postgres": await request.app.state.database.healthy(),
        "redis": await request.app.state.limiter.healthy(),
        "ollama": await request.app.state.ollama.health(),
    }
    if not all(dependencies.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if all(dependencies.values()) else "degraded",
            "dependencies": dependencies}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose Prometheus metrics without placing request contents in labels."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/triage", response_model=TriageResult, status_code=201)
async def create_triage(payload: TriageRequest, response: Response, request: Request,
                        identity: str = Depends(require_api_key)) -> TriageResult:
    """Validate, rate-limit, analyse, guard, draft and persist one client request."""
    if not await request.app.state.limiter.allow(identity):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    try:
        result, replayed = await request.app.state.service.triage(payload)
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(status_code=409, detail="Idempotency conflict") from exc
    if replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    else:
        DECISIONS.labels(result.category.value, result.priority.value,
                         result.decision_source).inc()
    return result


@app.get("/v1/triage", response_model=list[TriageResult])
async def list_triage(request: Request, limit: int = 20,
                      _: str = Depends(require_api_key)) -> list[TriageResult]:
    """Return the review queue with a bounded page size."""
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    return await request.app.state.database.list(limit)


@app.get("/v1/triage/{request_id}", response_model=TriageResult)
async def get_triage(request_id: UUID, request: Request,
                     _: str = Depends(require_api_key)) -> TriageResult:
    """Fetch a single durable result or report a precise not-found response."""
    result = await request.app.state.database.get(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Triage request not found")
    return result


@app.post("/v1/triage/{request_id}/review", status_code=201)
async def review_triage(request_id: UUID, payload: ReviewRequest, request: Request,
                        _: str = Depends(require_api_key)) -> dict:
    """Capture one human approval/correction/rejection without rewriting AI history."""
    if not await request.app.state.database.get(request_id):
        raise HTTPException(status_code=404, detail="Triage request not found")
    if not await request.app.state.database.add_review(request_id, payload):
        raise HTTPException(status_code=409, detail="Review already submitted")
    return {"request_id": request_id, "status": "review_recorded"}
