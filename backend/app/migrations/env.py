from typing import cast

from alembic import context
from sqlalchemy.engine import Connection

from app.db import create_db_engine
from app.repositories.models import Base


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = cast("Connection | None", context.config.attributes.get("connection"))
if connection is None:
    url = context.config.get_main_option("sqlalchemy.url")
    if url is None:
        raise RuntimeError("sqlalchemy.url is not configured")
    engine = create_db_engine(url)
    with engine.begin() as conn:
        _run(conn)
    engine.dispose()
else:
    _run(connection)
