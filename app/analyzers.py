"""分析层：总览、链接、产品、规格、推广、素材与异常。"""

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
        promo_by_product = promo_by_product[
            promo_by_product["商品ID"].astype(str).isin(allow_ids)
        ]

    if filters and any(filters.get(k) for k in ["stores", "product_names", "goods_ids", "baibu"]):
        order_goods = set(orders["商品id"].astype(str).tolist())
        promo_by_product = promo_by_product[
            promo_by_product["商品ID"].astype(str).isin(order_goods)
        ]

    creative_material_df = tables.get("creative_material", pd.DataFrame())
    creative_material_analysis = _analyze_creative_material(creative_material_df, promo_df, filters)

    cashflow_df = _apply_cashflow_filters(tables["cashflow"], filters)
    cash_spend = calc_store_cash_spend(cashflow_df)

    link_summary = _analyze_links(orders, promo_by_product)
    product_summary = _analyze_products(orders, promo_by_product)
    spec_summary = _analyze_specs(orders)
    baibu_vs_normal = _analyze_baibu_vs_normal(orders, promo_by_product)
    promotion_analysis = _analyze_promotion(promo_df)
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
        "creative_material_analysis": creative_material_analysis,
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

    if "订单成交时间" not in out.columns:
        out["订单成交时间"] = ""
    out["__筛选日期"] = pd.to_datetime(
        out["订单成交时间"].replace({"\\t": ""}),
        errors="coerce",
    )

    if "支付时间" in out.columns:
        pay_time = pd.to_datetime(out["支付时间"].replace({"\\t": ""}), errors="coerce")
        out["__筛选日期"] = out["__筛选日期"].fillna(pay_time)

    date_range = filters.get("date_range")
    if date_range and len(date_range) == 2 and all(date_range):
        start = pd.to_datetime(date_range[0])
        end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        out = out[(out["__筛选日期"] >= start) & (out["__筛选日期"] <= end)]

    if filters.get("stores") and "店铺名称" in out.columns:
        out = out[out["店铺名称"].astype(str).isin(filters["stores"])]

    if filters.get("product_names") and "标准产品名称" in out.columns:
        out = out[out["标准产品名称"].astype(str).isin(filters["product_names"])]

    if filters.get("goods_ids") and "商品id" in out.columns:
        out = out[out["商品id"].astype(str).isin(list(map(str, filters["goods_ids"])))]

    if filters.get("baibu") and "是否百补" in out.columns:
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
        out = out[out["商品ID"].astype(str).isin(list(map(str, filters["goods_ids"])))]

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


def _build_overview_daily_trend(valid_orders: pd.DataFrame) -> pd.DataFrame:
    if valid_orders.empty:
        return pd.DataFrame(columns=["日期", "商家实收", "客户实付"])

    out = valid_orders.copy()

    if "订单成交时间" not in out.columns:
        out["订单成交时间"] = ""

    out["日期"] = pd.to_datetime(
        out["订单成交时间"].replace({"\\t": ""}),
        errors="coerce",
    )

    if "支付时间" in out.columns:
        pay_time = pd.to_datetime(out["支付时间"].replace({"\\t": ""}), errors="coerce")
        out["日期"] = out["日期"].fillna(pay_time)

    out["日期"] = out["日期"].dt.normalize()
    out = out.dropna(subset=["日期"])

    if out.empty:
        return pd.DataFrame(columns=["日期", "商家实收", "客户实付"])

    daily = (
        out.groupby("日期", dropna=False)
        .agg(
            商家实收=("商家实收金额(元)", "sum"),
            客户实付=("用户实付金额(元)", "sum"),
        )
        .reset_index()
        .sort_values("日期")
    )
    return daily


def _analyze_overview(orders: pd.DataFrame, cash_spend: float) -> dict:
    valid_orders = orders[orders["订单分类"] == "有效"].copy()
    total_user_pay = valid_orders["用户实付金额(元)"].sum()
    total_merchant_income = valid_orders["商家实收金额(元)"].sum()
    gross_profit = valid_orders["订单侧估算毛利"].sum()
    valid_order_count = int((orders["订单分类"] == "有效").sum())
    daily_trend = _build_overview_daily_trend(valid_orders)

    metrics = {
        "总订单数": int(len(orders)),
        "有效订单数": valid_order_count,
        "无效订单数": int((orders["订单分类"] == "无效").sum()),
        "待确认订单数": int((orders["订单分类"] == "待确认").sum()),
        "非经营剔除订单数": int((orders["订单分类"] == "非经营剔除").sum()),
        "用户实付": float(total_user_pay),
        "商家实收": float(total_merchant_income),
        "客单价": float(safe_divide(total_merchant_income, valid_order_count)),
        "订单侧估算毛利": float(gross_profit),
        "店铺总盘推广费（现金口径）": float(cash_spend),
        "店铺整体实际ROI": safe_divide(total_merchant_income, cash_spend),
        "店铺扣推广后贡献毛利": float(gross_profit - cash_spend),
        "盈亏平衡ROI": safe_divide(total_merchant_income, gross_profit),
    }

    return {
        "metrics": metrics,
        "daily_trend": daily_trend,
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
        有效订单数=("订单分类", lambda s: int((s == "有效").sum())),
        无效订单数=("订单分类", lambda s: int((s == "无效").sum())),
        待确认订单数=("订单分类", lambda s: int((s == "待确认").sum())),
        非经营剔除订单数=("订单分类", lambda s: int((s == "非经营剔除").sum())),
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

    baibu_metrics = (
        valid_orders.groupby(["标准产品名称", "是否百补"], dropna=False)
        .agg(
            商家实收=("商家实收金额(元)", "sum"),
            有效订单数=("订单号", "count"),
        )
        .reset_index()
    )

    if baibu_metrics.empty:
        baibu_pivot = pd.DataFrame(
            columns=["标准产品名称", "百补商家实收", "日常商家实收", "百补有效订单数", "日常有效订单数"]
        )
    else:
        revenue_pivot = (
            baibu_metrics.pivot_table(
                index="标准产品名称",
                columns="是否百补",
                values="商家实收",
                aggfunc="sum",
                fill_value=0.0,
            )
            .reset_index()
        )
        order_pivot = (
            baibu_metrics.pivot_table(
                index="标准产品名称",
                columns="是否百补",
                values="有效订单数",
                aggfunc="sum",
                fill_value=0.0,
            )
            .reset_index()
        )

        def _rename_bb_cols(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
            rename_map = {}
            for col in df.columns:
                if col == "标准产品名称":
                    continue
                col_str = str(col).strip()
                if col_str in ["是", "百补", "1", "True", "true"]:
                    rename_map[col] = f"百补{suffix}"
                else:
                    rename_map[col] = f"日常{suffix}"
            return df.rename(columns=rename_map)

        revenue_pivot = _rename_bb_cols(revenue_pivot, "商家实收")
        order_pivot = _rename_bb_cols(order_pivot, "有效订单数")

        baibu_pivot = revenue_pivot.merge(order_pivot, on="标准产品名称", how="outer")

    promo_by_product_name = _build_product_promo(valid_orders, promo_by_product)

    out = counts.merge(metrics, on="标准产品名称", how="left")
    out = out.merge(promo_by_product_name, on="标准产品名称", how="left")
    out = out.merge(baibu_pivot, on="标准产品名称", how="left")
    out = out.rename(columns={"实际成交花费(元)": "链接推广费合计"})

    for col in [
        "销售件数",
        "用户实付",
        "商家实收",
        "产品总成本",
        "快递总成本",
        "平台扣点",
        "订单侧估算毛利",
        "链接推广费合计",
        "百补商家实收",
        "日常商家实收",
        "百补有效订单数",
        "日常有效订单数",
    ]:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    out["扣推广后贡献毛利"] = out["订单侧估算毛利"] - out["链接推广费合计"]
    out["实际ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["链接推广费合计"]), axis=1)
    out["盈亏平衡ROI"] = out.apply(lambda r: safe_divide(r["商家实收"], r["订单侧估算毛利"]), axis=1)

    out["单均商家实收"] = out.apply(lambda r: safe_divide(r["商家实收"], r["有效订单数"]), axis=1)
    out["单均订单侧毛利"] = out.apply(lambda r: safe_divide(r["订单侧估算毛利"], r["有效订单数"]), axis=1)
    out["订单侧毛利率"] = out.apply(lambda r: safe_divide(r["订单侧估算毛利"], r["商家实收"]), axis=1)
    out["扣推广后毛利率"] = out.apply(lambda r: safe_divide(r["扣推广后贡献毛利"], r["商家实收"]), axis=1)
    out["推广费率"] = out.apply(lambda r: safe_divide(r["链接推广费合计"], r["商家实收"]), axis=1)
    out["百补销售占比"] = out.apply(lambda r: safe_divide(r["百补商家实收"], r["商家实收"]), axis=1)
    out["日常销售占比"] = out.apply(lambda r: safe_divide(r["日常商家实收"], r["商家实收"]), axis=1)

    out["产品层级标签"] = out.apply(_product_tier, axis=1)

    return out.sort_values(
        ["产品层级标签", "商家实收", "扣推广后贡献毛利"],
        ascending=[True, False, False],
    )


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

    link_map_for_dup = link_map.copy()
    link_map_for_dup["商品ID"] = link_map_for_dup["商品ID"].fillna("").astype(str).str.strip()
    link_map_for_dup["销售规格ID"] = link_map_for_dup["销售规格ID"].fillna("").astype(str).str.strip()

    if "商品规格" not in link_map_for_dup.columns:
        link_map_for_dup["商品规格"] = ""

    link_map_for_dup["商品规格"] = (
        link_map_for_dup["商品规格"].fillna("").astype(str).str.strip()
    )

    link_map_for_dup = link_map_for_dup[
        (link_map_for_dup["商品ID"] != "")
        & (link_map_for_dup["商品规格"] != "")
        & (link_map_for_dup["销售规格ID"] != "")
    ].copy()

    duplicate_mapping = (
        link_map_for_dup.groupby(["商品ID", "商品规格", "销售规格ID"], dropna=False)
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


def _pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _normalize_goods_id_value(value) -> str:
    """
    统一商品ID格式，解决 Excel 导入后出现 1234567890.0 导致挂接失败的问题。
    """
    if pd.isna(value):
        return ""

    s = str(value).strip()
    if s in {"", "nan", "None", "null", "-"}:
        return ""

    if s.endswith(".0"):
        prefix = s[:-2]
        if prefix.isdigit():
            return prefix

    try:
        f = float(s)
        if pd.notna(f) and f.is_integer():
            return str(int(f))
    except Exception:
        pass

    return s


def _normalize_goods_id_series(series: pd.Series) -> pd.Series:
    return series.apply(_normalize_goods_id_value)


def _prepare_promotion_base(promo_df: pd.DataFrame) -> pd.DataFrame:
    out = promo_df.copy()

    if "商品ID" not in out.columns:
        out["商品ID"] = ""
    out["商品ID"] = _normalize_goods_id_series(out["商品ID"])

    date_col = _pick_first_existing(out, ["日期", "统计日期", "统计日期文本", "时间"])
    if date_col is None:
        out["日期"] = pd.NaT
    else:
        out["日期"] = pd.to_datetime(out[date_col], errors="coerce")

    spend_col = _pick_first_existing(out, ["实际成交花费", "实际成交花费(元)"])
    if spend_col is None:
        out["实际成交花费"] = 0.0
    else:
        out["实际成交花费"] = _safe_numeric(out[spend_col])

    settle_amt_col = _pick_first_existing(out, ["结算金额", "结算金额(元)"])
    if settle_amt_col is None:
        out["结算金额"] = 0.0
    else:
        out["结算金额"] = _safe_numeric(out[settle_amt_col])

    settle_roi_col = _pick_first_existing(out, ["结算投产比"])
    if settle_roi_col is None:
        out["结算投产比"] = 0.0
    else:
        out["结算投产比"] = _safe_numeric(out[settle_roi_col])

    imp_col = _pick_first_existing(out, ["曝光量", "曝光", "展现量"])
    clk_col = _pick_first_existing(out, ["点击量", "点击"])
    ord_col = _pick_first_existing(out, ["成交订单数", "订单数", "成交笔数"])
    net_amt_col = _pick_first_existing(out, ["净交易额(元)", "净交易额"])

    out["曝光"] = _safe_numeric(out[imp_col]) if imp_col else 0.0
    out["点击"] = _safe_numeric(out[clk_col]) if clk_col else 0.0
    out["成交订单数"] = _safe_numeric(out[ord_col]) if ord_col else 0.0
    out["净交易额"] = _safe_numeric(out[net_amt_col]) if net_amt_col else 0.0

    out["CTR"] = out.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    out["转化率"] = out.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)

    title_col = _pick_first_existing(out, ["链接标题", "商品", "商品名称", "计划名称"])
    if title_col is None:
        out["链接标题"] = ""
    else:
        out["链接标题"] = out[title_col].fillna("").astype(str)

    return out


def _prepare_creative_material_base(material_df: pd.DataFrame) -> pd.DataFrame:
    if material_df is None or material_df.empty:
        return pd.DataFrame()

    out = material_df.copy()

    text_cols = [
        "店铺名称",
        "商品ID",
        "链接标题",
        "素材编号",
        "素材名称",
        "素材类型大类",
        "素材类型小类",
        "图片类型",
        "审核状态",
        "是否启用",
        "数据口径",
        "统计日期文本",
        "备注",
    ]
    for col in text_cols:
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str).str.strip()

    out["商品ID"] = _normalize_goods_id_series(out["商品ID"])

    if "统计日期" not in out.columns:
        out["统计日期"] = pd.NaT
    else:
        out["统计日期"] = pd.to_datetime(out["统计日期"], errors="coerce")

    if "开始日期" not in out.columns:
        out["开始日期"] = pd.NaT
    else:
        out["开始日期"] = pd.to_datetime(out["开始日期"], errors="coerce")

    if "结束日期" not in out.columns:
        out["结束日期"] = pd.NaT
    else:
        out["结束日期"] = pd.to_datetime(out["结束日期"], errors="coerce")

    out["开始日期"] = out["开始日期"].fillna(out["统计日期"])
    out["结束日期"] = out["结束日期"].fillna(out["统计日期"])
    out["结束日期"] = out["结束日期"].fillna(out["开始日期"])

    out["开始日期"] = pd.to_datetime(out["开始日期"], errors="coerce").dt.normalize()
    out["结束日期"] = (
        pd.to_datetime(out["结束日期"], errors="coerce").dt.normalize()
        + pd.Timedelta(days=1)
        - pd.Timedelta(seconds=1)
    )

    numeric_cols = [
        "统计天数",
        "交易额(元)",
        "成交笔数",
        "每笔成交金额(元)",
        "曝光量",
        "点击量",
        "点击率",
        "净成交笔数",
        "每笔净成交金额(元)",
        "净交易额占比",
        "净成交笔数占比",
        "净交易额(元)",
        "点击转化率",
    ]
    for col in numeric_cols:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    if "点击率" not in out.columns or (out["点击率"] == 0).all():
        out["点击率"] = out.apply(lambda r: safe_divide(r["点击量"], r["曝光量"]), axis=1)

    if "点击转化率" not in out.columns or (out["点击转化率"] == 0).all():
        out["点击转化率"] = out.apply(lambda r: safe_divide(r["成交笔数"], r["点击量"]), axis=1)

    return out


def _apply_creative_material_filters(material_df: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    """
    推广素材分析第一版先不跟随订单侧全局日期 / 店铺筛选，
    避免因为订单表口径不完整（如缺店铺名称、日期范围不同）把素材数据误筛空。

    当前仅保留商品ID筛选。
    后续如需要，再给素材分析模块单独做自己的筛选器。
    """
    if material_df is None or material_df.empty:
        return pd.DataFrame()

    if not filters:
        return material_df

    out = material_df.copy()

    if filters.get("goods_ids") and "商品ID" in out.columns:
        out = out[out["商品ID"].astype(str).isin(list(map(str, filters["goods_ids"])))]

    return out


def _build_goods_promo_rollup(material_df: pd.DataFrame, promo_df: pd.DataFrame) -> pd.DataFrame:
    if material_df.empty:
        return pd.DataFrame()

    promo_base = _prepare_promotion_base(promo_df)
    promo_base["商品ID"] = _normalize_goods_id_series(promo_base["商品ID"])
    promo_base["日期"] = pd.to_datetime(promo_base["日期"], errors="coerce")

    group_keys = [
        "店铺名称",
        "商品ID",
        "链接标题",
        "数据口径",
        "统计日期文本",
        "开始日期",
        "结束日期",
        "统计天数",
    ]

    periods = material_df[group_keys].drop_duplicates().copy()
    periods["商品ID"] = _normalize_goods_id_series(periods["商品ID"])

    results = []

    for _, row in periods.iterrows():
        goods_id = str(row["商品ID"]).strip()
        start = row["开始日期"]
        end = row["结束日期"]

        current = promo_base[
            (promo_base["商品ID"] == goods_id)
            & (promo_base["日期"] >= start)
            & (promo_base["日期"] <= end)
        ].copy()

        result = row.to_dict()
        result["商品ID汇总实际成交花费(元)"] = float(current["实际成交花费"].sum()) if len(current) else 0.0
        result["商品ID汇总结算金额(元)"] = float(current["结算金额"].sum()) if len(current) else 0.0
        result["商品ID汇总曝光量"] = float(current["曝光"].sum()) if len(current) else 0.0
        result["商品ID汇总点击量"] = float(current["点击"].sum()) if len(current) else 0.0
        result["商品ID汇总成交笔数"] = float(current["成交订单数"].sum()) if len(current) else 0.0
        result["商品ID汇总净交易额(元)"] = float(current["净交易额"].sum()) if len(current) else 0.0
        result["商品ID汇总结算投产比"] = safe_divide(
            result["商品ID汇总结算金额(元)"],
            result["商品ID汇总实际成交花费(元)"],
        )

        result["素材数量"] = int(
            material_df[
                (material_df["商品ID"].astype(str).map(_normalize_goods_id_value) == goods_id)
                & (material_df["开始日期"] == start)
                & (material_df["结束日期"] == end)
            ]["素材编号"].nunique()
        )

        results.append(result)

    return pd.DataFrame(results)


def _allocate_creative_estimated_spend(material_df: pd.DataFrame, goods_rollup_df: pd.DataFrame) -> pd.DataFrame:
    if material_df.empty:
        return pd.DataFrame()

    merge_keys = [
        "店铺名称",
        "商品ID",
        "链接标题",
        "数据口径",
        "统计日期文本",
        "开始日期",
        "结束日期",
        "统计天数",
    ]

    out = material_df.merge(goods_rollup_df, on=merge_keys, how="left")

    out["商品ID汇总实际成交花费(元)"] = pd.to_numeric(
        out.get("商品ID汇总实际成交花费(元)", 0), errors="coerce"
    ).fillna(0.0)

    click_totals = (
        out.groupby(merge_keys, dropna=False)["点击量"]
        .sum()
        .reset_index(name="素材组总点击量")
    )
    out = out.merge(click_totals, on=merge_keys, how="left")
    out["素材组总点击量"] = pd.to_numeric(out["素材组总点击量"], errors="coerce").fillna(0.0)

    out["估算花费(元)"] = out.apply(
        lambda r: r["商品ID汇总实际成交花费(元)"] * safe_divide(r["点击量"], r["素材组总点击量"]),
        axis=1,
    )
    out["估算ROI"] = out.apply(
        lambda r: safe_divide(r["净交易额(元)"], r["估算花费(元)"]),
        axis=1,
    )
    return out


def _build_creative_type_summary(material_detail: pd.DataFrame) -> pd.DataFrame:
    if material_detail.empty:
        return pd.DataFrame()

    group_cols = ["商品ID", "素材类型大类", "素材类型小类"]
    out = (
        material_detail.groupby(group_cols, dropna=False)
        .agg(
            素材数量=("素材编号", "nunique"),
            曝光量=("曝光量", "sum"),
            点击量=("点击量", "sum"),
            成交笔数=("成交笔数", "sum"),
            净交易额=("净交易额(元)", "sum"),
            估算花费=("估算花费(元)", "sum"),
        )
        .reset_index()
    )
    out["平均点击率"] = out.apply(lambda r: safe_divide(r["点击量"], r["曝光量"]), axis=1)
    out["平均点击转化率"] = out.apply(lambda r: safe_divide(r["成交笔数"], r["点击量"]), axis=1)
    out["估算ROI"] = out.apply(lambda r: safe_divide(r["净交易额"], r["估算花费"]), axis=1)
    out = out.rename(columns={"净交易额": "净交易额(元)", "估算花费": "估算花费(元)"})
    return out.sort_values(["商品ID", "净交易额(元)"], ascending=[True, False])


def _build_creative_anomalies(material_detail: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if material_detail.empty:
        return {
            "高曝光低点击素材": pd.DataFrame(),
            "高点击低转化素材": pd.DataFrame(),
            "高点击低净交易额素材": pd.DataFrame(),
            "高点击低估算ROI素材": pd.DataFrame(),
            "高潜素材": pd.DataFrame(),
        }

    records = []
    for _, grp in material_detail.groupby(["店铺名称", "商品ID", "统计日期文本"], dropna=False):
        g = grp.copy()

        imp_med = g["曝光量"].median() if len(g) else 0
        clk_med = g["点击量"].median() if len(g) else 0
        ctr_med = g["点击率"].median() if len(g) else 0
        cv_med = g["点击转化率"].median() if len(g) else 0
        net_med = g["净交易额(元)"].median() if len(g) else 0
        roi_med = g["估算ROI"].median() if len(g) else 0

        g["__高曝光低点击"] = (g["曝光量"] >= imp_med) & (g["点击率"] < ctr_med)
        g["__高点击低转化"] = (g["点击量"] >= clk_med) & (g["点击转化率"] < cv_med)
        g["__高点击低净交易额"] = (g["点击量"] >= clk_med) & (g["净交易额(元)"] < net_med)
        g["__高点击低估算ROI"] = (g["点击量"] >= clk_med) & (g["估算ROI"] < roi_med)
        g["__高潜素材"] = (g["点击率"] >= ctr_med) & (g["点击转化率"] >= cv_med) & (g["估算ROI"] >= roi_med)
        records.append(g)

    merged = pd.concat(records, ignore_index=True) if records else material_detail.copy()

    return {
        "高曝光低点击素材": merged[merged["__高曝光低点击"]].drop(columns=[c for c in merged.columns if c.startswith("__")], errors="ignore"),
        "高点击低转化素材": merged[merged["__高点击低转化"]].drop(columns=[c for c in merged.columns if c.startswith("__")], errors="ignore"),
        "高点击低净交易额素材": merged[merged["__高点击低净交易额"]].drop(columns=[c for c in merged.columns if c.startswith("__")], errors="ignore"),
        "高点击低估算ROI素材": merged[merged["__高点击低估算ROI"]].drop(columns=[c for c in merged.columns if c.startswith("__")], errors="ignore"),
        "高潜素材": merged[merged["__高潜素材"]].drop(columns=[c for c in merged.columns if c.startswith("__")], errors="ignore"),
    }


def _analyze_creative_material(
    creative_material_df: pd.DataFrame,
    promo_df: pd.DataFrame,
    filters: dict | None = None,
) -> dict[str, pd.DataFrame]:
    if creative_material_df is None or creative_material_df.empty:
        empty = pd.DataFrame()
        return {
            "goods_rollup": empty,
            "material_detail": empty,
            "type_summary": empty,
            "anomalies": {
                "高曝光低点击素材": empty,
                "高点击低转化素材": empty,
                "高点击低净交易额素材": empty,
                "高点击低估算ROI素材": empty,
                "高潜素材": empty,
            },
        }

    material_base = _prepare_creative_material_base(creative_material_df)
    material_base = _apply_creative_material_filters(material_base, filters)

    if material_base.empty:
        empty = pd.DataFrame()
        return {
            "goods_rollup": empty,
            "material_detail": empty,
            "type_summary": empty,
            "anomalies": {
                "高曝光低点击素材": empty,
                "高点击低转化素材": empty,
                "高点击低净交易额素材": empty,
                "高点击低估算ROI素材": empty,
                "高潜素材": empty,
            },
        }

    goods_rollup = _build_goods_promo_rollup(material_base, promo_df)
    material_detail = _allocate_creative_estimated_spend(material_base, goods_rollup)
    type_summary = _build_creative_type_summary(material_detail)
    anomalies = _build_creative_anomalies(material_detail)

    return {
        "goods_rollup": goods_rollup.sort_values(["商品ID", "开始日期"], ascending=[True, True]),
        "material_detail": material_detail.sort_values(["商品ID", "开始日期", "素材编号"], ascending=[True, True, True]),
        "type_summary": type_summary,
        "anomalies": anomalies,
    }


def _analyze_promotion(promo_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    base = _prepare_promotion_base(promo_df)

    daily = (
        base.groupby("日期", dropna=False)
        .agg(
            实际成交花费=("实际成交花费", "sum"),
            结算金额=("结算金额", "sum"),
            推广商品ID数=("商品ID", lambda s: int(pd.Series(s).replace("", np.nan).dropna().nunique())),
            曝光=("曝光", "sum"),
            点击=("点击", "sum"),
            成交订单数=("成交订单数", "sum"),
        )
        .reset_index()
    )
    daily["结算投产比"] = daily.apply(lambda r: safe_divide(r["结算金额"], r["实际成交花费"]), axis=1)
    daily["CTR"] = daily.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    daily["转化率"] = daily.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)
    daily = daily.sort_values("日期")

    goods = (
        base.groupby("商品ID", dropna=False)
        .agg(
            链接标题=("链接标题", "first"),
            实际成交花费=("实际成交花费", "sum"),
            结算金额=("结算金额", "sum"),
            曝光=("曝光", "sum"),
            点击=("点击", "sum"),
            成交订单数=("成交订单数", "sum"),
            投放天数=("日期", lambda s: int(pd.Series(s).dropna().nunique())),
        )
        .reset_index()
    )
    goods["结算投产比"] = goods.apply(lambda r: safe_divide(r["结算金额"], r["实际成交花费"]), axis=1)
    goods["CTR"] = goods.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    goods["转化率"] = goods.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)

    total_spend = goods["实际成交花费"].sum()
    goods["花费占比"] = goods.apply(lambda r: safe_divide(r["实际成交花费"], total_spend), axis=1)
    goods["花费排名"] = goods["实际成交花费"].rank(method="dense", ascending=False).astype(int)
    goods["ROI排名"] = goods["结算投产比"].rank(method="dense", ascending=False).astype(int)
    goods["日均实际成交花费"] = goods.apply(lambda r: safe_divide(r["实际成交花费"], r["投放天数"]), axis=1)
    goods["日均结算金额"] = goods.apply(lambda r: safe_divide(r["结算金额"], r["投放天数"]), axis=1)
    goods = goods.sort_values("实际成交花费", ascending=False)

    detail = (
        base.groupby(["日期", "商品ID"], dropna=False)
        .agg(
            链接标题=("链接标题", "first"),
            实际成交花费=("实际成交花费", "sum"),
            结算金额=("结算金额", "sum"),
            曝光=("曝光", "sum"),
            点击=("点击", "sum"),
            成交订单数=("成交订单数", "sum"),
        )
        .reset_index()
    )
    detail["结算投产比"] = detail.apply(lambda r: safe_divide(r["结算金额"], r["实际成交花费"]), axis=1)
    detail["CTR"] = detail.apply(lambda r: safe_divide(r["点击"], r["曝光"]), axis=1)
    detail["转化率"] = detail.apply(lambda r: safe_divide(r["成交订单数"], r["点击"]), axis=1)
    detail = detail.sort_values(["商品ID", "日期"], ascending=[True, True])

    spend_median = goods["实际成交花费"].median() if len(goods) else 0
    roi_median = goods["结算投产比"].median() if len(goods) else 0

    high_spend_low_roi = goods[
        (goods["实际成交花费"] >= spend_median) & (goods["结算投产比"] < roi_median)
    ].copy()

    high_spend_low_settle = goods[
        (goods["实际成交花费"] >= spend_median)
        & (goods["结算金额"] < goods["实际成交花费"] * 1.2)
    ].copy()

    detail_sorted = detail.sort_values(["商品ID", "日期"])
    roi_drop_rows = []
    for _, grp in detail_sorted.groupby("商品ID"):
        g = grp.dropna(subset=["日期"]).tail(3)
        if len(g) == 3:
            vals = g["结算投产比"].tolist()
            if vals[0] > vals[1] > vals[2]:
                roi_drop_rows.append(g.iloc[-1])
    roi_continuous_down = pd.DataFrame(roi_drop_rows)

    scale_bad_rows = []
    for _, grp in detail_sorted.groupby("商品ID"):
        g = grp.dropna(subset=["日期"]).sort_values("日期")
        if len(g) >= 3:
            last = g.iloc[-1]
            prev = g.iloc[:-1]
            prev_spend_mean = prev["实际成交花费"].mean()
            prev_roi_mean = prev["结算投产比"].mean()
            if last["实际成交花费"] > prev_spend_mean * 1.5 and last["结算投产比"] < prev_roi_mean * 0.8:
                scale_bad_rows.append(last)
    scale_up_but_worse = pd.DataFrame(scale_bad_rows)

    anomalies = {
        "高花费低ROI商品": high_spend_low_roi,
        "高花费低结算金额商品": high_spend_low_settle,
        "ROI连续下滑商品": roi_continuous_down,
        "放量但效率恶化商品": scale_up_but_worse,
    }

    return {
        "daily": daily,
        "goods": goods,
        "detail": detail,
        "anomalies": anomalies,
    }
