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
    extra_message: str | None = None


def _validate_creative_material(df: pd.DataFrame) -> str | None:
    messages: list[str] = []

    if "开始日期" in df.columns:
        start_ser = pd.to_datetime(df["开始日期"], errors="coerce")
        if start_ser.isna().any():
            messages.append("开始日期存在无法识别的值")
    else:
        start_ser = pd.Series(dtype="datetime64[ns]")

    if "结束日期" in df.columns:
        end_ser = pd.to_datetime(df["结束日期"], errors="coerce")
        if end_ser.isna().any():
            messages.append("结束日期存在无法识别的值")
    else:
        end_ser = pd.Series(dtype="datetime64[ns]")

    if len(start_ser) and len(end_ser):
        invalid_range = ((start_ser.notna()) & (end_ser.notna()) & (end_ser < start_ser)).sum()
        if invalid_range > 0:
            messages.append(f"存在 {int(invalid_range)} 行结束日期早于开始日期")

    if "统计天数" in df.columns:
        days_ser = pd.to_numeric(df["统计天数"], errors="coerce")
        bad_days = ((days_ser.isna()) | (days_ser <= 0)).sum()
        if bad_days > 0:
            messages.append(f"存在 {int(bad_days)} 行统计天数无效")
    else:
        days_ser = pd.Series(dtype=float)

    if "数据口径" in df.columns:
        allowed = {"单日", "近7天", "近30天", "近90天", "自定义区间"}
        invalid_scope = (
            ~df["数据口径"].fillna("").astype(str).isin(allowed)
        ).sum()
        if invalid_scope > 0:
            messages.append(f"存在 {int(invalid_scope)} 行数据口径不在允许范围内")

    if "素材编号" in df.columns and "商品ID" in df.columns and "开始日期" in df.columns and "结束日期" in df.columns:
        dup_count = (
            df.assign(
                __商品ID=df["商品ID"].fillna("").astype(str).str.strip(),
                __素材编号=df["素材编号"].fillna("").astype(str).str.strip(),
                __开始日期=df["开始日期"].fillna("").astype(str).str.strip(),
                __结束日期=df["结束日期"].fillna("").astype(str).str.strip(),
            )
            .groupby(["__商品ID", "__素材编号", "__开始日期", "__结束日期"], dropna=False)
            .size()
            .reset_index(name="重复数")
            .query("重复数 > 1")
        )
        if len(dup_count) > 0:
            messages.append(f"存在 {len(dup_count)} 组素材主键重复（商品ID+素材编号+开始日期+结束日期）")

    return "；".join(messages) if messages else None


def validate_table(key: str, df: pd.DataFrame) -> ValidationResult:
    spec = next(item for item in UPLOAD_SPECS if item.key == key)
    missing = _missing_with_alias(key, df, spec.required_columns)
    date_min, date_max = parse_datetime_range(df, DATE_CANDIDATE_COLUMNS.get(key, tuple()))
    extra_message = None

    if key == "creative_material" and len(missing) == 0:
        extra_message = _validate_creative_material(df)

    return ValidationResult(
        key=key,
        label=spec.label,
        ok=len(missing) == 0,
        missing_columns=missing,
        record_count=len(df),
        date_min=str(date_min.date()) if date_min is not None else None,
        date_max=str(date_max.date()) if date_max is not None else None,
        extra_message=extra_message,
    )


def validate_all(tables: dict[str, pd.DataFrame]) -> list[ValidationResult]:
    return [validate_table(spec.key, tables[spec.key]) for spec in UPLOAD_SPECS if spec.key in tables]
