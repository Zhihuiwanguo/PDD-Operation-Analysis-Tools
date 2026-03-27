"""产品分析页。"""

from __future__ import annotations

import streamlit as st


def render(product_df):
    st.subheader("产品分析（按标准产品名称）")
    st.dataframe(
        product_df[
            [
                "标准产品名称",
                "产品层级标签",
                "有效订单数",
                "销售件数",
                "用户实付",
                "商家实收",
                "产品总成本",
                "快递总成本",
                "平台扣点",
                "订单侧估算毛利",
                "链接推广费合计",
                "扣推广后贡献毛利",
                "实际ROI",
                "盈亏平衡ROI",
            ]
        ],
        use_container_width=True,
    )
