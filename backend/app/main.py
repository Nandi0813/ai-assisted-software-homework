from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app.api.auth import router as auth_router
from app.api.deps import AppContext
from app.api.groups import router as groups_router
from app.api.health import router as health_router
from app.config import Settings, load_settings
from app.db import create_db_engine, run_migrations


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else load_settings()
    engine = create_db_engine(resolved.database_url)
    context = AppContext(
        settings=resolved,
        engine=engine,
        session_factory=sessionmaker(bind=engine, expire_on_commit=False),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        run_migrations(engine)
        yield
        engine.dispose()

    app = FastAPI(title="SplitLedger API", version="0.1.0", lifespan=lifespan)
    app.state.context = context
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(groups_router, prefix="/api")
    return app


app = create_app()
