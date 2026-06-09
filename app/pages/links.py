"""链接分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_display(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["退款率", "退款金额占比", "发货后退款率", "扣推广后利润率", "订单无效率"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).map(lambda x: f"{x:.2%}")
    for col in ["ROI", "实际ROI", "退款后ROI", "确认有效ROI", "盈亏平衡ROI"]:
        if col in out.columns:
            spend = pd.to_numeric(out.get("成交花费", out.get("推广成交花费", out.get("实际成交花费(元)", 0))), errors="coerce").fillna(0.0)
            val = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
            out[col] = ["-" if s == 0 else f"{v:.2f}" for s, v in zip(spend, val)]
    return out


def render(link_df):
    st.subheader("链接分析")
    if link_df is None or len(link_df) == 0:
        st.info("当前无链接分析数据。")
        return
    show_cols = [c for c in [
        "商品ID",
        "链接标题",
        "标准产品名称",
        "有效订单数",
        "无效订单数",
        "待确认订单数",
        "非经营剔除订单数",
        "支付订单数",
        "商品总价",
        "商品件数",
        "用户实付",
        "商家实收",
        "退款订单数",
        "退款率",
        "退款金额",
        "未发货退款订单数",
        "发货后退款订单数",
        "售后处理中订单数",
        "剔除退款后商家实收",
        "确认有效商家实收",
        "产品总成本",
        "快递总成本",
        "平台扣点",
        "毛利金额",
        "推广成交花费",
        "成交花费",
        "结算券花费",
        "商品营销总花费",
        "扣推广后毛利",
        "扣推广后利润率",
        "经营利润",
        "链接校验提示",
        "是否异常",
        "ROI",
        "退款后ROI",
        "确认有效ROI",
        "实际ROI",
        "盈亏平衡ROI",
        "订单无效率",
    ] if c in link_df.columns]
    st.dataframe(_format_display(link_df[show_cols]), use_container_width=True)
