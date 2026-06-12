"""规格分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_percent_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
    return out


def render(spec_df):
    st.subheader("规格分析（销量前五产品，按商品ID+规格）")
    if spec_df is None or len(spec_df) == 0:
        st.info("当前无规格分析数据。")
        return

    show_cols = [
        "商品ID",
        "标准产品名称",
        "销售规格名称",
        "规格定位建议",
        "有效订单数",
        "销售件数",
        "商品总价",
        "店铺优惠",
        "推广结算券",
        "平台优惠",
        "店铺设置优惠金额",
        "推广结算券金额",
        "店铺优惠折扣",
        "平台优惠折扣",
        "用户实付",
        "商家实收",
        "产品总成本",
        "快递总成本",
        "平台扣点",
        "订单侧估算毛利",
        "单均实收",
        "单均订单侧毛利",
        "订单侧毛利率",
        "无效率",
    ]
    show_cols = [c for c in show_cols if c in spec_df.columns]
    spec_show = _format_percent_columns(spec_df[show_cols], ["订单侧毛利率", "无效率"])
    st.caption("推广结算券按商品ID在规格间分摊后，从店铺优惠中拆出展示；规格利润仍基于订单侧估算毛利，不重复扣结算券。")
    st.dataframe(spec_show, use_container_width=True)
