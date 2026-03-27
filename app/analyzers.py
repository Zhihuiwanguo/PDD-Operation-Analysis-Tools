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
    business_alerts = _build_business_alerts(link_summary, product_summary, spec_summary)
    overview = _analyze_overview(orders, cash_spend)
    exceptions = _analyze_exceptions(tables, orders, promo_by_product, diagnostics)

    return {
        "orders_enriched": orders,
        "link_summary": link_summary,
        "product_summary": product_summary,
        "spec_summary": spec_summary,
        "baibu_vs_normal": baibu_vs_normal,
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
    if row["订单侧估算毛利"] < t.weaken_loss_threshold or row["无效率"] >= t.weaken_invalid_rate_threshold:
        return "弱化规格"
    if row["订单侧毛利率"] >= t.profit_margin_threshold and row["单均订单侧毛利"] >= t.profit_per_order_threshold:
        return "利润规格"
    if row["有效订单数"] >= t.main_push_orders_threshold and row["订单侧毛利率"] >= t.main_push_margin_threshold:
        return "主推规格"
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

    if "商品ID" not in link_map.columns:
        link_map["商品ID"] = ""
    if "销售规格ID" not in link_map.columns:
        link_map["销售规格ID"] = ""

    link_map["商品ID"] = link_map["商品ID"].fillna("").astype(str).str.strip()
    link_map["销售规格ID"] = link_map["销售规格ID"].fillna("").astype(str).str.strip()

    if "商品id" not in orders.columns:
        orders["商品id"] = ""
    if "销售规格ID" not in orders.columns:
        orders["销售规格ID"] = ""
    if "订单销售规格ID" not in orders.columns:
        orders["订单销售规格ID"] = orders["销售规格ID"]

    for col in ["订单号", "商品规格", "商品", "售后状态"]:
        if col not in orders.columns:
            orders[col] = ""

    orders["商品id"] = orders["商品id"].fillna("").astype(str).str.strip()
    orders["销售规格ID"] = orders["销售规格ID"].fillna("").astype(str).str.strip()
    orders["订单销售规格ID"] = orders["订单销售规格ID"].fillna("").astype(str).str.strip()

    # 未映射规格：按 商品ID + 订单销售规格ID 判断
    order_pairs = orders[["订单号", "商品id", "订单销售规格ID", "商品规格", "商品"]].copy()
    order_pairs = order_pairs.rename(
        columns={
            "商品id": "商品ID",
            "订单销售规格ID": "销售规格ID",
        }
    )

    mapped_pairs = link_map[["商品ID", "销售规格ID"]].drop_duplicates()
    unmapped_specs = order_pairs.merge(
        mapped_pairs,
        on=["商品ID", "销售规格ID"],
        how="left",
        indicator=True,
    )
    unmapped_specs = unmapped_specs[unmapped_specs["_merge"] == "left_only"].drop(columns=["_merge"])

    mapped_ids = set(link_map["商品ID"].tolist())
    order_ids = set(orders["商品id"].tolist())
    promo_ids = (
        set(promo_by_product["商品ID"].fillna("").astype(str).str.strip().tolist())
        if "商品ID" in promo_by_product.columns
        else set()
    )

    unmapped_goods = pd.DataFrame(
        sorted(x for x in (order_ids | promo_ids) - mapped_ids if x),
        columns=["商品ID"],
    )

    # 重复映射：只按 商品ID + 销售规格ID pair 判定
    link_map_for_dup = link_map.copy()

    if "商品ID" not in link_map_for_dup.columns:
        link_map_for_dup["商品ID"] = ""
    if "销售规格ID" not in link_map_for_dup.columns:
        link_map_for_dup["销售规格ID"] = ""

    link_map_for_dup["商品ID"] = (
        link_map_for_dup["商品ID"].fillna("").astype(str).str.strip()
    )
    link_map_for_dup["销售规格ID"] = (
        link_map_for_dup["销售规格ID"].fillna("").astype(str).str.strip()
    )

    link_map_for_dup = link_map_for_dup[
        (link_map_for_dup["商品ID"] != "") & (link_map_for_dup["销售规格ID"] != "")
    ].copy()

    duplicate_mapping = (
        link_map_for_dup.groupby(["商品ID", "销售规格ID"], dropna=False)
        .size()
        .reset_index(name="重复数")
        .query("重复数 > 1")
    )

    valid_orders = orders[orders["订单分类"] == "有效"].copy()

    order_with_promo = (
        valid_orders.groupby("商品id", as_index=False)
        .size()
        .rename(columns={"商品id": "商品ID", "size": "订单数"})
    )
    order_with_promo["商品ID"] = order_with_promo["商品ID"].fillna("").astype(str).str.strip()

    with_promo = order_with_promo.merge(promo_by_product, on="商品ID", how="left")
    if "实际成交花费(元)" not in with_promo.columns:
        with_promo["实际成交花费(元)"] = 0
    order_no_promo = with_promo[with_promo["实际成交花费(元)"].fillna(0) <= 0]

    promo_no_order = promo_by_product.copy()
    if "商品ID" in promo_no_order.columns:
        promo_no_order["商品ID"] = promo_no_order["商品ID"].fillna("").astype(str).str.strip()
        promo_no_order = promo_no_order[~promo_no_order["商品ID"].isin(order_with_promo["商品ID"])]

    promo_attach_issues = pd.DataFrame()
    if "商品ID" in promo_by_product.columns:
        promo_attach_issues = promo_by_product.copy()
        promo_attach_issues["商品ID"] = promo_attach_issues["商品ID"].fillna("").astype(str).str.strip()

        def _attach_reason(goods_id: str) -> str:
            if goods_id in ["", "-", "nan", "None"]:
                return "商品ID为空/非法（疑似汇总行）"
            if goods_id not in mapped_ids:
                return "未在映射表中"
            if goods_id not in order_ids:
                return "订单侧无该商品ID"
            return ""

        promo_attach_issues["挂接异常原因"] = promo_attach_issues["商品ID"].apply(_attach_reason)
        promo_attach_issues = promo_attach_issues[promo_attach_issues["挂接异常原因"] != ""]

    diff_price_items = orders[orders["订单分类"] == "非经营剔除"][["订单号", "商品id", "商品"]]
    pending_orders = orders[orders["订单分类"] == "待确认"][["订单号", "商品id", "售后状态", "商品"]]

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
