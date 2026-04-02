"""经营总览页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render(overview: dict) -> None:
    st.subheader("经营总览")

    metrics_dict = overview.get("metrics", {})
    daily_trend = overview.get("daily_trend", pd.DataFrame())

    metrics = [
        "总订单数",
        "有效订单数",
        "无效订单数",
        "待确认订单数",
        "非经营剔除订单数",
        "用户实付",
        "商家实收",
        "客单价",
        "订单侧估算毛利",
        "店铺总盘推广费（现金口径）",
        "店铺整体实际ROI",
        "店铺扣推广后贡献毛利",
        "盈亏平衡ROI",
    ]

    cols = st.columns(3)
    for idx, key in enumerate(metrics):
        val = metrics_dict.get(key, 0)
        if "ROI" in key:
            display = f"{val:.2f}"
        elif "数" in key:
            display = f"{int(val)}"
        else:
            display = f"¥{val:,.2f}"
        cols[idx % 3].metric(key, display)

    st.markdown("---")
    st.markdown("### 每日趋势")

    if daily_trend.empty:
        st.info("当前无经营总览趋势数据。")
        return

    chart_df = daily_trend.copy().sort_values("日期").set_index("日期")

    left_col, right_col = st.columns(2)

    with left_col:
        if "商家实收" in chart_df.columns:
            st.markdown("#### 商家实收每日趋势")
            st.line_chart(chart_df[["商家实收"]], use_container_width=True)

    with right_col:
        if "客户实付" in chart_df.columns:
            st.markdown("#### 客户实付每日趋势")
            st.line_chart(chart_df[["客户实付"]], use_container_width=True)

    st.markdown("#### 每日趋势明细")
    st.dataframe(
        daily_trend,
        use_container_width=True,
    )
