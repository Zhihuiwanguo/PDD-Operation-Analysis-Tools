"""退款/售后分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
    return out


def render(refund_analysis: dict) -> None:
    st.subheader("退款/售后分析")
    messages = refund_analysis.get("messages", []) if isinstance(refund_analysis, dict) else []
    for msg in messages:
        st.warning(msg)

    overview = refund_analysis.get("overview", {}) if isinstance(refund_analysis, dict) else {}
    daily = refund_analysis.get("daily", pd.DataFrame()) if isinstance(refund_analysis, dict) else pd.DataFrame()
    product = refund_analysis.get("product", pd.DataFrame()) if isinstance(refund_analysis, dict) else pd.DataFrame()
    link = refund_analysis.get("link", pd.DataFrame()) if isinstance(refund_analysis, dict) else pd.DataFrame()
    alerts = refund_analysis.get("alerts", pd.DataFrame()) if isinstance(refund_analysis, dict) else pd.DataFrame()

    st.markdown("### 一、总览卡片")
    cards = [
        ("支付订单数", overview.get("支付订单数", 0), "int"),
        ("商家实收", overview.get("商家实收金额", 0.0), "money"),
        ("退款成功订单数", overview.get("退款成功订单数", 0), "int"),
        ("退款成功率", overview.get("退款成功率", 0.0), "pct"),
        ("退款金额", overview.get("退款金额", 0.0), "money"),
        ("剔除退款后商家实收", overview.get("剔除退款后商家实收", 0.0), "money"),
        ("售后处理中订单数", overview.get("售后处理中订单数", 0), "int"),
        ("确认有效商家实收", overview.get("确认有效商家实收", 0.0), "money"),
    ]
    cols = st.columns(4)
    for idx, (label, value, kind) in enumerate(cards):
        if kind == "pct":
            display = f"{float(value):.2%}"
        elif kind == "money":
            display = f"¥{float(value):,.2f}"
        else:
            display = f"{int(value)}"
        cols[idx % 4].metric(label, display)

    st.markdown("### 二、每日退款趋势表")
    daily_cols = [
        "日期", "支付订单数", "商家实收金额", "退款成功订单数", "退款成功率", "未发货退款订单数",
        "未成交退款订单数", "发货后退款订单数", "售后处理中订单数", "剔除退款后商家实收", "确认有效商家实收",
    ]
    if daily is None or daily.empty:
        st.info("当前无每日退款趋势数据。")
    else:
        show = _format_percent_columns(daily[[c for c in daily_cols if c in daily.columns]], ["退款成功率"])
        st.dataframe(show, use_container_width=True)

    st.markdown("### 三、产品退款分析表")
    product_cols = [
        "标准产品名称", "支付订单数", "商家实收金额", "退款成功订单数", "退款成功率", "退款金额",
        "未发货退款订单数", "未成交退款订单数", "发货后退款订单数", "售后处理中订单数", "剔除退款后商家实收",
    ]
    if product is None or product.empty:
        st.info("当前无产品退款分析数据。")
    else:
        show = _format_percent_columns(product[[c for c in product_cols if c in product.columns]], ["退款成功率"])
        st.dataframe(show, use_container_width=True)

    st.markdown("### 四、链接退款分析表（按商品ID，不拆规格）")
    link_cols = [
        "商品ID", "商品名称", "支付订单数", "商家实收金额", "退款成功订单数", "退款成功率", "退款金额",
        "未发货退款订单数", "未成交退款订单数", "发货后退款订单数", "售后处理中订单数", "剔除退款后商家实收",
    ]
    if link is None or link.empty:
        st.info("当前无链接退款分析数据。")
    else:
        show = _format_percent_columns(link[[c for c in link_cols if c in link.columns]], ["退款成功率"])
        st.dataframe(show, use_container_width=True)

    st.markdown("### 五、异常提醒")
    if alerts is None or alerts.empty:
        st.success("当前无退款/售后异常提醒。")
    else:
        pct_cols = [c for c in ["退款成功率"] if c in alerts.columns]
        st.dataframe(_format_percent_columns(alerts, pct_cols), use_container_width=True)
