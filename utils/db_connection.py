"""Database connection helpers.

Reads `DATABASE_URL` from the environment. If not set, falls back to
an SQLite database at `database/sales.db`.

Provides `execute_sql(query)` with error handling and `test_connection()`.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


HERE = Path(__file__).resolve().parent
SQLITE_PATH = HERE.parent / "database" / "sales.db"


def _get_database_url() -> Optional[str]:
    # Read from environment only; do not hardcode credentials here
    return os.environ.get("DATABASE_URL")


def get_engine() -> Engine:
    """Create (or recreate) a SQLAlchemy engine based on env var or sqlite."""
    database_url = _get_database_url()
    if database_url:
        return create_engine(database_url)

    # Fallback to sqlite file in repository
    sqlite_url = f"sqlite:///{SQLITE_PATH.as_posix()}"
    return create_engine(sqlite_url)


def execute_sql(query: str) -> pd.DataFrame:
    """Execute a SQL query and return a pandas DataFrame.

    Raises a RuntimeError with details on failure.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()
            df = pd.DataFrame(rows, columns=columns)
        return df
    except Exception as e:
        # Provide a clearer error for the calling code
        raise RuntimeError(f"Database query failed: {e}") from e


def execute_non_query(query: str, params: Optional[dict] = None) -> None:
    """Execute INSERT/UPDATE/DELETE statements."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text(query), params or {})
            # Some dialects require explicit commit on the connection
            if hasattr(conn, "commit"):
                conn.commit()
    except Exception as e:
        raise RuntimeError(f"Database non-query failed: {e}") from e


def test_connection() -> Tuple[bool, str]:
    """Test database connectivity.

    Returns (True, message) on success, or (False, error_message) on failure.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            # Simple DB-agnostic test
            result = conn.execute(text("SELECT 1"))
            _ = result.scalar()
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)


__all__ = ["get_engine", "execute_sql", "execute_non_query", "test_connection"]