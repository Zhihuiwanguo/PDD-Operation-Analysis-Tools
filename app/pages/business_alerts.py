"""经营异常清单页。"""

from __future__ import annotations

import streamlit as st


ALERT_DESCRIPTIONS = {
    "亏损链接清单": "扣推广后贡献毛利小于阈值，说明链接整体在亏损。",
    "低ROI链接清单": "实际ROI低于盈亏平衡ROI，说明当前投放效率不足以覆盖经营成本。",
    "高无效率规格清单": "规格无效率高，建议检查履约、售后与投放匹配度。",
    "高利润低销量规格清单": "规格利润率高但销量低，可评估是否加预算或优化曝光。",
    "有利润但未放量产品清单": "产品已具备正贡献毛利，但规模偏小，建议评估放量策略。",
}


def render(alerts: dict):
    st.subheader("经营异常清单")
    for name, desc in ALERT_DESCRIPTIONS.items():
        df = alerts.get(name)
        if df is None:
            continue
        st.markdown(f"#### {name}（{len(df)}）")
        st.caption(desc)
        st.dataframe(df, use_container_width=True)
