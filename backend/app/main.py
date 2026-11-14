"""The FastAPI application: middleware (request id, access log, headers, CORS), error envelope, routers."""
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import logging as applog
from app.api import auth, catalog, enrollments, errors, exceptions, learner, metrics, payments, students
from app.config import settings

settings.check()                       # S-6: refuse to start in production with default secrets
applog.setup()

app = FastAPI(title="StudEase API", version="1.0.0", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json",
              redoc_url=None, description="Tuition and fees, scholarships, payment allocation and balance "
              "reconciliation. Money is integer paise. See docs/architecture.md.")
errors.install(app)

# S-11: only the configured origins, no wildcard, no credentials mode (the token travels in a header).
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
                   expose_headers=["X-Request-ID", "Idempotent-Replay"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = uuid.uuid4().hex[:16]
    request.state.request_id = rid
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    applog.event(rid=rid, method=request.method, path=request.url.path, status=response.status_code,
                 ms=round((time.perf_counter() - started) * 1000, 1))
    return response


for module in (auth, metrics, students, catalog, payments, enrollments, exceptions, learner):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {"name": "StudEase API", "docs": "/api/v1/docs", "health": "/api/v1/healthz"}
