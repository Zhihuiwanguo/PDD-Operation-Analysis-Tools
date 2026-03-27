"""百补 vs 日常对比页。"""

from __future__ import annotations

import math

import streamlit as st


def _safe_float(value) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, float) and math.isnan(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _efficiency_score(row) -> float:
    actual_roi = _safe_float(row.get("实际ROI", 0))
    breakeven_roi = _safe_float(row.get("盈亏平衡ROI", 0))
    if breakeven_roi <= 0:
        return 0.0
    return actual_roi / breakeven_roi


def _build_conclusion(current_row, other_row) -> str:
    current_orders = _safe_float(current_row.get("有效订单数", 0))
    current_revenue = _safe_float(current_row.get("商家实收", 0))
    current_contribution = _safe_float(current_row.get("扣推广后贡献毛利", 0))
    current_efficiency = _efficiency_score(current_row)

    other_orders = _safe_float(other_row.get("有效订单数", 0))
    other_revenue = _safe_float(other_row.get("商家实收", 0))
    other_contribution = _safe_float(other_row.get("扣推广后贡献毛利", 0))
    other_efficiency = _efficiency_score(other_row)

    current_scale_score = 0
    if current_orders > other_orders * 1.2:
        current_scale_score += 1
    if current_revenue > other_revenue * 1.2:
        current_scale_score += 1

    current_profit_score = 0
    if current_contribution > other_contribution * 1.1:
        current_profit_score += 1
    if current_efficiency > other_efficiency * 1.05:
        current_profit_score += 1

    if current_scale_score >= 1 and current_profit_score == 0:
        return "更偏规模，但利润效率偏弱"
    if current_scale_score == 0 and current_profit_score >= 1:
        return "规模较小，但利润效率更优"
    if current_scale_score >= 1 and current_profit_score >= 1:
        return "规模与利润效率均占优"
    return "规模与利润效率均不占优"


def render(compare_df):
    st.subheader("百补 vs 日常对比")

    show_cols = [
        "是否百补",
        "有效订单数",
        "用户实付",
        "商家实收",
        "产品总成本",
        "快递总成本",
        "平台扣点",
        "订单侧估算毛利",
        "推广费",
        "扣推广后贡献毛利",
        "实际ROI",
        "盈亏平衡ROI",
    ]
    existing_cols = [c for c in show_cols if c in compare_df.columns]

    st.dataframe(compare_df[existing_cols], use_container_width=True)

    rows = {row["是否百补"]: row for _, row in compare_df.iterrows() if "是否百补" in compare_df.columns}

    bb_row = rows.get("是")
    normal_row = rows.get("否")

    if bb_row is not None and normal_row is not None:
        bb_text = _build_conclusion(bb_row, normal_row)
        normal_text = _build_conclusion(normal_row, bb_row)
        st.markdown(f"- 百补盘：**{bb_text}**")
        st.markdown(f"- 日常盘：**{normal_text}**")
    elif bb_row is not None:
        st.markdown("- 百补盘：**当前仅有百补数据，无法与日常盘对比**")
    elif normal_row is not None:
        st.markdown("- 日常盘：**当前仅有日常数据，无法与百补盘对比**")
    else:
        st.info("当前无百补 / 日常对比数据。")
