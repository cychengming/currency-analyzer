"""Postgres helpers for DL/ETL pipeline.

This module is intentionally separate from the main SQLite database used by the web app.
It reads the DSN from env var POSTGRES_DSN.

Usage:
  from modules.dl_postgres import get_engine, init_dl_schema
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


DEFAULT_POSTGRES_DSN = "postgresql+psycopg2://currency:currency@localhost:5432/currency_analyzer"


def get_postgres_dsn() -> str:
    return os.environ.get("POSTGRES_DSN", DEFAULT_POSTGRES_DSN)


def get_engine(dsn: Optional[str] = None) -> Engine:
    dsn = dsn or get_postgres_dsn()
    # pool_pre_ping helps avoid stale connections
    return create_engine(dsn, pool_pre_ping=True)


@dataclass(frozen=True)
class DLIngestConfig:
    years: int = 30
    # World Bank country codes (ISO3)
    gdp_countries: Tuple[str, ...] = ("WLD", "USA", "CHN", "EUU", "JPN", "IND")


def init_dl_schema(engine: Optional[Engine] = None) -> None:
    from modules.dl_schema import Base  # local import to avoid import cycles

    engine = engine or get_engine()
    Base.metadata.create_all(engine)

    # Lightweight migrations for existing tables (create_all does not ALTER).
    # Keep this minimal and Postgres-compatible.
    try:
        from sqlalchemy import inspect, text

        insp = inspect(engine)

        # dl_forecast_runs: add optional asset column (multi-asset support)
        if insp.has_table("dl_forecast_runs"):
            cols = {c["name"] for c in insp.get_columns("dl_forecast_runs")}
            if "asset" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE dl_forecast_runs ADD COLUMN IF NOT EXISTS asset VARCHAR(32)"))

        if insp.has_table("gold_daily"):
            cols = {c["name"] for c in insp.get_columns("gold_daily")}
            alter = []
            if "open" not in cols:
                alter.append("ADD COLUMN IF NOT EXISTS open DOUBLE PRECISION")
            if "high" not in cols:
                alter.append("ADD COLUMN IF NOT EXISTS high DOUBLE PRECISION")
            if "low" not in cols:
                alter.append("ADD COLUMN IF NOT EXISTS low DOUBLE PRECISION")
            if alter:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE gold_daily {', '.join(alter)}"))
    except Exception:
        # Best-effort: if migration fails, callers will still work with close-only data.
        pass
