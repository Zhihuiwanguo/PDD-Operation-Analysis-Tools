"""经营分层页面。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _render_summary(df: pd.DataFrame, name_col: str) -> None:
    if df.empty:
        st.info("暂无可展示数据。")
        return

    summary = (
        df.groupby("经营分层", dropna=False)
        .agg(
            数量=(name_col, "count"),
            商家实收=("商家实收", "sum"),
            扣推广后贡献毛利=("扣推广后贡献毛利", "sum"),
        )
        .reset_index()
        
    )
    st.dataframe(summary, use_container_width=True)


def render(product_segmentation: pd.DataFrame, link_segmentation: pd.DataFrame) -> None:
    st.header("经营分层")

    st.subheader("产品经营分层")
    _render_summary(product_segmentation, "标准产品名称")

    product_cols = [
        "标准产品名称",
        "商家实收",
        "实际ROI",
        "盈亏平衡ROI",
        "扣推广后贡献毛利",
        "订单侧毛利率",
        "推广费率",
        "经营分层",
        "分层原因",
        "建议动作",
        "优先级",
    ]
    show_product_cols = [c for c in product_cols if c in product_segmentation.columns]
    st.dataframe(product_segmentation[show_product_cols], use_container_width=True)

    st.subheader("链接经营分层")
    _render_summary(link_segmentation, "商品ID")

    link_cols = [
        "商品ID",
        "链接标题",
        "标准产品名称",
        "是否百补",
        "商家实收",
        "实际成交花费(元)",
        "实际ROI",
        "盈亏平衡ROI",
        "扣推广后贡献毛利",
        "订单无效率",
        "经营分层",
        "分层原因",
        "建议动作",
        "优先级",
    ]
    show_link_cols = [c for c in link_cols if c in link_segmentation.columns]
    st.dataframe(link_segmentation[show_link_cols], use_container_width=True)
