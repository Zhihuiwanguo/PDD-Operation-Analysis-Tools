"""工具函数。"""

from __future__ import annotations

from typing import Any

import pandas as pd


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def parse_datetime_range(df: pd.DataFrame, date_columns: tuple[str, ...]) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    for col in date_columns:
        if col in df.columns:
            ser = pd.to_datetime(df[col], errors="coerce")
            if ser.notna().any():
                return ser.min(), ser.max()
    return None, None


def to_numeric(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    return out


def safe_divide(numerator: Any, denominator: Any) -> float:
    try:
        n = float(numerator)
        d = float(denominator)
    except (TypeError, ValueError):
        return 0.0
    if d == 0:
        return 0.0
    return n / d


def pick_first_existing(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None
