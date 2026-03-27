"""规格分析页。"""

from __future__ import annotations

import streamlit as st


def render(spec_df):
    st.subheader("规格分析（销量前五产品）")
    st.dataframe(
        spec_df[
            [
                "标准产品名称",
                "销售规格名称",
                "规格定位建议",
                "有效订单数",
                "销售件数",
                "用户实付",
                "商家实收",
                "产品总成本",
                "快递总成本",
                "平台扣点",
                "订单侧估算毛利",
                "单均实收",
                "单均订单侧毛利",
                "订单侧毛利率",
                "无效率",
            ]
        ],
        use_container_width=True,
    )
