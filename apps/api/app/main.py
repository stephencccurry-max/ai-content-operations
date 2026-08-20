from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import content, exports, health, internal, reviews, tasks
from app.errors import register_error_handlers
from app.middleware import RequestIdMiddleware

LOCAL_WEB_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]


def create_app() -> FastAPI:
    app = FastAPI(title="AI Content Ops API")
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_WEB_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Request-Id"],
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(content.router, prefix="/api/v1")
    app.include_router(reviews.router, prefix="/api/v1")
    app.include_router(exports.router, prefix="/api/v1")
    app.include_router(internal.router, prefix="/internal/v1")
    return app


app = create_app()
