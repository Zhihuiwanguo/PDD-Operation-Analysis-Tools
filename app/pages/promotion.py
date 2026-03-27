"""推广数据分析页（过程分析）。"""

from __future__ import annotations

import streamlit as st


def _line(df, x, y, title):
    if df.empty or y not in df.columns:
        return
    st.line_chart(df.set_index(x)[y], height=220)
    st.caption(title)


def render(promo_ctx: dict):
    st.subheader("推广数据分析（过程口径）")

    daily = promo_ctx.get("daily")
    goods = promo_ctx.get("goods")
    detail = promo_ctx.get("detail")
    anomalies = promo_ctx.get("anomalies", {})

    st.markdown("### A. 店铺级每日推广分析")
    if daily is not None and not daily.empty:
        st.dataframe(daily, use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            _line(daily, "日期", "推广费", "每日推广费趋势")
            _line(daily, "日期", "推广成交金额", "每日推广成交金额趋势")
        with c2:
            _line(daily, "日期", "每日推广ROI", "每日推广ROI趋势")
            _line(daily, "日期", "推广商品ID数", "每日推广商品ID数趋势")
    else:
        st.info("当前筛选范围内无每日推广数据")

    st.markdown("### B. 商品ID汇总推广分析")
    if goods is not None and not goods.empty:
        st.dataframe(goods, use_container_width=True)
    else:
        st.info("当前筛选范围内无商品ID推广汇总数据")

    st.markdown("### C. 单个商品ID趋势分析")
    if detail is not None and not detail.empty:
        ids = sorted(detail["商品ID"].dropna().astype(str).unique().tolist())
        gid = st.selectbox("选择商品ID", ids)
        gdf = detail[detail["商品ID"].astype(str) == gid].sort_values("日期")
        st.dataframe(gdf, use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            _line(gdf, "日期", "推广费", "单商品ID每日推广费趋势")
            _line(gdf, "日期", "推广成交金额", "单商品ID每日推广成交金额趋势")
        with c2:
            _line(gdf, "日期", "实际ROI", "单商品ID每日推广ROI趋势")
            _line(gdf, "日期", "点击", "单商品ID每日点击趋势")
    else:
        st.info("当前筛选范围内无单商品趋势数据")

    st.markdown("### D. 推广异常识别")
    for name, df in anomalies.items():
        st.markdown(f"#### {name}（{0 if df is None else len(df)}）")
        if df is None or len(df) == 0:
            st.success(f"当前无{name}")
        else:
            st.dataframe(df, use_container_width=True)
