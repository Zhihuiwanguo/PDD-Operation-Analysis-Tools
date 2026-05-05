"""经营口径计算。"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from app.config import CONFIG
from app.constants import PROMOTION_SPEND_COLUMN_ALIASES
from app.utils import safe_divide


def _is_bb(text: str) -> bool:
    text = "" if text is None else str(text)
    return any(k in text for k in CONFIG.business_rules.bb_keywords)


def classify_orders(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "订单状态" not in out.columns:
        out["订单状态"] = ""
    if "售后状态" not in out.columns:
        out["售后状态"] = ""
    if "商品" not in out.columns:
        out["商品"] = ""

    out["订单状态"] = out["订单状态"].fillna("").astype(str)
    out["售后状态"] = out["售后状态"].fillna("").astype(str)
    out["商品"] = out["商品"].fillna("").astype(str)

    invalid_by_order = out["订单状态"].isin(CONFIG.business_rules.invalid_order_statuses)
    invalid_by_aftersale = out["售后状态"].isin(CONFIG.business_rules.invalid_after_sale_statuses)
    pending = out["售后状态"].isin(CONFIG.business_rules.pending_after_sale_statuses)

    non_operating_pattern = "|".join(
        re.escape(x) for x in CONFIG.business_rules.non_operating_keywords if x
    )
    if non_operating_pattern:
        non_operating = out["商品"].str.contains(non_operating_pattern, na=False, regex=True)
    else:
        non_operating = pd.Series(False, index=out.index)

    effective_by_status = out["订单状态"].apply(
        lambda x: any(k in x for k in CONFIG.business_rules.effective_order_status_keywords)
    )
    is_effective = (
        effective_by_status
        & (~invalid_by_order)
        & (~invalid_by_aftersale)
        & (~pending)
        & (~non_operating)
    )

    out["订单分类"] = np.select(
        [non_operating, pending, invalid_by_order | invalid_by_aftersale, is_effective],
        ["非经营剔除", "待确认", "无效", "有效"],
        default="未分类",
    )
    return out


def prepare_enriched_orders(
    tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    required = ["orders", "link_spec_mapping", "sales_spec_mapping", "product_master"]
    missing = [k for k in required if k not in tables]
    if missing:
        raise KeyError(f"缺少必需数据表: {', '.join(missing)}")

    orders = classify_orders(tables["orders"]).copy()

    if "商品id" not in orders.columns and "商品ID" in orders.columns:
        orders = orders.rename(columns={"商品ID": "商品id"})
    if "商品id" not in orders.columns:
        orders["商品id"] = ""

    orders["商品id"] = orders["商品id"].fillna("").astype(str).str.strip()

    if "商品规格" not in orders.columns:
        orders["商品规格"] = ""
    orders["商品规格"] = orders["商品规格"].fillna("").astype(str).str.strip()

    link_map = tables["link_spec_mapping"].copy()
    if "商品ID" not in link_map.columns:
        link_map["商品ID"] = ""
    link_map["商品ID"] = link_map["商品ID"].fillna("").astype(str).str.strip()

    if "商品规格" not in link_map.columns:
        link_map["商品规格"] = ""
    link_map["商品规格"] = link_map["商品规格"].fillna("").astype(str).str.strip()

    if "销售规格ID" not in link_map.columns:
        link_map["销售规格ID"] = ""
    link_map["销售规格ID"] = link_map["销售规格ID"].fillna("").astype(str).str.strip()

    if "销售规格ID" not in orders.columns:
        orders["销售规格ID"] = ""
    orders["销售规格ID"] = orders["销售规格ID"].fillna("").astype(str).str.strip()

    # 先用 商品ID + 商品规格 反查销售规格ID
    spec_lookup = (
        link_map[["商品ID", "商品规格", "销售规格ID"]]
        .dropna(subset=["商品ID", "商品规格", "销售规格ID"])
        .drop_duplicates()
    )
    spec_lookup = spec_lookup[
        (spec_lookup["商品ID"] != "")
        & (spec_lookup["商品规格"] != "")
        & (spec_lookup["销售规格ID"] != "")
    ].copy()

    spec_candidate_count = (
        spec_lookup.groupby(["商品ID", "商品规格"], dropna=False)
        .size()
        .reset_index(name="匹配候选数")
    )

    orders = orders.merge(
        spec_candidate_count,
        left_on=["商品id", "商品规格"],
        right_on=["商品ID", "商品规格"],
        how="left",
    )
    orders["匹配候选数"] = pd.to_numeric(orders["匹配候选数"], errors="coerce").fillna(0)

    spec_lookup_unique = spec_lookup.drop_duplicates(subset=["商品ID", "商品规格"])
    orders = orders.merge(
        spec_lookup_unique.rename(columns={"销售规格ID": "销售规格ID_映射"}),
        left_on=["商品id", "商品规格"],
        right_on=["商品ID", "商品规格"],
        how="left",
        suffixes=("", "_spec"),
    )

    orders["销售规格ID"] = orders["销售规格ID"].replace("", np.nan)
    orders["销售规格ID"] = orders["销售规格ID"].fillna(orders.get("销售规格ID_映射"))
    orders["销售规格ID"] = orders["销售规格ID"].fillna("").astype(str).str.strip()

    drop_cols = [c for c in ["商品ID_spec", "销售规格ID_映射"] if c in orders.columns]
    if drop_cols:
        orders = orders.drop(columns=drop_cols, errors="ignore")

    # 再按 商品ID + 销售规格ID 精确映射链接信息
    link_map_candidate_count = (
        link_map.groupby(["商品ID", "销售规格ID"], dropna=False)
        .size()
        .reset_index(name="链接映射候选数")
    )

    orders = orders.merge(
        link_map_candidate_count,
        left_on=["商品id", "销售规格ID"],
        right_on=["商品ID", "销售规格ID"],
        how="left",
    )
    orders["链接映射候选数"] = pd.to_numeric(orders["链接映射候选数"], errors="coerce").fillna(0)

    link_map_unique = link_map.drop_duplicates(subset=["商品ID", "销售规格ID"]).copy()
    orders = orders.merge(
        link_map_unique,
        left_on=["商品id", "销售规格ID"],
        right_on=["商品ID", "销售规格ID"],
        how="left",
        suffixes=("", "_链接映射"),
    )

    sales_map = tables["sales_spec_mapping"].copy()
    if "销售规格ID" not in sales_map.columns:
        sales_map["销售规格ID"] = ""
    sales_map["销售规格ID"] = sales_map["销售规格ID"].fillna("").astype(str).str.strip()

    need_sales_cols = ["销售规格ID", "标准产品ID", "产品总成本", "快递费"]
    for col in need_sales_cols:
        if col not in sales_map.columns:
            sales_map[col] = np.nan if col in ["产品总成本", "快递费"] else ""

    orders = orders.merge(
        sales_map[need_sales_cols].drop_duplicates(subset=["销售规格ID"]),
        on="销售规格ID",
        how="left",
    )

    product_master = tables["product_master"].copy()
    if "标准产品ID" not in product_master.columns:
        product_master["标准产品ID"] = ""
    if "标准产品名称" not in product_master.columns:
        product_master["标准产品名称"] = ""

    pm = product_master[["标准产品ID", "标准产品名称"]].drop_duplicates()
    orders = orders.merge(pm, on="标准产品ID", how="left")

    for col in ["用户实付金额(元)", "商家实收金额(元)", "产品总成本", "快递费", "商品数量(件)"]:
        if col not in orders.columns:
            orders[col] = 0
        orders[col] = pd.to_numeric(orders[col], errors="coerce").fillna(0)

    # 百补识别：优先 是否百补，其次 资源位类型，最后默认非百补
    if "是否百补" in orders.columns:
        bb_flag = orders["是否百补"].fillna("").astype(str).str.strip()
        is_bb = bb_flag.eq("是")
    else:
        is_bb = pd.Series(False, index=orders.index)

    if "资源位类型" in orders.columns:
        resource_type = orders["资源位类型"].fillna("").astype(str).str.strip()
    else:
        resource_type = pd.Series("", index=orders.index, dtype="object")

    unresolved_bb = (~is_bb) & resource_type.apply(_is_bb)
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

    # 诊断信息
    duplicate_risk = orders.loc[orders["匹配候选数"] > 1, ["订单号", "商品id", "商品规格", "匹配候选数"]].drop_duplicates() \
        if "订单号" in orders.columns else pd.DataFrame(columns=["订单号", "商品id", "商品规格", "匹配候选数"])

    bb_missing_prompt = pd.DataFrame()
    if "是否百补" not in orders.columns and "资源位类型" not in orders.columns:
        bb_missing_prompt = pd.DataFrame(
            [{"提示": "未提供 是否百补/资源位类型，系统已默认按非百补处理"}]
        )

    diagnostics = {
        "链接映射多候选风险": duplicate_risk,
        "百补字段缺失提示": bb_missing_prompt,
    }

    return orders, diagnostics


def aggregate_promotion_by_product(promotion_df: pd.DataFrame) -> pd.DataFrame:
    if "商品ID" not in promotion_df.columns:
        return pd.DataFrame(columns=["商品ID", "实际成交花费(元)"])

    out = promotion_df.copy()
    out["商品ID"] = out["商品ID"].fillna("").astype(str).str.strip()
    out = out[~out["商品ID"].isin(["", "-", "nan", "None"])].copy()

    spend_col = next((col for col in PROMOTION_SPEND_COLUMN_ALIASES if col in out.columns), None)
    if spend_col is None:
        out["实际成交花费(元)"] = 0.0
    else:
        out["实际成交花费(元)"] = pd.to_numeric(out[spend_col], errors="coerce").fillna(0.0)

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
        lambda r: safe_divide(r["无效订单数"], r["有效订单数"] + r["无效订单数"]),
        axis=1,
    )
    return out
