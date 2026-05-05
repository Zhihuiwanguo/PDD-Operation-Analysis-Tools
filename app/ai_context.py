"""Build compact AI context from current business analysis context."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def safe_round(value: Any, digits: int = 4):
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return value
    if math.isnan(num) or math.isinf(num):
        return None
    return round(num, digits)


def pick_existing_columns(df: pd.DataFrame, columns: list[str]) -> list[str]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [c for c in columns if c in df.columns]


def df_to_records(df: pd.DataFrame, columns: list[str], limit: int = 10) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    use_cols = pick_existing_columns(df, columns)
    if not use_cols:
        return []
    chunk = df.loc[:, use_cols].head(limit).copy()
    for col in chunk.columns:
        chunk[col] = chunk[col].map(lambda x: safe_round(x, 4))
    return chunk.to_dict(orient="records")


def build_ai_context(ctx: dict, q2_result: dict | None, notes: list | None = None) -> dict:
    overview_metrics = (((ctx or {}).get("overview") or {}).get("metrics") or {})
    product_df = (ctx or {}).get("product_summary", pd.DataFrame())
    link_df = (ctx or {}).get("link_summary", pd.DataFrame())
    baibu_df = (ctx or {}).get("baibu_vs_normal", pd.DataFrame())

    product_cols = [
        "标准产品名称", "商家实收", "订单侧估算毛利", "链接推广费合计", "扣推广后贡献毛利",
        "实际ROI", "盈亏平衡ROI", "订单侧毛利率", "推广费率", "百补销售占比", "产品层级标签",
    ]
    link_cols = [
        "商品ID", "链接标题", "标准产品名称", "是否百补", "商家实收", "订单侧估算毛利", "实际成交花费(元)",
        "扣推广后贡献毛利", "实际ROI", "盈亏平衡ROI", "订单无效率",
    ]
    baibu_cols = ["是否百补", "有效订单数", "商家实收", "推广费", "扣推广后贡献毛利", "实际ROI", "盈亏平衡ROI"]

    loss_products = pd.DataFrame()
    high_roi_products = pd.DataFrame()
    if isinstance(product_df, pd.DataFrame) and not product_df.empty:
        if "扣推广后贡献毛利" in product_df.columns:
            loss_products = product_df[product_df["扣推广后贡献毛利"] < 0].sort_values("扣推广后贡献毛利")
        if all(c in product_df.columns for c in ["实际ROI", "链接推广费合计"]):
            high_roi_products = product_df[(product_df["链接推广费合计"] > 0)].sort_values("实际ROI", ascending=False)

    low_roi_links = pd.DataFrame()
    if isinstance(link_df, pd.DataFrame) and not link_df.empty and all(c in link_df.columns for c in ["实际ROI", "盈亏平衡ROI"]):
        low_roi_links = link_df[link_df["实际ROI"] < link_df["盈亏平衡ROI"]].sort_values("实际ROI")

    note_tail = (notes or [])[:10]

    return {
        "report_scope": {
            "date_field_used": (ctx or {}).get("date_field_used", ""),
            "channel": "拼多多",
        },
        "overview": {
            "商家实收": safe_round(overview_metrics.get("商家实收")),
            "用户实付": safe_round(overview_metrics.get("用户实付")),
            "有效订单数": safe_round(overview_metrics.get("有效订单数")),
            "订单侧估算毛利": safe_round(overview_metrics.get("订单侧估算毛利")),
            "店铺总盘推广费": safe_round(overview_metrics.get("店铺总盘推广费（现金口径）")),
            "店铺整体实际ROI": safe_round(overview_metrics.get("店铺整体实际ROI")),
            "店铺扣推广后贡献毛利": safe_round(overview_metrics.get("店铺扣推广后贡献毛利")),
            "盈亏平衡ROI": safe_round(overview_metrics.get("盈亏平衡ROI")),
        },
        "q2_kpi": {k: safe_round(v) for k, v in (q2_result or {}).items()},
        "top_products": df_to_records(product_df, product_cols, limit=10),
        "loss_products": df_to_records(loss_products, product_cols, limit=10),
        "high_roi_products": df_to_records(high_roi_products, product_cols, limit=10),
        "top_links": df_to_records(link_df, link_cols, limit=10),
        "low_roi_links": df_to_records(low_roi_links, link_cols, limit=10),
        "baibu_vs_normal": df_to_records(baibu_df, baibu_cols, limit=10),
        "business_notes": note_tail,
    }
