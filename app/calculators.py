"""经营口径计算。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import CONFIG
from app.utils import safe_divide


def _is_bb(text: str) -> bool:
    return any(k in text for k in CONFIG.business_rules.bb_keywords)


def classify_orders(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["订单状态"] = out["订单状态"].fillna("").astype(str)
    out["售后状态"] = out["售后状态"].fillna("").astype(str)
    out["商品"] = out.get("商品", "").fillna("").astype(str)

    invalid_by_order = out["订单状态"].isin(CONFIG.business_rules.invalid_order_statuses)
    invalid_by_aftersale = out["售后状态"].isin(CONFIG.business_rules.invalid_after_sale_statuses)
    pending = out["售后状态"].isin(CONFIG.business_rules.pending_after_sale_statuses)
    non_operating = out["商品"].str.contains("|".join(CONFIG.business_rules.non_operating_keywords), na=False)

    effective_by_status = out["订单状态"].apply(
        lambda x: any(k in x for k in CONFIG.business_rules.effective_order_status_keywords)
    )
    is_effective = effective_by_status & (~invalid_by_order) & (~invalid_by_aftersale) & (~pending) & (~non_operating)

    out["订单分类"] = np.select(
        [non_operating, pending, invalid_by_order | invalid_by_aftersale, is_effective],
        ["非经营剔除", "待确认", "无效", "有效"],
        default="未分类",
    )
    return out


def _normalize_order_ids(orders: pd.DataFrame) -> pd.DataFrame:
    out = orders.copy()
    if "商品id" not in out.columns and "商品ID" in out.columns:
        out = out.rename(columns={"商品ID": "商品id"})
    out["商品id"] = out["商品id"].astype(str).str.strip()
    out["商品规格"] = out["商品规格"].fillna("").astype(str).str.strip()
    return out


def _prepare_link_mapping(link_map: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    lm = link_map.copy()
    lm["商品ID"] = lm["商品ID"].astype(str).str.strip()
    lm["商品规格"] = lm["商品规格"].fillna("").astype(str).str.strip()
    lm["销售规格ID"] = lm["销售规格ID"].astype(str).str.strip()

    # 用于从商品ID+商品规格反查销售规格ID
    by_goods_spec = (
        lm.groupby(["商品ID", "商品规格"], as_index=False)
        .agg(
            销售规格ID=("销售规格ID", "first"),
            匹配候选数=("销售规格ID", "nunique"),
        )
    )

    # 用于最终按 商品ID+销售规格ID 精确映射，先去重避免重复展开
    by_goods_sales = (
        lm.sort_values(["商品ID", "销售规格ID"])  # 稳定性
        .drop_duplicates(subset=["商品ID", "销售规格ID"], keep="first")
        .copy()
    )
    return by_goods_spec, by_goods_sales


def prepare_enriched_orders(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    orders = _normalize_order_ids(classify_orders(tables["orders"]))
    by_goods_spec, by_goods_sales = _prepare_link_mapping(tables["link_spec_mapping"])

    orders = orders.merge(
        by_goods_spec,
        left_on=["商品id", "商品规格"],
        right_on=["商品ID", "商品规格"],
        how="left",
    )

    existing_col = "销售规格ID" if "销售规格ID" in orders.columns else None
    mapped_col = "销售规格ID_y" if "销售规格ID_y" in orders.columns else "销售规格ID"

    if existing_col is not None:
        existing_spec = orders[existing_col].astype(str).replace({"nan": ""}).str.strip()
    else:
        existing_spec = pd.Series("", index=orders.index)

    mapped_spec = orders[mapped_col].astype(str).replace({"nan": ""}).str.strip()
    orders["订单销售规格ID"] = existing_spec.where(existing_spec != "", mapped_spec)

    orders = orders.merge(
        by_goods_sales,
        left_on=["商品id", "订单销售规格ID"],
        right_on=["商品ID", "销售规格ID"],
        how="left",
        suffixes=("", "_映射"),
    )

    sales_map = tables["sales_spec_mapping"].copy()
    sales_map["销售规格ID"] = sales_map["销售规格ID"].astype(str).str.strip()
    orders = orders.merge(
        sales_map[["销售规格ID", "标准产品ID", "产品总成本", "快递费"]],
        left_on="订单销售规格ID",
        right_on="销售规格ID",
        how="left",
        suffixes=("", "_销售"),
    )

    pm = tables["product_master"][["标准产品ID", "标准产品名称"]].drop_duplicates()
    orders = orders.merge(pm, on="标准产品ID", how="left")

    for col in ["用户实付金额(元)", "商家实收金额(元)", "产品总成本", "快递费"]:
        if col in orders.columns:
            orders[col] = pd.to_numeric(orders[col], errors="coerce").fillna(0)

    if "是否百补" in orders.columns:
        bb_flag = orders["是否百补"].fillna("").astype(str).str.strip()
        is_bb = bb_flag.eq("是")
    else:
        is_bb = pd.Series(False, index=orders.index)

    unresolved_bb = (~is_bb) & (orders["资源位类型"].fillna("").astype(str).apply(_is_bb))
    is_bb = is_bb | unresolved_bb

    orders["是否百补"] = np.where(is_bb, "是", "否")
    orders["平台扣点"] = np.where(
        is_bb,
        orders["商家实收金额(元)"] * CONFIG.business_rules.bb_platform_fee_rate,
        orders["用户实付金额(元)"] * CONFIG.business_rules.normal_platform_fee_rate,
    )
    orders["订单侧估算毛利"] = (
        orders["商家实收金额(元)"] - orders["产品总成本"] - orders["快递费"] - orders["平台扣点"]
    )

    duplicate_risk = by_goods_spec[by_goods_spec["匹配候选数"] > 1].copy()
    diagnostics = {
        "链接映射多候选风险": duplicate_risk,
    }
    return orders, diagnostics


def aggregate_promotion_by_product(promotion_df: pd.DataFrame) -> pd.DataFrame:
    out = promotion_df.copy()
    if "商品ID" not in out.columns:
        return pd.DataFrame(columns=["商品ID", "实际成交花费(元)"])

    out["实际成交花费(元)"] = pd.to_numeric(out["实际成交花费(元)"], errors="coerce").fillna(0)
    out["商品ID"] = out["商品ID"].astype(str).str.strip()
    invalid_ids = {"", "-", "nan", "none", "null"}
    out = out[~out["商品ID"].str.lower().isin(invalid_ids)]
    return out.groupby("商品ID", as_index=False)["实际成交花费(元)"].sum()


def calc_store_cash_spend(cashflow_df: pd.DataFrame) -> float:
    df = cashflow_df.copy()
    if "现金支出" in df.columns:
        return pd.to_numeric(df["现金支出"], errors="coerce").fillna(0).sum()

    if {"资金类型", "流水类型", "交易金额"}.issubset(df.columns):
        mask = (df["资金类型"].astype(str) == "现金") & (df["流水类型"].astype(str) == "支出")
        return pd.to_numeric(df.loc[mask, "交易金额"], errors="coerce").fillna(0).sum()

    if {"流水类型", "交易金额"}.issubset(df.columns):
        mask = df["流水类型"].astype(str) == "支出"
        return pd.to_numeric(df.loc[mask, "交易金额"], errors="coerce").fillna(0).sum()

    return 0.0


def calc_ratio_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["实际ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["实际成交花费(元)"]), axis=1)
    out["盈亏平衡ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["订单侧估算毛利"]), axis=1)
    out["订单无效率"] = out.apply(
        lambda r: safe_divide(r["无效订单数"], r["有效订单数"] + r["无效订单数"]), axis=1
    )
    return out
