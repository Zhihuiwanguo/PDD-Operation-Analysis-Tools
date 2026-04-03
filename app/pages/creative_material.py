"""推广素材分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
    return out


def render(creative_analysis: dict):
    st.subheader("推广素材分析")

    goods_rollup = creative_analysis.get("goods_rollup", pd.DataFrame())
    material_detail = creative_analysis.get("material_detail", pd.DataFrame())
    type_summary = creative_analysis.get("type_summary", pd.DataFrame())
    anomalies = creative_analysis.get("anomalies", {})

    if goods_rollup.empty and material_detail.empty:
        st.info("当前无推广素材分析数据。")
        return

    st.markdown("### 一、商品ID推广汇总")
    if goods_rollup.empty:
        st.info("当前无商品ID推广汇总数据。")
    else:
        summary_cols = [
            c
            for c in [
                "店铺名称",
                "商品ID",
                "链接标题",
                "数据口径",
                "统计日期文本",
                "开始日期",
                "结束日期",
                "统计天数",
                "商品ID汇总实际成交花费(元)",
                "商品ID汇总结算金额(元)",
                "商品ID汇总结算投产比",
                "商品ID汇总曝光量",
                "商品ID汇总点击量",
                "商品ID汇总成交笔数",
                "商品ID汇总净交易额(元)",
                "素材数量",
            ]
            if c in goods_rollup.columns
        ]
        st.dataframe(goods_rollup[summary_cols], use_container_width=True)

    st.markdown("---")
    st.markdown("### 二、素材明细对比")

    if material_detail.empty:
        st.info("当前无素材明细数据。")
    else:
        show_cols = [
            c
            for c in [
                "店铺名称",
                "商品ID",
                "链接标题",
                "数据口径",
                "统计日期文本",
                "素材编号",
                "素材名称",
                "素材类型大类",
                "素材类型小类",
                "是否启用",
                "曝光量",
                "点击量",
                "点击率",
                "成交笔数",
                "交易额(元)",
                "净交易额(元)",
                "点击转化率",
                "商品ID汇总实际成交花费(元)",
                "估算花费(元)",
                "估算ROI",
            ]
            if c in material_detail.columns
        ]
        material_show = _format_percent_columns(
            material_detail[show_cols],
            ["点击率", "点击转化率"],
        )
        st.dataframe(material_show, use_container_width=True)

    st.markdown("---")
    st.markdown("### 三、素材类型汇总")
    if type_summary.empty:
        st.info("当前无素材类型汇总数据。")
    else:
        type_show_cols = [
            c
            for c in [
                "商品ID",
                "素材类型大类",
                "素材类型小类",
                "素材数量",
                "曝光量",
                "点击量",
                "平均点击率",
                "成交笔数",
                "净交易额(元)",
                "平均点击转化率",
                "估算花费(元)",
                "估算ROI",
            ]
            if c in type_summary.columns
        ]
        type_show = _format_percent_columns(
            type_summary[type_show_cols],
            ["平均点击率", "平均点击转化率"],
        )
        st.dataframe(type_show, use_container_width=True)

    st.markdown("---")
    st.markdown("### 四、素材异常识别")
    if not anomalies:
        st.info("当前无素材异常结果。")
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
                        "店铺名称",
                        "商品ID",
                        "统计日期文本",
                        "素材编号",
                        "素材名称",
                        "素材类型大类",
                        "曝光量",
                        "点击量",
                        "点击率",
                        "成交笔数",
                        "净交易额(元)",
                        "点击转化率",
                        "估算花费(元)",
                        "估算ROI",
                    ]
                    if c in df.columns
                ]
                df_show = _format_percent_columns(df[show_cols], ["点击率", "点击转化率"])
                st.dataframe(df_show, use_container_width=True)
            st.markdown("---")
