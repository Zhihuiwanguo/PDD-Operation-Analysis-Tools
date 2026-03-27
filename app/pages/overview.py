"""经营总览页。"""

from __future__ import annotations

import streamlit as st


def render(overview: dict[str, float]) -> None:
    st.subheader("经营总览")

    metrics = [
        "总订单数",
        "有效订单数",
        "无效订单数",
        "待确认订单数",
        "非经营剔除订单数",
        "用户实付",
        "商家实收",
        "订单侧估算毛利",
        "店铺总盘推广费（现金口径）",
        "店铺整体实际ROI",
        "店铺扣推广后贡献毛利",
        "盈亏平衡ROI",
    ]

    cols = st.columns(3)
    for idx, key in enumerate(metrics):
        val = overview.get(key, 0)
        if "ROI" in key:
            display = f"{val:.2f}"
        elif "数" in key:
            display = f"{int(val)}"
        else:
            display = f"¥{val:,.2f}"
        cols[idx % 3].metric(key, display)
