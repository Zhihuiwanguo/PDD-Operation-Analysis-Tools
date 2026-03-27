"""分析层：总览、链接、产品、规格与异常。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.calculators import (
    aggregate_promotion_by_product,
    calc_ratio_columns,
    calc_store_cash_spend,
    prepare_enriched_orders,
)
from app.config import CONFIG
from app.utils import safe_divide


def build_analysis_context(
    tables: dict[str, pd.DataFrame],
    filters: dict | None = None,
) -> dict[str, pd.DataFrame | dict[str, float]]:
    orders, diagnostics = prepare_enriched_orders(tables)
    orders = _apply_order_filters(orders, filters)

    promo_df = _apply_promotion_filters(tables["promotion"], filters)
    promo_by_product = aggregate_promotion_by_product(promo_df)

    if filters and filters.get("goods_ids"):
        allow_ids = set(map(str, filters["goods_ids"]))
        promo_by_product = promo_by_product[promo_by_product["商品ID"].astype(str).isin(allow_ids)]

    if filters and any(filters.get(k) for k in ["stores", "product_names", "goods_ids", "baibu"]):
        order_goods = set(orders["商品id"].astype(str).tolist())
        promo_by_product = promo_by_product[promo_by_product["商品ID"].astype(str).isin(order_goods)]

    cashflow_df = _apply_cashflow_filters(tables["cashflow"], filters)
    cash_spend = calc_store_cash_spend(cashflow_df)

    link_summary = _analyze_links(orders, promo_by_product)
    product_summary = _analyze_products(orders, promo_by_product)
    spec_summary = _analyze_specs(orders)
    baibu_vs_normal = _analyze_baibu_vs_normal(orders, promo_by_product)
    promotion_analysis = _analyze_promotion_module(promo_df, orders)
    business_alerts = _build_business_alerts(link_summary, product_summary, spec_summary)
    overview = _analyze_overview(orders, cash_spend)
    exceptions = _analyze_exceptions(tables, orders, promo_by_product, diagnostics)

    return {
        "orders_enriched": orders,
        "link_summary": link_summary,
        "product_summary": product_summary,
        "spec_summary": spec_summary,
        "baibu_vs_normal": baibu_vs_normal,
        "promotion_analysis": promotion_analysis,
        "business_alerts": business_alerts,
        "overview": overview,
        "exceptions": exceptions,
        "store_cash_spend": cash_spend,
        "date_field_used": "订单成交时间(为空回退支付时间)",
    }




def _apply_order_filters(orders: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    if not filters:
        return orders

    out = orders.copy()
    out["__筛选日期"] = pd.to_datetime(
        out["订单成交时间"].replace({"	": ""}),
        errors="coerce",
    )
    if "支付时间" in out.columns:
        pay_time = pd.to_datetime(out["支付时间"].replace({"	": ""}), errors="coerce")
        out["__筛选日期"] = out["__筛选日期"].fillna(pay_time)

    date_range = filters.get("date_range")
    if date_range and len(date_range) == 2 and all(date_range):
        start = pd.to_datetime(date_range[0])
        end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = out[(out["__筛选日期"] >= start) & (out["__筛选日期"] <= end)]

    if filters.get("stores") and "店铺名称" in out.columns:
        out = out[out["店铺名称"].astype(str).isin(filters["stores"])]

    if filters.get("product_names"):
        out = out[out["标准产品名称"].astype(str).isin(filters["product_names"])]

    if filters.get("goods_ids"):
        out = out[out["商品id"].astype(str).isin(list(map(str, filters["goods_ids"]))) ]

    if filters.get("baibu"):
        out = out[out["是否百补"].astype(str).isin(filters["baibu"])]

    return out.drop(columns=["__筛选日期"], errors="ignore")


def _apply_promotion_filters(promo_df: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    if not filters:
        return promo_df

    out = promo_df.copy()
    if filters.get("date_range") and "日期" in out.columns:
        date_range = filters["date_range"]
        if len(date_range) == 2 and all(date_range):
            ser = pd.to_datetime(out["日期"], errors="coerce")
            start = pd.to_datetime(date_range[0])
            end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            out = out[(ser >= start) & (ser <= end)]

    if filters.get("goods_ids") and "商品ID" in out.columns:
        out = out[out["商品ID"].astype(str).isin(list(map(str, filters["goods_ids"]))) ]
    return out


def _apply_cashflow_filters(cashflow_df: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    if not filters:
        return cashflow_df

    out = cashflow_df.copy()
    if filters.get("date_range") and "时间" in out.columns:
        date_range = filters["date_range"]
        if len(date_range) == 2 and all(date_range):
            ser = pd.to_datetime(out["时间"], errors="coerce")
            start = pd.to_datetime(date_range[0])
            end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            out = out[(ser >= start) & (ser <= end)]

    if filters.get("stores") and "店铺名称" in out.columns:
        out = out[out["店铺名称"].astype(str).isin(filters["stores"])]
    return out

def _analyze_overview(orders: pd.DataFrame, cash_spend: float) -> dict[str, float]:
    valid_orders = orders[orders["订单分类"] == "有效"]
    total_user_pay = valid_orders["用户实付金额(元)"].sum()
    total_merchant_income = valid_orders["商家实收金额(元)"].sum()
    gross_profit = valid_orders["订单侧估算毛利"].sum()

    return {
        "总订单数": int(len(orders)),
        "有效订单数": int((orders["订单分类"] == "有效").sum()),
        "无效订单数": int((orders["订单分类"] == "无效").sum()),
        "待确认订单数": int((orders["订单分类"] == "待确认").sum()),
        "非经营剔除订单数": int((orders["订单分类"] == "非经营剔除").sum()),
        "用户实付": float(total_user_pay),
        "商家实收": float(total_merchant_income),
        "订单侧估算毛利": float(gross_profit),
        "店铺总盘推广费（现金口径）": float(cash_spend),
        "店铺整体实际ROI": safe_divide(total_merchant_income, cash_spend),
        "店铺扣推广后贡献毛利": float(gross_profit - cash_spend),
        "盈亏平衡ROI": safe_divide(total_merchant_income, gross_profit),
    }


def _analyze_links(orders: pd.DataFrame, promo_by_product: pd.DataFrame) -> pd.DataFrame:
    link_title_col = "商品"
    group_cols = ["商品id", link_title_col, "标准产品名称", "是否百补"]

    counts = orders.groupby(group_cols, dropna=False).agg(
        有效订单数=("订单分类", lambda s: int((s == "有效").sum())),
        无效订单数=("订单分类", lambda s: int((s == "无效").sum())),
        待确认订单数=("订单分类", lambda s: int((s == "待确认").sum())),
        非经营剔除订单数=("订单分类", lambda s: int((s == "非经营剔除").sum())),
    ).reset_index()

    valid_orders = orders[orders["订单分类"] == "有效"]
    amounts = valid_orders.groupby(group_cols, dropna=False).agg(
        用户实付=("用户实付金额(元)", "sum"),
        商家实收=("商家实收金额(元)", "sum"),
        产品总成本=("产品总成本", "sum"),
        快递总成本=("快递费", "sum"),
        平台扣点=("平台扣点", "sum"),
        订单侧估算毛利=("订单侧估算毛利", "sum"),
    ).reset_index()

    base = counts.merge(amounts, on=group_cols, how="left")
    for col in ["用户实付", "商家实收", "产品总成本", "快递总成本", "平台扣点", "订单侧估算毛利"]:
        base[col] = base[col].fillna(0.0)

    base = base.rename(columns={"商品id": "商品ID", link_title_col: "链接标题"})
    base["商品ID"] = base["商品ID"].astype(str)

    result = base.merge(promo_by_product, on="商品ID", how="left")
    result["实际成交花费(元)"] = pd.to_numeric(result["实际成交花费(元)"], errors="coerce").fillna(0.0)
    result["扣推广后贡献毛利"] = result["订单侧估算毛利"] - result["实际成交花费(元)"]
    result = calc_ratio_columns(result)
    return result.sort_values("订单侧估算毛利", ascending=False)


def _build_product_promo(valid_orders: pd.DataFrame, promo_by_product: pd.DataFrame) -> pd.DataFrame:
    # 仅在商品ID->标准产品名称“可解释映射”下汇总推广费：每个商品ID取有效订单最多的产品作为归属。
    mapping = (
        valid_orders.groupby(["商品id", "标准产品名称"], dropna=False)
        .size()
        .reset_index(name="有效订单数")
        .sort_values(["商品id", "有效订单数"], ascending=[True, False])
        .drop_duplicates(subset=["商品id"], keep="first")
    )
    mapping["商品id"] = mapping["商品id"].astype(str)

    promo = promo_by_product.rename(columns={"商品ID": "商品id"}).copy()
    promo["商品id"] = promo["商品id"].astype(str)

    mapped = promo.merge(mapping[["商品id", "标准产品名称"]], on="商品id", how="left")
    mapped = mapped.dropna(subset=["标准产品名称"])
    return mapped.groupby("标准产品名称", as_index=False)["实际成交花费(元)"].sum()


def _product_tier(row: pd.Series) -> str:
    if row["有效订单数"] <= 0:
        return "C层"
    if (row["扣推广后贡献毛利"] > 0 and row["实际ROI"] >= 1.5) or row["商家实收"] >= 50000:
        return "A层"
    if row["扣推广后贡献毛利"] >= 0 or row["实际ROI"] >= 1.0:
        return "B层"
    return "C层"


def _analyze_products(orders: pd.DataFrame, promo_by_product: pd.DataFrame) -> pd.DataFrame:
    valid_orders = orders[orders["订单分类"] == "有效"].copy()

    counts = orders.groupby("标准产品名称", dropna=False).agg(
        有效订单数=("订单分类", lambda s: int((s == "有效").sum()),),
    ).reset_index()

    metrics = valid_orders.groupby("标准产品名称", dropna=False).agg(
        销售件数=("商品数量(件)", "sum"),
        用户实付=("用户实付金额(元)", "sum"),
        商家实收=("商家实收金额(元)", "sum"),
        产品总成本=("产品总成本", "sum"),
        快递总成本=("快递费", "sum"),
        平台扣点=("平台扣点", "sum"),
        订单侧估算毛利=("订单侧估算毛利", "sum"),
    ).reset_index()

    promo_by_product_name = _build_product_promo(valid_orders, promo_by_product)

    out = counts.merge(metrics, on="标准产品名称", how="left")
    out = out.merge(promo_by_product_name, on="标准产品名称", how="left")
    out = out.rename(columns={"实际成交花费(元)": "链接推广费合计"})

    for col in ["销售件数", "用户实付", "商家实收", "产品总成本", "快递总成本", "平台扣点", "订单侧估算毛利", "链接推广费合计"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["扣推广后贡献毛利"] = out["订单侧估算毛利"] - out["链接推广费合计"]
    out["实际ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["链接推广费合计"]), axis=1)
    out["盈亏平衡ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["订单侧估算毛利"]), axis=1)
    out["产品层级标签"] = out.apply(_product_tier, axis=1)

    return out.sort_values(["产品层级标签", "订单侧估算毛利"], ascending=[True, False])


def _spec_positioning(row: pd.Series) -> str:
    t = CONFIG.spec_thresholds

    low_scale = (row["有效订单数"] < t.weaken_low_orders_threshold) and (row["销售件数"] < t.weaken_low_sales_qty_threshold)
    weak_profit = row["订单侧估算毛利"] < t.weaken_loss_threshold
    if weak_profit or row["无效率"] >= t.weaken_invalid_rate_threshold or low_scale:
        return "弱化规格"

    has_scale = (row["有效订单数"] >= t.main_push_orders_threshold) or (row["销售件数"] >= t.main_push_sales_qty_threshold)
    has_profit_base = (row["订单侧毛利率"] >= t.main_push_margin_threshold) and (
        row["单均订单侧毛利"] >= t.main_push_avg_profit_threshold
    )
    if has_scale and has_profit_base:
        return "主推规格"

    high_volume_low_profit = (row["销售件数"] >= t.traffic_sales_qty_threshold) and (
        row["单均订单侧毛利"] <= t.traffic_avg_profit_upper
    )
    if high_volume_low_profit:
        return "引流规格"

    if (row["订单侧毛利率"] >= t.profit_margin_threshold) and (
        row["单均订单侧毛利"] >= t.profit_per_order_threshold
    ):
        return "利润规格"

    return "引流规格"


def _analyze_baibu_vs_normal(orders: pd.DataFrame, promo_by_product: pd.DataFrame) -> pd.DataFrame:
    valid_orders = orders[orders["订单分类"] == "有效"].copy()
    dims = valid_orders.groupby("是否百补", dropna=False).agg(
        有效订单数=("订单号", "count"),
        用户实付=("用户实付金额(元)", "sum"),
        商家实收=("商家实收金额(元)", "sum"),
        产品总成本=("产品总成本", "sum"),
        快递总成本=("快递费", "sum"),
        平台扣点=("平台扣点", "sum"),
        订单侧估算毛利=("订单侧估算毛利", "sum"),
    ).reset_index()

    # 推广费按商品ID聚合后，依据有效订单中商品ID的百补属性（多数口径）汇总。
    goods_bb = (
        valid_orders.groupby(["商品id", "是否百补"], dropna=False)
        .size()
        .reset_index(name="有效订单数")
        .sort_values(["商品id", "有效订单数"], ascending=[True, False])
        .drop_duplicates(subset=["商品id"], keep="first")
    )
    goods_bb["商品id"] = goods_bb["商品id"].astype(str)

    promo = promo_by_product.rename(columns={"商品ID": "商品id", "实际成交花费(元)": "推广费"}).copy()
    promo["商品id"] = promo["商品id"].astype(str)
    promo_bb = promo.merge(goods_bb[["商品id", "是否百补"]], on="商品id", how="left")
    promo_bb = promo_bb.dropna(subset=["是否百补"])
    promo_sum = promo_bb.groupby("是否百补", as_index=False)["推广费"].sum()

    out = dims.merge(promo_sum, on="是否百补", how="left")
    out["推广费"] = pd.to_numeric(out["推广费"], errors="coerce").fillna(0.0)
    out["扣推广后贡献毛利"] = out["订单侧估算毛利"] - out["推广费"]
    out["实际ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["推广费"]), axis=1)
    out["盈亏平衡ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["订单侧估算毛利"]), axis=1)
    return out.sort_values("是否百补")


def _analyze_specs(orders: pd.DataFrame) -> pd.DataFrame:
    valid_orders = orders[orders["订单分类"] == "有效"].copy()

    top_products = (
        valid_orders.groupby("标准产品名称", dropna=False)["商品数量(件)"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .index
    )

    scope_all = orders[orders["标准产品名称"].isin(top_products)].copy()
    scope_valid = valid_orders[valid_orders["标准产品名称"].isin(top_products)].copy()

    spec_col = "销售规格名称" if "销售规格名称" in scope_all.columns else "商品规格"
    group_cols = ["标准产品名称", spec_col]

    counts = scope_all.groupby(group_cols, dropna=False).agg(
        有效订单数=("订单分类", lambda s: int((s == "有效").sum())),
        无效订单数=("订单分类", lambda s: int((s == "无效").sum())),
    ).reset_index()

    metrics = scope_valid.groupby(group_cols, dropna=False).agg(
        销售件数=("商品数量(件)", "sum"),
        用户实付=("用户实付金额(元)", "sum"),
        商家实收=("商家实收金额(元)", "sum"),
        产品总成本=("产品总成本", "sum"),
        快递总成本=("快递费", "sum"),
        平台扣点=("平台扣点", "sum"),
        订单侧估算毛利=("订单侧估算毛利", "sum"),
    ).reset_index()

    out = counts.merge(metrics, on=group_cols, how="left")
    out = out.rename(columns={spec_col: "销售规格名称"})
    for col in ["销售件数", "用户实付", "商家实收", "产品总成本", "快递总成本", "平台扣点", "订单侧估算毛利"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["单均实收"] = out.apply(lambda r: safe_divide(r["商家实收"], r["有效订单数"]), axis=1)
    out["单均订单侧毛利"] = out.apply(lambda r: safe_divide(r["订单侧估算毛利"], r["有效订单数"]), axis=1)
    out["订单侧毛利率"] = out.apply(lambda r: safe_divide(r["订单侧估算毛利"], r["商家实收"]), axis=1)
    out["无效率"] = out.apply(lambda r: safe_divide(r["无效订单数"], r["有效订单数"] + r["无效订单数"]), axis=1)
    out["规格定位建议"] = out.apply(_spec_positioning, axis=1)

    return out.sort_values(["标准产品名称", "销售件数"], ascending=[True, False])


def _pick_first(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _normalize_promotion_detail(promo_df: pd.DataFrame) -> pd.DataFrame:
    if promo_df.empty:
        return pd.DataFrame(columns=["日期", "商品ID", "推广费", "推广成交金额", "实际ROI", "曝光", "点击", "成交订单数", "CTR", "转化率"])

    df = promo_df.copy()
    date_col = _pick_first(df, ["日期"])
    goods_col = _pick_first(df, ["商品ID", "商品id"])
    spend_col = _pick_first(df, ["实际成交花费(元)"])
    roi_col = _pick_first(df, ["实际ROI", "实际投产比"])
    amount_col = _pick_first(df, ["推广成交金额", "成交金额(元)", "交易额(元)"])
    expo_col = _pick_first(df, ["曝光", "曝光量"])
    click_col = _pick_first(df, ["点击", "点击量"])
    order_col = _pick_first(df, ["成交订单数", "成交笔数"])

    out = pd.DataFrame()
    out["日期"] = pd.to_datetime(df[date_col], errors="coerce") if date_col else pd.NaT
    out["商品ID"] = df[goods_col].astype(str).str.strip() if goods_col else ""
    out["推广费"] = pd.to_numeric(df[spend_col], errors="coerce").fillna(0) if spend_col else 0

    if amount_col:
        out["推广成交金额"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
    elif roi_col:
        out["推广成交金额"] = pd.to_numeric(df[roi_col], errors="coerce").fillna(0) * out["推广费"]
    else:
        out["推广成交金额"] = 0.0

    if roi_col:
        out["实际ROI"] = pd.to_numeric(df[roi_col], errors="coerce").fillna(0)
    else:
        out["实际ROI"] = out.apply(lambda r: safe_divide(r["推广成交金额"], r["推广费"]), axis=1)

    out["曝光"] = pd.to_numeric(df[expo_col], errors="coerce").fillna(0) if expo_col else 0
    out["点击"] = pd.to_numeric(df[click_col], errors="coerce").fillna(0) if click_col else 0
    out["成交订单数"] = pd.to_numeric(df[order_col], errors="coerce").fillna(0) if order_col else 0
    out["CTR"] = out.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    out["转化率"] = out.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)
    out = out.dropna(subset=["日期"])
    return out


def _analyze_promotion_module(promo_df: pd.DataFrame, orders: pd.DataFrame) -> dict[str, pd.DataFrame]:
    detail = _normalize_promotion_detail(promo_df)
    if detail.empty:
        empty = pd.DataFrame()
        return {
            "daily": empty,
            "goods": empty,
            "detail": empty,
            "anomalies": {
                "推广费高但ROI低": empty,
                "推广费高但成交增长不足": empty,
                "ROI连续下滑": empty,
                "放量但效率恶化": empty,
            },
        }

    daily = detail.groupby("日期", as_index=False).agg(
        推广费=("推广费", "sum"),
        推广成交金额=("推广成交金额", "sum"),
        推广商品ID数=("商品ID", "nunique"),
        曝光=("曝光", "sum"),
        点击=("点击", "sum"),
        成交订单数=("成交订单数", "sum"),
    )
    daily["每日推广ROI"] = daily.apply(lambda r: safe_divide(r["推广成交金额"], r["推广费"]), axis=1)
    daily["CTR"] = daily.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    daily["转化率"] = daily.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)

    goods = detail.groupby("商品ID", as_index=False).agg(
        推广费=("推广费", "sum"),
        推广成交金额=("推广成交金额", "sum"),
        曝光=("曝光", "sum"),
        点击=("点击", "sum"),
        成交订单数=("成交订单数", "sum"),
        活跃天数=("日期", "nunique"),
    )
    goods["实际ROI"] = goods.apply(lambda r: safe_divide(r["推广成交金额"], r["推广费"]), axis=1)
    goods["CTR"] = goods.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    goods["转化率"] = goods.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)
    total_spend = goods["推广费"].sum()
    goods["花费占比"] = goods["推广费"].apply(lambda x: safe_divide(x, total_spend))
    goods["花费排名"] = goods["推广费"].rank(ascending=False, method="dense").astype(int)
    goods["ROI排名"] = goods["实际ROI"].rank(ascending=False, method="dense").astype(int)
    goods["日均推广费"] = goods.apply(lambda r: safe_divide(r["推广费"], r["活跃天数"]), axis=1)
    goods["日均推广成交金额"] = goods.apply(lambda r: safe_divide(r["推广成交金额"], r["活跃天数"]), axis=1)

    # 关联链接标题
    title_map = (
        orders.groupby("商品id")["商品"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0]).reset_index()
    )
    title_map["商品id"] = title_map["商品id"].astype(str)
    goods = goods.merge(title_map.rename(columns={"商品id": "商品ID", "商品": "链接标题"}), on="商品ID", how="left")

    detail = detail.sort_values(["商品ID", "日期"])

    # 异常识别
    spend_q = goods["推广费"].quantile(0.75) if len(goods) else 0
    roi_q = goods["实际ROI"].quantile(0.25) if len(goods) else 0
    a1 = goods[(goods["推广费"] >= spend_q) & (goods["实际ROI"] <= roi_q)]

    growth_records = []
    down_records = []
    scale_bad_records = []
    for gid, g in detail.groupby("商品ID"):
        g = g.sort_values("日期")
        if len(g) >= 4:
            first = g.head(max(2, len(g)//3))["推广成交金额"].mean()
            last = g.tail(max(2, len(g)//3))["推广成交金额"].mean()
            growth = safe_divide(last - first, first)
            spend_mean = g["推广费"].mean()
            growth_records.append({"商品ID": gid, "成交金额增长率": growth, "平均推广费": spend_mean})

        if len(g) >= 3:
            tail = g.tail(3)["实际ROI"].tolist()
            if tail[0] > tail[1] > tail[2]:
                down_records.append({"商品ID": gid, "最近3日ROI": tail})

        if len(g) >= 14:
            prev = g.iloc[-14:-7]
            recent = g.iloc[-7:]
            prev_spend, recent_spend = prev["推广费"].mean(), recent["推广费"].mean()
            prev_roi, recent_roi = prev["实际ROI"].mean(), recent["实际ROI"].mean()
            if recent_spend > prev_spend * 1.3 and recent_roi < prev_roi * 0.9:
                scale_bad_records.append({"商品ID": gid, "近7日平均推广费": recent_spend, "近7日平均ROI": recent_roi})

    growth_df = pd.DataFrame(growth_records)
    if growth_df.empty:
        a2 = growth_df
    else:
        merged = goods[["商品ID", "推广费"]].merge(growth_df, on="商品ID", how="left")
        a2 = merged[(merged["推广费"] >= spend_q) & (merged["成交金额增长率"].fillna(0) < 0.05)]

    a3 = pd.DataFrame(down_records)
    a4 = pd.DataFrame(scale_bad_records)

    return {
        "daily": daily.sort_values("日期"),
        "goods": goods.sort_values("推广费", ascending=False),
        "detail": detail,
        "anomalies": {
            "推广费高但ROI低": a1,
            "推广费高但成交增长不足": a2,
            "ROI连续下滑": a3,
            "放量但效率恶化": a4,
        },
    }



def _build_business_alerts(
    link_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    spec_summary: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    t = CONFIG.alert_thresholds

    loss_links = link_summary[
        link_summary["扣推广后贡献毛利"] < t.loss_link_contribution_threshold
    ].copy()

    low_roi_links = link_summary[
        link_summary["实际ROI"] < link_summary["盈亏平衡ROI"]
    ].copy()

    high_invalid_specs = spec_summary[
        spec_summary["无效率"] > t.spec_high_invalid_rate_threshold
    ].copy()

    high_profit_low_sales_specs = spec_summary[
        (spec_summary["订单侧毛利率"] >= t.spec_high_profit_margin_threshold)
        & (
            (spec_summary["销售件数"] < t.spec_low_sales_qty_threshold)
            | (spec_summary["有效订单数"] < t.spec_low_valid_orders_threshold)
        )
    ].copy()

    profit_not_scaled_products = product_summary[
        (product_summary["扣推广后贡献毛利"] > t.product_profit_positive_threshold)
        & (product_summary["商家实收"] < t.product_unscaled_revenue_threshold)
    ].copy()

    return {
        "亏损链接清单": loss_links,
        "低ROI链接清单": low_roi_links,
        "高无效率规格清单": high_invalid_specs,
        "高利润低销量规格清单": high_profit_low_sales_specs,
        "有利润但未放量产品清单": profit_not_scaled_products,
    }



def _analyze_exceptions(
    tables: dict[str, pd.DataFrame],
    orders: pd.DataFrame,
    promo_by_product: pd.DataFrame,
    diagnostics: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    link_map = tables["link_spec_mapping"].copy()
    link_map["商品ID"] = link_map["商品ID"].astype(str).str.strip()
    link_map["销售规格ID"] = link_map["销售规格ID"].astype(str).str.strip()

    # 未映射规格：订单 商品ID + 订单销售规格ID 在映射表中不存在
    mapped_pairs = set(zip(link_map["商品ID"], link_map["销售规格ID"]))
    order_pairs = orders[["订单号", "商品id", "订单销售规格ID", "商品规格", "商品"]].copy()
    order_pairs["订单销售规格ID"] = order_pairs["订单销售规格ID"].fillna("").astype(str).str.strip()
    order_pairs["pair_found"] = order_pairs.apply(
        lambda r: (str(r["商品id"]).strip(), str(r["订单销售规格ID"]).strip()) in mapped_pairs,
        axis=1,
    )
    unmapped_specs = order_pairs[(~order_pairs["pair_found"]) | (order_pairs["订单销售规格ID"] == "")].drop(
        columns=["pair_found"]
    )

    order_ids = set(orders["商品id"].astype(str).str.strip().tolist())
    promo_ids = set(promo_by_product["商品ID"].astype(str).str.strip().tolist())
    mapped_ids = set(link_map["商品ID"].astype(str).str.strip().tolist())
    unmapped_goods = pd.DataFrame(sorted((order_ids | promo_ids) - mapped_ids), columns=["商品ID"])

    # 重复映射判定口径：仅当“同一商品ID + 同一销售规格ID”出现多条时才算重复。
    duplicate_mapping = pd.DataFrame(columns=["商品ID", "销售规格ID", "重复数"])
    if {"商品ID", "销售规格ID"}.issubset(link_map.columns):
        pair_df = link_map[["商品ID", "销售规格ID"]].copy()
        pair_df["商品ID"] = pair_df["商品ID"].fillna("").astype(str).str.strip()
        pair_df["销售规格ID"] = pair_df["销售规格ID"].fillna("").astype(str).str.strip()
        pair_df = pair_df[(pair_df["商品ID"] != "") & (pair_df["销售规格ID"] != "")]
        duplicate_mapping = (
            pair_df.groupby(["商品ID", "销售规格ID"]).size().reset_index(name="重复数").query("重复数 > 1")
        )

    # 基于有效订单判断“有订单无推广费”
    effective_orders = orders[orders["订单分类"] == "有效"]
    effective_by_id = (
        effective_orders.groupby("商品id", as_index=False).size().rename(columns={"商品id": "商品ID", "size": "有效订单数"})
    )
    with_promo = effective_by_id.merge(promo_by_product, on="商品ID", how="left")
    with_promo["实际成交花费(元)"] = pd.to_numeric(with_promo["实际成交花费(元)"], errors="coerce").fillna(0)
    order_no_promo = with_promo[with_promo["实际成交花费(元)"] <= 0]

    promo_no_order = promo_by_product[~promo_by_product["商品ID"].isin(effective_by_id["商品ID"])]

    promo_raw = tables["promotion"].copy()
    if "商品ID" in promo_raw.columns:
        promo_raw["商品ID"] = promo_raw["商品ID"].astype(str).str.strip()
        promo_raw["实际成交花费(元)"] = pd.to_numeric(promo_raw.get("实际成交花费(元)"), errors="coerce").fillna(0)
        bad_id_mask = promo_raw["商品ID"].str.lower().isin({"", "-", "nan", "none", "null"})
        invalid_id_rows = promo_raw.loc[bad_id_mask, ["商品ID", "实际成交花费(元)"]].copy()
        if not invalid_id_rows.empty:
            invalid_id_rows["原因"] = "商品ID为空/非法（疑似汇总行）"
    else:
        invalid_id_rows = pd.DataFrame(columns=["商品ID", "实际成交花费(元)", "原因"])

    promo_attach_issues = promo_by_product.copy()
    promo_attach_issues["原因"] = ""
    promo_attach_issues.loc[~promo_attach_issues["商品ID"].isin(mapped_ids), "原因"] = "商品ID未在链接映射表中"
    promo_attach_issues.loc[
        promo_attach_issues["原因"].eq("") & ~promo_attach_issues["商品ID"].isin(order_ids), "原因"
    ] = "有推广费但订单侧无该商品ID"
    promo_attach_issues = pd.concat(
        [promo_attach_issues[promo_attach_issues["原因"] != ""], invalid_id_rows],
        ignore_index=True,
    )

    diff_price_items = orders[orders["订单分类"] == "非经营剔除"]["订单号 商品id 商品".split()]
    pending_orders = orders[orders["订单分类"] == "待确认"]["订单号 商品id 售后状态 商品".split()]

    return {
        "未映射规格": unmapped_specs,
        "未映射商品ID": unmapped_goods,
        "重复映射": duplicate_mapping,
        "有订单无推广费": order_no_promo,
        "有推广费无订单": promo_no_order,
        "推广费挂接异常": promo_attach_issues,
        "链接映射多候选风险": diagnostics.get("链接映射多候选风险", pd.DataFrame()),
        "百补字段缺失提示": diagnostics.get("百补字段缺失提示", pd.DataFrame()),
        "差价补款商品": diff_price_items,
        "待确认订单": pending_orders,
    }
