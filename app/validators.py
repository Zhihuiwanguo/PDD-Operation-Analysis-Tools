"""上传表校验器。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.constants import DATE_CANDIDATE_COLUMNS, UPLOAD_SPECS
from app.utils import parse_datetime_range


def _missing_with_alias(key: str, df: pd.DataFrame, required_cols: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for col in required_cols:
        if key == "orders" and col == "商品id":
            if ("商品id" not in df.columns) and ("商品ID" not in df.columns):
                missing.append("商品id/商品ID")
            continue
        if col not in df.columns:
            missing.append(col)
    return missing


@dataclass
class ValidationResult:
    key: str
    label: str
    ok: bool
    missing_columns: list[str]
    record_count: int
    date_min: str | None
    date_max: str | None


def validate_table(key: str, df: pd.DataFrame) -> ValidationResult:
    spec = next(item for item in UPLOAD_SPECS if item.key == key)
    missing = _missing_with_alias(key, df, spec.required_columns)
    date_min, date_max = parse_datetime_range(df, DATE_CANDIDATE_COLUMNS.get(key, tuple()))
    return ValidationResult(
        key=key,
        label=spec.label,
        ok=len(missing) == 0,
        missing_columns=missing,
        record_count=len(df),
        date_min=str(date_min.date()) if date_min is not None else None,
        date_max=str(date_max.date()) if date_max is not None else None,
    )


def validate_all(tables: dict[str, pd.DataFrame]) -> list[ValidationResult]:
    return [validate_table(spec.key, tables[spec.key]) for spec in UPLOAD_SPECS if spec.key in tables]
