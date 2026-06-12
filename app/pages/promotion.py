"""推广分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = (
                pd.to_numeric(out[col], errors="coerce")
                .fillna(0.0)
                .map(lambda x: f"{x:.2%}")
            )
    return out


def render(promotion_analysis: dict):
    st.subheader("推广分析")

    overview = promotion_analysis.get("overview", {})
    performance = promotion_analysis.get("performance", pd.DataFrame())
    diagnostics = promotion_analysis.get("diagnostics", pd.DataFrame())
    daily = promotion_analysis.get("daily", pd.DataFrame())
    goods = promotion_analysis.get("goods", pd.DataFrame())
    detail = promotion_analysis.get("detail", pd.DataFrame())
    anomalies = promotion_analysis.get("anomalies", {})
    account_flow = promotion_analysis.get("account_flow_validation", pd.DataFrame())
    data_version = promotion_analysis.get("data_version", "old_promotion")

    if daily.empty and goods.empty and detail.empty:
        st.info("当前无推广分析数据。")
        return

    st.info(f"当前推广数据口径：{data_version}。经营利润口径只扣推广成交花费，不二次扣结算券。")
    st.caption("平台 ROI = 推广成交金额 / 推广成交花费；财务 ROI = 推广订单商家实收 / 推广成交花费。")

    st.markdown("### 一、商品推广总览")
    overview_metrics = [
        "推广成交花费", "推广成交金额", "推广订单商家实收", "平台ROI", "财务ROI", "推广订单数",
        "推广成交件数", "推广费率", "结算券总额", "结算券占商家实收比例", "扣推广后毛利", "扣推广后毛利率",
    ]
    cols = st.columns(4)
    for idx, key in enumerate(overview_metrics):
        val = overview.get(key, 0)
        if "率" in key or "占" in key:
            display = f"{float(val):.2%}"
        elif "ROI" in key:
            display = f"{float(val):.2f}"
        elif "数" in key or "件数" in key:
            display = f"{int(val)}"
        else:
            display = f"¥{float(val):,.2f}"
        cols[idx % 4].metric(key, display)

    st.markdown("### 二、经营诊断结果")
    if diagnostics.empty:
        st.info("当前无经营诊断结果。")
    else:
        for text in diagnostics.get("诊断结果", pd.Series(dtype=str)).dropna().astype(str).tolist():
            st.write(f"- {text}")

    st.markdown("### 三、商品推广表现表")
    if performance.empty:
        st.info("当前无商品推广表现数据。")
    else:
        perf_cols = [
            c for c in [
                "商品ID", "商品名称", "标准产品", "推广成交金额", "推广订单商家实收", "成交花费", "平台ROI", "财务ROI",
                "推广费率", "结算券总额", "结算券占比", "产品成本", "快递费", "平台扣点", "扣推广后毛利",
                "扣推广后毛利率", "成交订单数", "退款订单数", "退款率", "判断标签",
            ] if c in performance.columns
        ]
        perf_show = _format_percent_columns(performance[perf_cols], ["推广费率", "结算券占比", "扣推广后毛利率", "退款率"])
        st.dataframe(perf_show, use_container_width=True)

    st.markdown("---")
    spend_scope = st.radio(
        "展示口径切换",
        ["旧推广口径：只看推广成交花费", "商品营销口径：推广成交花费 + 结算券花费", "经营利润口径：只扣推广成交花费"],
        horizontal=True,
    )
    st.caption("切换项用于页面理解口径；底层利润计算始终采用经营利润口径。")

    st.markdown("### 四、店铺级每日推广分析")
    if daily.empty:
        st.info("当前无每日推广数据。")
    else:
        daily_show_cols = [
            c
            for c in [
                "日期",
                "实际成交花费",
                "结算券花费",
                "商品营销总花费",
                "结算金额",
                "结算投产比",
                "推广商品ID数",
                "曝光",
                "点击",
                "CTR",
                "成交订单数",
                "转化率",
            ]
            if c in daily.columns
        ]
        daily_show = _format_percent_columns(daily[daily_show_cols], ["CTR", "转化率"])
        st.dataframe(daily_show, use_container_width=True)

        if "日期" in daily.columns:
            chart_df = daily.copy().sort_values("日期")

            if {"日期", "实际成交花费"}.issubset(chart_df.columns):
                st.markdown("#### 每日实际成交花费趋势")
                st.line_chart(chart_df.set_index("日期")[["实际成交花费"]], use_container_width=True)

            if {"日期", "结算金额"}.issubset(chart_df.columns):
                st.markdown("#### 每日结算金额趋势")
                st.line_chart(chart_df.set_index("日期")[["结算金额"]], use_container_width=True)

            if {"日期", "结算投产比"}.issubset(chart_df.columns):
                st.markdown("#### 每日结算投产比趋势")
                st.line_chart(chart_df.set_index("日期")[["结算投产比"]], use_container_width=True)

            if {"日期", "推广商品ID数"}.issubset(chart_df.columns):
                st.markdown("#### 每日推广商品ID数趋势")
                st.line_chart(chart_df.set_index("日期")[["推广商品ID数"]], use_container_width=True)

    st.markdown("---")
    st.markdown("### 五、商品ID汇总推广分析")
    if goods.empty:
        st.info("当前无商品ID推广汇总数据。")
    else:
        goods_show_cols = [
            c
            for c in [
                "商品ID",
                "链接标题",
                "实际成交花费",
                "结算券花费",
                "商品营销总花费",
                "结算金额",
                "结算投产比",
                "花费占比",
                "花费排名",
                "ROI排名",
                "曝光",
                "点击",
                "CTR",
                "成交订单数",
                "转化率",
                "投放天数",
                "日均实际成交花费",
                "日均结算金额",
            ]
            if c in goods.columns
        ]
        goods_show = _format_percent_columns(goods[goods_show_cols], ["CTR", "转化率", "花费占比"])
        st.dataframe(goods_show, use_container_width=True)

    st.markdown("---")
    st.markdown("### 六、单个商品ID趋势分析")
    if detail.empty:
        st.info("当前无单商品ID明细数据。")
    else:
        goods_options = (
            detail["商品ID"].fillna("").astype(str).replace("", pd.NA).dropna().unique().tolist()
            if "商品ID" in detail.columns
            else []
        )
        goods_options = sorted(goods_options)

        if not goods_options:
            st.info("当前无可选择的商品ID。")
        else:
            selected_goods_id = st.selectbox("选择商品ID", goods_options)
            selected_detail = detail[detail["商品ID"].astype(str) == str(selected_goods_id)].copy()

            show_cols = [
                c
                for c in [
                    "日期",
                    "商品ID",
                    "链接标题",
                    "实际成交花费",
                    "结算券花费",
                    "商品营销总花费",
                    "结算金额",
                    "结算投产比",
                    "曝光",
                    "点击",
                    "CTR",
                    "成交订单数",
                    "转化率",
                ]
                if c in selected_detail.columns
            ]
            selected_detail_show = _format_percent_columns(selected_detail[show_cols], ["CTR", "转化率"])
            st.dataframe(selected_detail_show, use_container_width=True)

            if "日期" in selected_detail.columns:
                selected_detail = selected_detail.sort_values("日期")

                if {"日期", "实际成交花费"}.issubset(selected_detail.columns):
                    st.markdown("#### 单商品ID每日实际成交花费趋势")
                    st.line_chart(
                        selected_detail.set_index("日期")[["实际成交花费"]],
                        use_container_width=True,
                    )

                if {"日期", "结算金额"}.issubset(selected_detail.columns):
                    st.markdown("#### 单商品ID每日结算金额趋势")
                    st.line_chart(
                        selected_detail.set_index("日期")[["结算金额"]],
                        use_container_width=True,
                    )

                if {"日期", "结算投产比"}.issubset(selected_detail.columns):
                    st.markdown("#### 单商品ID每日结算投产比趋势")
                    st.line_chart(
                        selected_detail.set_index("日期")[["结算投产比"]],
                        use_container_width=True,
                    )

                metric_cols = [c for c in ["点击", "曝光"] if c in selected_detail.columns]
                if metric_cols:
                    st.markdown("#### 单商品ID每日点击 / 曝光趋势")
                    st.line_chart(
                        selected_detail.set_index("日期")[metric_cols],
                        use_container_width=True,
                    )

    st.markdown("---")
    st.markdown("### 七、账户流水校验")
    if account_flow.empty:
        st.info("当前无账户流水校验结果。")
    else:
        st.dataframe(account_flow, use_container_width=True)

    st.markdown("### 八、推广异常识别")
    if not anomalies:
        st.info("当前无推广异常结果。")
    else:
        for name, df in anomalies.items():
            if df is None:
                df = pd.DataFrame()

            st.markdown(f"#### {name}（{len(df)}）")
            if len(df) == 0:
                st.info(f"当前无{name}")
            else:
                show_cols = [
                    c
                    for c in [
                        "商品ID",
                        "链接标题",
                        "日期",
                        "实际成交花费",
                        "结算券花费",
                        "商品营销总花费",
                        "结算金额",
                        "结算投产比",
                        "曝光",
                        "点击",
                        "CTR",
                        "成交订单数",
                        "转化率",
                        "花费占比",
                        "花费排名",
                        "ROI排名",
                    ]
                    if c in df.columns
                ]
                df_show = _format_percent_columns(df[show_cols], ["CTR", "转化率", "花费占比"])
                st.dataframe(df_show, use_container_width=True)
