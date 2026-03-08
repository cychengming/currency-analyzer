"""Optional API helpers for deep-learning forecasts stored in Postgres.

This module is safe to import even when DL deps are not installed. Callers should
handle the error messages returned by the functions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _normalize_asset(asset: Optional[str]) -> Optional[str]:
    if asset is None:
        return None
    a = str(asset).strip()
    return a or None


def _try_import_sqlalchemy():
    try:
        from sqlalchemy.orm import Session  # noqa: F401

        return True, None
    except Exception as e:
        return False, f"SQLAlchemy not installed: {e}. Install with: pip install -r requirements-dl.txt"


def get_latest_forecast(asset: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return the latest forecast run + its daily rows.

    Returns:
      (payload, error)
    """

    ok, err = _try_import_sqlalchemy()
    if not ok:
        return None, err

    from sqlalchemy.orm import Session

    from modules.dl_postgres import get_engine, init_dl_schema
    from modules.dl_schema import AssetForecastDaily, ForecastRun, GoldForecastDaily

    engine = get_engine()
    init_dl_schema(engine)

    asset_n = _normalize_asset(asset)

    with Session(engine) as session:
        q = session.query(ForecastRun)
        if asset_n is not None:
            q = q.filter(ForecastRun.asset == asset_n)
        run = q.order_by(ForecastRun.id.desc()).limit(1).one_or_none()
        if run is None:
            if asset_n is not None:
                return None, f"No forecast runs found for asset={asset_n}. Run training first."
            return None, "No forecast runs found. Run training first."

        run_asset = _normalize_asset(getattr(run, "asset", None))
        is_gold = (run_asset is None) or (run_asset.upper() in ("GOLD", "GOLD/USD", "XAUUSD", "XAUUSD/USD"))

        if is_gold:
            rows = (
                session.query(GoldForecastDaily)
                .filter(GoldForecastDaily.run_id == run.id)
                .order_by(GoldForecastDaily.dt.asc())
                .all()
            )
        else:
            rows = (
                session.query(AssetForecastDaily)
                .filter(AssetForecastDaily.run_id == run.id)
                .order_by(AssetForecastDaily.dt.asc())
                .all()
            )

    payload = {
        "run": {
            "id": int(run.id),
            "created_at": run.created_at,
            "model_type": run.model_type,
            "lookback_days": int(run.lookback_days),
            "horizon_days": int(run.horizon_days),
            "asset": run_asset,
            "notes": run.notes,
        },
        "forecast": [{"dt": r.dt, "predicted_close": float(r.predicted_close)} for r in rows],
    }
    return payload, None


def get_forecast_by_run_id(run_id: int) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    ok, err = _try_import_sqlalchemy()
    if not ok:
        return None, err

    from sqlalchemy.orm import Session

    from modules.dl_postgres import get_engine, init_dl_schema
    from modules.dl_schema import AssetForecastDaily, ForecastRun, GoldForecastDaily

    engine = get_engine()
    init_dl_schema(engine)

    with Session(engine) as session:
        run = session.query(ForecastRun).filter(ForecastRun.id == run_id).one_or_none()
        if run is None:
            return None, f"Forecast run_id={run_id} not found"

        run_asset = _normalize_asset(getattr(run, "asset", None))
        is_gold = (run_asset is None) or (run_asset.upper() in ("GOLD", "GOLD/USD", "XAUUSD", "XAUUSD/USD"))

        if is_gold:
            rows = (
                session.query(GoldForecastDaily)
                .filter(GoldForecastDaily.run_id == run.id)
                .order_by(GoldForecastDaily.dt.asc())
                .all()
            )
        else:
            rows = (
                session.query(AssetForecastDaily)
                .filter(AssetForecastDaily.run_id == run.id)
                .order_by(AssetForecastDaily.dt.asc())
                .all()
            )

    payload = {
        "run": {
            "id": int(run.id),
            "created_at": run.created_at,
            "model_type": run.model_type,
            "lookback_days": int(run.lookback_days),
            "horizon_days": int(run.horizon_days),
            "asset": run_asset,
            "notes": run.notes,
        },
        "forecast": [{"dt": r.dt, "predicted_close": float(r.predicted_close)} for r in rows],
    }
    return payload, None


def list_forecast_runs(limit: int = 25) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    ok, err = _try_import_sqlalchemy()
    if not ok:
        return None, err

    from sqlalchemy.orm import Session

    from modules.dl_postgres import get_engine, init_dl_schema
    from modules.dl_schema import ForecastRun

    engine = get_engine()
    init_dl_schema(engine)

    with Session(engine) as session:
        runs = session.query(ForecastRun).order_by(ForecastRun.id.desc()).limit(int(limit)).all()

    out = []
    for r in runs:
        out.append(
            {
                "id": int(r.id),
                "created_at": r.created_at,
                "model_type": r.model_type,
                "lookback_days": int(r.lookback_days),
                "horizon_days": int(r.horizon_days),
                "asset": _normalize_asset(getattr(r, "asset", None)),
                "notes": r.notes,
            }
        )
    return out, None
