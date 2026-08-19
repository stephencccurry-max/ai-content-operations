from fastapi import FastAPI

from app.api import health
from app.errors import register_error_handlers
from app.middleware import RequestIdMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="AI Content Ops API")
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
