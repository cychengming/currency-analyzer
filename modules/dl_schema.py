"""SQLAlchemy schema for deep-learning dataset storage."""

from typing import Optional

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Float, Integer, String, UniqueConstraint


class Base(DeclarativeBase):
    pass


class GoldDaily(Base):
    __tablename__ = "gold_daily"
    __table_args__ = (UniqueConstraint("dt", name="uq_gold_daily_dt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dt: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    open: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class UsdIndexDaily(Base):
    __tablename__ = "usd_index_daily"
    __table_args__ = (UniqueConstraint("dt", name="uq_usd_index_daily_dt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dt: Mapped[str] = mapped_column(String(10), nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)


class GdpAnnual(Base):
    __tablename__ = "gdp_annual"
    __table_args__ = (UniqueConstraint("country", "year", name="uq_gdp_country_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country: Mapped[str] = mapped_column(String(8), nullable=False)  # ISO3 or WLD
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    gdp_current_usd: Mapped[float] = mapped_column(Float, nullable=False)


class ForecastRun(Base):
    __tablename__ = "dl_forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # ISO string
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # lstm/gru
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # Optional asset identifier (e.g. 'GOLD/USD', 'EUR/USD').
    # Kept nullable for backwards-compatibility with existing runs.
    asset: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class GoldForecastDaily(Base):
    __tablename__ = "gold_forecast_daily"
    __table_args__ = (UniqueConstraint("run_id", "dt", name="uq_gold_forecast_run_dt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    dt: Mapped[str] = mapped_column(String(10), nullable=False)
    predicted_close: Mapped[float] = mapped_column(Float, nullable=False)


class AssetForecastDaily(Base):
    __tablename__ = "asset_forecast_daily"
    __table_args__ = (UniqueConstraint("run_id", "dt", name="uq_asset_forecast_run_dt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    dt: Mapped[str] = mapped_column(String(10), nullable=False)
    predicted_close: Mapped[float] = mapped_column(Float, nullable=False)
