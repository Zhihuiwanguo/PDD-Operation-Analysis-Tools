"""百补 vs 日常对比页。"""

from __future__ import annotations

import streamlit as st


def _conclusion(row) -> str:
    margin = (row["扣推广后贡献毛利"] / row["商家实收"]) if row["商家实收"] else 0
    return "更偏利润" if margin >= 0.15 else "更偏规模"


def render(compare_df):
    st.subheader("百补 vs 日常对比")
    st.dataframe(
        compare_df[
            [
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
        ],
        use_container_width=True,
    )

    decisions = {row["是否百补"]: _conclusion(row) for _, row in compare_df.iterrows()}
    bb = decisions.get("是", "暂无数据")
    normal = decisions.get("否", "暂无数据")
    st.markdown(f"- 百补盘：**{bb}**")
    st.markdown(f"- 日常盘：**{normal}**")
