"""推广订单豁免分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_loader import load_table
from app.exporters import to_excel_bytes
from app.promotion_exemption_analysis import build_promotion_exemption_analysis

UPLOAD_FILE_TYPES = ["csv", "xls", "xlsx"]


def _metric_value(value, kind: str) -> str:
    if kind == "pct":
        return f"{float(value or 0):.2%}"
    if kind == "money":
        return f"¥{float(value or 0):,.2f}"
    return f"{int(value or 0):,}"


def _format_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if "豁免覆盖率" in out.columns:
        out["豁免覆盖率"] = pd.to_numeric(out["豁免覆盖率"], errors="coerce").fillna(0).map(lambda x: f"{x:.2%}")
    return out


def _render_uploads(key_prefix: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    st.markdown("### 数据上传")
    c1, c2 = st.columns(2)
    with c1:
        order_file = st.file_uploader("1. 拼多多订单明细（CSV / Excel）", type=UPLOAD_FILE_TYPES, key=f"{key_prefix}_orders")
        promo_deal_file = st.file_uploader("3. 商品推广成交明细（选传，后续增强使用）", type=UPLOAD_FILE_TYPES, key=f"{key_prefix}_promo_deal")
    with c2:
        exemption_file = st.file_uploader("2. 拼多多推广豁免订单数据（Excel）", type=["xls", "xlsx"], key=f"{key_prefix}_exemption")
        refund_file = st.file_uploader("4. 售后退款明细（选传，后续增强使用）", type=UPLOAD_FILE_TYPES, key=f"{key_prefix}_refund")

    orders = load_table(order_file, order_file.name, key="orders") if order_file is not None else pd.DataFrame()
    exemptions = load_table(exemption_file, exemption_file.name) if exemption_file is not None else pd.DataFrame()
    promo_deal = load_table(promo_deal_file, promo_deal_file.name) if promo_deal_file is not None else pd.DataFrame()
    refund = load_table(refund_file, refund_file.name) if refund_file is not None else pd.DataFrame()
    return orders, exemptions, promo_deal, refund


def render(default_orders: pd.DataFrame | None = None, key_prefix: str = "promotion_exemption") -> None:
    st.subheader("推广订单豁免分析")
    st.caption("用于识别退款成功但未出现在推广豁免清单中的订单，并按商品、订单状态、判定分类汇总。")

    use_current_orders = False
    if default_orders is not None and not default_orders.empty:
        use_current_orders = st.checkbox("使用当前经营分析已上传的订单明细", value=True, key=f"{key_prefix}_use_current_orders")

    orders, exemptions, promo_deal, refund = _render_uploads(key_prefix)
    if use_current_orders and orders.empty:
        orders = default_orders.copy()

    if not promo_deal.empty or not refund.empty:
        st.info("已接收选传文件。当前版本先完成豁免匹配与疑似漏识别分析，商品推广成交明细和售后退款明细将用于后续增强规则判断。")

    date_range = None
    if not orders.empty:
        pay_dates = pd.to_datetime(orders.get("支付时间", pd.Series(dtype=str)), errors="coerce").dropna()
        if not pay_dates.empty:
            date_range = st.date_input(
                "分析期间（按订单明细中的支付时间筛选；豁免清单按订单支付日期同步筛选）",
                value=(pay_dates.min().date(), pay_dates.max().date()),
                key=f"{key_prefix}_date_range",
            )

    if orders.empty or exemptions.empty:
        st.warning("请上传拼多多订单明细和拼多多推广豁免订单数据后开始分析。")
        return

    result = build_promotion_exemption_analysis(orders, exemptions, date_range if isinstance(date_range, (tuple, list)) else None)

    for msg in result.get("messages", []):
        st.warning(msg)

    overview = result.get("overview", {})
    st.markdown("### 一、总览指标")
    cards = [
        ("支付订单数", overview.get("支付订单数", 0), "int"),
        ("退款成功订单数", overview.get("退款成功订单数", 0), "int"),
        ("已豁免订单数", overview.get("已豁免订单数", 0), "int"),
        ("未豁免订单数", overview.get("未豁免订单数", 0), "int"),
        ("豁免覆盖率", overview.get("豁免覆盖率", 0), "pct"),
        ("已豁免商家实收金额", overview.get("已豁免商家实收金额", 0), "money"),
        ("未豁免商家实收金额", overview.get("未豁免商家实收金额", 0), "money"),
        ("疑似应豁免但未豁免订单数", overview.get("疑似应豁免但未豁免订单数", 0), "int"),
        ("疑似应豁免但未豁免金额", overview.get("疑似应豁免但未豁免金额", 0), "money"),
    ]
    cols = st.columns(3)
    for idx, (label, value, kind) in enumerate(cards):
        cols[idx % 3].metric(label, _metric_value(value, kind))

    st.markdown("### 二、商品汇总")
    st.dataframe(_format_table(result.get("product_summary", pd.DataFrame())), use_container_width=True)

    st.markdown("### 三、订单状态汇总")
    st.dataframe(_format_table(result.get("status_summary", pd.DataFrame())), use_container_width=True)

    st.markdown("### 四、判定分类汇总")
    st.dataframe(result.get("category_summary", pd.DataFrame()), use_container_width=True)

    st.markdown("### 五、未豁免退款订单明细")
    details = result.get("unexempted_details", pd.DataFrame())
    st.dataframe(details, use_container_width=True)

    export_payload = {
        "未豁免退款订单明细": details,
        "疑似应豁免但未豁免": result.get("suspected_details", pd.DataFrame()),
        "商品汇总": result.get("product_summary", pd.DataFrame()),
        "状态汇总": result.get("status_summary", pd.DataFrame()),
        "判定分类汇总": result.get("category_summary", pd.DataFrame()),
        "已解析豁免清单": result.get("exemption_orders", pd.DataFrame()),
    }
    st.download_button(
        "导出推广订单豁免分析 Excel",
        data=to_excel_bytes(export_payload),
        file_name="推广订单豁免分析.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}_download",
    )
