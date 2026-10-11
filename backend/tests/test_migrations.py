from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from app.db import create_db_engine, make_alembic_config, run_migrations
from app.repositories.models import Base


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    e = create_db_engine(f"sqlite:///{tmp_path / 'm.db'}")
    yield e
    e.dispose()


def test_migrations_create_tables(engine: Engine) -> None:
    run_migrations(engine)
    assert {"users", "alembic_version"} <= set(inspect(engine).get_table_names())


def test_migrations_are_idempotent(engine: Engine) -> None:
    run_migrations(engine)
    run_migrations(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == [
            "0001"
        ]


def test_migrations_match_models(engine: Engine) -> None:
    run_migrations(engine)
    with engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []


def test_migration_downgrade_to_base(engine: Engine) -> None:
    run_migrations(engine)
    with engine.begin() as c:
        command.downgrade(make_alembic_config(c), "base")
    assert "users" not in inspect(engine).get_table_names()


def test_sqlite_foreign_keys_enabled(engine: Engine) -> None:
    with engine.connect() as c:
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_create_db_engine_rejects_non_sqlite() -> None:
    with pytest.raises(ValueError, match="only SQLite database URLs are supported"):
        create_db_engine("postgresql://u@h/db")
