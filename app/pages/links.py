"""链接分析页。"""

from __future__ import annotations

import streamlit as st


def render(link_df):
    st.subheader("链接分析")
    st.dataframe(
        link_df[[c for c in
            [
                "商品ID",
                "链接标题",
                "标准产品名称",
                "是否百补",
                "有效订单数",
                "无效订单数",
                "待确认订单数",
                "非经营剔除订单数",
                "商品总价",
                "店铺优惠折扣",
                "推广结算券金额",
                "店铺设置优惠金额",
                "平台优惠折扣",
                "用户实付",
                "商家实收",
                "产品总成本",
                "快递总成本",
                "平台扣点",
                "订单侧估算毛利",
                "推广成交花费",
                "结算券花费",
                "商品营销总花费",
                "实际成交花费(元)",
                "扣推广后贡献毛利",
                "经营利润",
                "是否异常",
                "实际ROI",
                "盈亏平衡ROI",
                "订单无效率",
            ] if c in link_df.columns]
        ],
        use_container_width=True,
    )
