"""经营总览页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_rate_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
    return out


def render(overview: dict) -> None:
    st.subheader("经营总览")

    metrics_dict = overview.get("metrics", {})
    daily_trend = overview.get("daily_trend", pd.DataFrame())
    profit_breakdown = overview.get("profit_breakdown", pd.DataFrame())
    product_profit_rank = overview.get("product_profit_rank", pd.DataFrame())

    core_metrics = [
        "商品总价",
        "商家实收",
        "有效订单数",
        "客单价",
        "产品毛利率",
        "快递费",
        "扣快递费毛利率",
        "结算券总额",
    ]
    st.markdown("### 核心经营指标")
    cols = st.columns(4)
    for idx, key in enumerate(core_metrics):
        val = metrics_dict.get(key, 0)
        if "率" in key:
            display = f"{float(val):.2%}"
        elif "数" in key:
            display = f"{int(val)}"
        else:
            display = f"¥{float(val):,.2f}"
        help_text = "商家实收口径" if key in ["产品毛利率", "扣快递费毛利率"] else None
        if key == "快递费":
            help_text = "有效订单口径"
        if key == "结算券总额":
            help_text = "已影响商家实收，仅列示不重复扣减"
        cols[idx % 4].metric(key, display, help=help_text)

    st.caption("产品毛利率只扣产品成本；扣快递费毛利率只扣产品成本和快递费；结算券已影响商家实收，不作为利润扣减项重复计算。")

    st.markdown("### 利润结构拆解")
    if profit_breakdown.empty:
        st.info("当前无利润结构拆解数据。")
    else:
        st.dataframe(profit_breakdown, use_container_width=True)

    st.markdown("### 商品利润排行")
    if product_profit_rank.empty:
        st.info("当前无商品利润排行数据。")
    else:
        sort_options = [c for c in ["商家实收金额", "扣快递费毛利率", "扣推广后毛利", "结算券总额", "推广成交花费"] if c in product_profit_rank.columns]
        sort_col = st.selectbox("排序字段", sort_options, index=0) if sort_options else None
        rank_df = product_profit_rank.sort_values(sort_col, ascending=False) if sort_col else product_profit_rank.copy()
        show_cols = [
            c for c in [
                "商品ID", "商品名称", "标准产品", "有效订单数", "商家实收金额", "产品总成本", "快递费",
                "产品毛利额", "产品毛利率", "扣快递费毛利额", "扣快递费毛利率", "结算券总额",
                "推广成交花费", "扣推广后毛利",
            ] if c in rank_df.columns
        ]
        rank_show = _format_rate_columns(rank_df[show_cols], ["产品毛利率", "扣快递费毛利率"])
        st.dataframe(rank_show, use_container_width=True)

    st.markdown("---")
    st.info("经营利润/扣推广后贡献毛利仅扣推广成交花费，不再二次扣除结算券花费；结算券仅用于价格链路和商品营销总花费展示。")

    st.markdown("### 其他经营指标")
    other_metrics = [
        "总订单数", "无效订单数", "待确认订单数", "非经营剔除订单数", "用户实付", "店铺优惠折扣", "平台优惠折扣",
        "产品总成本", "产品毛利额", "扣快递费毛利额", "平台扣点", "订单侧估算毛利", "推广成交花费",
        "店铺扣推广后贡献毛利", "店铺整体实际ROI", "盈亏平衡ROI", "退款成功订单数", "退款成功率", "退款金额",
        "剔除退款后商家实收", "售后处理中金额", "确认有效商家实收", "退款后ROI", "确认有效ROI",
    ]
    cols = st.columns(3)
    for idx, key in enumerate(other_metrics):
        val = metrics_dict.get(key, 0)
        if "率" in key and "ROI" not in key:
            display = f"{float(val):.2%}"
        elif "ROI" in key:
            display = f"{float(val):.2f}"
        elif "数" in key:
            display = f"{int(val)}"
        else:
            display = f"¥{float(val):,.2f}"
        cols[idx % 3].metric(key, display)

    st.markdown("### 每日趋势")

    if daily_trend.empty:
        st.info("当前无经营总览趋势数据。")
        return

    chart_df = daily_trend.copy().sort_values("日期").set_index("日期")

    left_col, right_col = st.columns(2)

    with left_col:
        if "商家实收" in chart_df.columns:
            st.markdown("#### 商家实收每日趋势")
            st.line_chart(chart_df[["商家实收"]], use_container_width=True)

    with right_col:
        if "客户实付" in chart_df.columns:
            st.markdown("#### 客户实付每日趋势")
            st.line_chart(chart_df[["客户实付"]], use_container_width=True)

    st.markdown("#### 每日趋势明细")
    st.dataframe(daily_trend, use_container_width=True)
