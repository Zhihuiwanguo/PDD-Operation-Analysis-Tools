"""数据存储与配置记忆模块。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path("data")
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "business_config.json"

DEFAULT_CONFIG = {
    "q2_sales_target": 0,
    "q2_roi_target": 1.0,
    "gross_margin_warning": 0.5,
    "personal_score": 100,
}


def ensure_storage_dirs() -> None:
    for d in (RAW_DIR, PROCESSED_DIR, CONFIG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


def save_raw_data(orders_df: pd.DataFrame, promo_df: pd.DataFrame | None):
    ensure_storage_dirs()
    ts = _timestamp()
    orders_path = RAW_DIR / f"orders_{ts}.csv"
    orders_df.to_csv(orders_path, index=False)

    promo_path = None
    if promo_df is not None and not promo_df.empty:
        promo_path = RAW_DIR / f"promo_{ts}.csv"
        promo_df.to_csv(promo_path, index=False)

    return {"orders": str(orders_path), "promo": str(promo_path) if promo_path else None}


def _to_jsonable(obj: Any):
    if isinstance(obj, pd.DataFrame):
        return {
            "__type__": "dataframe",
            "columns": list(obj.columns),
            "data": obj.to_dict(orient="records"),
        }
    if isinstance(obj, pd.Series):
        return {"__type__": "series", "name": obj.name, "data": obj.to_list()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj


def _from_jsonable(obj: Any):
    if isinstance(obj, dict):
        t = obj.get("__type__")
        if t == "dataframe":
            return pd.DataFrame(obj.get("data", []), columns=obj.get("columns", []))
        if t == "series":
            return pd.Series(obj.get("data", []), name=obj.get("name"))
        return {k: _from_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_jsonable(v) for v in obj]
    return obj


def save_analysis_result(result_dict: dict):
    ensure_storage_dirs()
    ts = _timestamp()
    path = PROCESSED_DIR / f"analysis_{ts}.json"
    payload = _to_jsonable(result_dict)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return str(path)


def load_latest_analysis():
    ensure_storage_dirs()
    files = sorted(PROCESSED_DIR.glob("analysis_*.json"), key=lambda p: p.name)
    if not files:
        return None
    latest = files[-1]
    with latest.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _from_jsonable(data)


def save_config(config_dict: dict):
    ensure_storage_dirs()
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config_dict, f, ensure_ascii=False, indent=2)


def load_config():
    ensure_storage_dirs()
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    merged = DEFAULT_CONFIG.copy()
    merged.update(loaded or {})
    return merged


ensure_storage_dirs()
