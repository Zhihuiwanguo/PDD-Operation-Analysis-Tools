"""Q2考核达成率页面。"""

from __future__ import annotations

import streamlit as st


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def render(kpi: dict) -> None:
    st.subheader("Q2考核达成率")

    cols = st.columns(3)
    cols[0].metric("当前销售额", f"¥{kpi.get('当前销售额', 0.0):,.2f}")
    cols[1].metric("Q2销售目标", f"¥{kpi.get('Q2销售目标', 0.0):,.2f}")
    cols[2].metric("销售达成率", _fmt_pct(kpi.get("销售达成率", 0.0)))

    cols2 = st.columns(3)
    cols2[0].metric("当前实际ROI", f"{kpi.get('当前实际ROI', 0.0):.2f}")
    cols2[1].metric("Q2 ROI目标", f"{kpi.get('Q2 ROI目标', 0.0):.2f}")
    cols2[2].metric("ROI达成率", _fmt_pct(kpi.get("ROI达成率", 0.0)))

    cols3 = st.columns(3)
    cols3[0].metric("ROI扣分法达成率", _fmt_pct(kpi.get("ROI扣分法达成率", 0.0)))
    cols3[1].metric("个人指标得分", _fmt_pct(kpi.get("个人指标得分", 0.0)))
    cols3[2].metric("综合达成率", _fmt_pct(kpi.get("综合达成率", 0.0)))

    cols4 = st.columns(2)
    cols4[0].metric("当前毛利率", _fmt_pct(kpi.get("当前毛利率", 0.0)))
    cols4[1].metric("奖金风险等级", kpi.get("奖金风险等级", "-"))

    st.markdown("### 经营建议")
    st.info(kpi.get("经营建议", "暂无建议"))
