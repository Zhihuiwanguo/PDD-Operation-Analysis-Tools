"""经营异常清单页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


ALERT_CONFIG = {
    "亏损链接清单": {
        "desc": "扣推广后贡献毛利小于阈值，说明链接整体在亏损。",
        "actions": [
            "优先检查该链接推广费是否明显高于订单侧毛利，必要时先降投或停投。",
            "检查是否属于百补盘低价引流链接，若是则单独设置止损阈值，不与日常利润盘混看。",
            "复核规格定价、赠品、平台扣点、快递成本，判断是投放问题还是商品模型问题。",
        ],
    },
    "低ROI链接清单": {
        "desc": "实际ROI低于盈亏平衡ROI，说明当前投放效率不足以覆盖经营成本。",
        "actions": [
            "优先优化主图、标题、卖点和详情首屏，先提升点击率和转化率，再决定是否继续放量。",
            "检查投放是否集中在低转化商品ID，必要时收缩预算到高转化链接。",
            "对比百补与日常盘同产品表现，判断是否应由百补承担规模、日常承担利润修复。",
        ],
    },
    "高无效率规格清单": {
        "desc": "规格无效率高，建议检查履约、售后与投放匹配度。",
        "actions": [
            "优先排查是否存在规格描述不清、下单误拍、履约异常、售后集中等问题。",
            "检查该规格是否是历史别名或映射异常，避免把底表问题误判成经营问题。",
            "必要时降低该规格投放，优先把流量导向更稳定、更易成交的规格。",
        ],
    },
    "高利润低销量规格清单": {
        "desc": "规格利润率高但销量低，可评估是否加预算或优化曝光。",
        "actions": [
            "优先检查该规格是否展示位置偏弱，是否需要前置到主规格或详情页第一屏。",
            "可小幅加预算测试放量，但先观察ROI和转化率，不建议直接大幅放量。",
            "评估是否将该规格包装为主推利润款，配合更明确的周期装/家庭装表达。",
        ],
    },
    "有利润但未放量产品清单": {
        "desc": "产品已具备正贡献毛利，但规模偏小，建议评估放量策略。",
        "actions": [
            "优先补投高质量素材，观察放量后ROI是否仍稳定高于盈亏平衡线。",
            "评估是否增加规格矩阵、价格带或百补/日常双盘承接，放大成交规模。",
            "若为潜力单品，可单独建立测试计划，不要与低效产品共用预算池。",
        ],
    },
}


def _append_action_column(df: pd.DataFrame, actions: list[str]) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return pd.DataFrame()

    out = df.copy()
    action_text = "；".join(actions)
    out["建议动作"] = action_text
    return out


def render(alerts: dict):
    st.subheader("经营异常")
    st.caption("以下异常基于当前筛选结果生成，建议动作用于辅助判断优先处理顺序，不改变现有经营口径。")

    for name, config in ALERT_CONFIG.items():
        df = alerts.get(name)
        desc = config["desc"]
        actions = config["actions"]

        if df is None:
            df = pd.DataFrame()

        st.markdown(f"#### {name}（{len(df)}）")
        st.caption(desc)

        with st.container(border=True):
            st.markdown("**建议动作**")
            for idx, action in enumerate(actions, start=1):
                st.write(f"{idx}. {action}")

        if len(df) == 0:
            st.info(f"当前无{name}")
            continue

        df_show = _append_action_column(df, actions)
        st.dataframe(df_show, use_container_width=True)
        st.markdown("---")
