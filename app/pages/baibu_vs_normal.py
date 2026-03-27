"""百补 vs 日常对比页。"""

from __future__ import annotations

import streamlit as st

from app.config import CONFIG


def _efficiency_score(row) -> float:
    breakeven = row.get("盈亏平衡ROI", 0) or 0
    actual = row.get("实际ROI", 0) or 0
    return actual / breakeven if breakeven else 0


def _build_conclusion(side_row, other_row) -> str:
    t = CONFIG.baibu_conclusion_thresholds

    scale_adv = (
        side_row["有效订单数"] >= other_row["有效订单数"] * t.scale_advantage_ratio
        and side_row["商家实收"] >= other_row["商家实收"] * t.scale_advantage_ratio
    )

    eff_side = _efficiency_score(side_row)
    eff_other = _efficiency_score(other_row)
    profit_adv = (
        side_row["扣推广后贡献毛利"] >= other_row["扣推广后贡献毛利"] * t.profit_advantage_ratio
        or eff_side >= eff_other + t.efficiency_advantage_delta
    )

    if scale_adv and profit_adv:
        return "规模与利润效率均占优"
    if scale_adv and not profit_adv:
        return "更偏规模，但利润效率偏弱"
    if (not scale_adv) and profit_adv:
        return "规模较小，但利润效率更优"
    return "规模与利润效率均不占优"


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

    rows = {row["是否百补"]: row for _, row in compare_df.iterrows()}
    bb_row = rows.get("是")
    normal_row = rows.get("否")

    if bb_row is not None and normal_row is not None:
        st.markdown(f"- 百补盘：**{_build_conclusion(bb_row, normal_row)}**")
        st.markdown(f"- 日常盘：**{_build_conclusion(normal_row, bb_row)}**")
    else:
        st.info("当前筛选范围内百补/日常数据不完整，暂无法生成对比结论。")
