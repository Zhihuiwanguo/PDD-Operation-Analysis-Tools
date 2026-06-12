"""产品分析页。"""

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


def render(product_df, link_df: pd.DataFrame | None = None):
    st.subheader("产品分析（按标准产品名称）")

    if product_df is None or len(product_df) == 0:
        st.info("当前无产品分析数据。")
        return

    product_df = product_df.copy()

    st.markdown("### 一、产品经营概览")

    total_products = len(product_df)
    a_count = int((product_df["产品层级标签"] == "A层").sum()) if "产品层级标签" in product_df.columns else 0
    b_count = int((product_df["产品层级标签"] == "B层").sum()) if "产品层级标签" in product_df.columns else 0
    c_count = int((product_df["产品层级标签"] == "C层").sum()) if "产品层级标签" in product_df.columns else 0
    total_revenue = pd.to_numeric(product_df.get("商家实收", 0), errors="coerce").fillna(0).sum()
    total_profit = pd.to_numeric(product_df.get("扣推广后贡献毛利", 0), errors="coerce").fillna(0).sum()
    zero_series = pd.Series(0.0, index=product_df.index)
    total_store_discount = pd.to_numeric(product_df.get("店铺优惠", product_df.get("店铺设置优惠金额", zero_series)), errors="coerce").fillna(0).sum()
    total_settlement_coupon = pd.to_numeric(product_df.get("推广结算券", product_df.get("推广结算券金额", zero_series)), errors="coerce").fillna(0).sum()
    total_platform_discount = pd.to_numeric(product_df.get("平台优惠", product_df.get("平台优惠折扣", zero_series)), errors="coerce").fillna(0).sum()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("产品数", f"{total_products}")
    c2.metric("A层产品数", f"{a_count}")
    c3.metric("B层产品数", f"{b_count}")
    c4.metric("C层产品数", f"{c_count}")
    c5.metric("产品总商家实收", f"¥{total_revenue:,.2f}")
    c6.metric("产品总扣推广后毛利", f"¥{total_profit:,.2f}")

    d1, d2, d3 = st.columns(3)
    d1.metric("店铺优惠（拆券后）", f"¥{total_store_discount:,.2f}")
    d2.metric("推广结算券", f"¥{total_settlement_coupon:,.2f}")
    d3.metric("平台优惠", f"¥{total_platform_discount:,.2f}")
    st.caption("产品总扣推广后毛利仅扣推广成交花费；推广结算券已从店铺优惠中拆出展示，不作为利润项重复扣减。")

    st.markdown("---")
    st.markdown("### 二、产品经营明细")

    show_cols = [
        "标准产品名称",
        "产品层级标签",
        "有效订单数",
        "无效订单数",
        "待确认订单数",
        "非经营剔除订单数",
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
        "退款订单数",
        "退款率",
        "退款金额",
        "未发货退款订单数",
        "发货后退款订单数",
        "售后处理中订单数",
        "剔除退款后商家实收",
        "确认有效商家实收",
        "单均商家实收",
        "产品总成本",
        "快递总成本",
        "平台扣点",
        "订单侧估算毛利",
        "单均订单侧毛利",
        "订单侧毛利率",
        "推广成交花费",
        "结算券花费",
        "商品营销总花费",
        "链接推广费合计",
        "推广费率",
        "商品营销总费率",
        "结算券占店铺优惠比例",
        "扣推广后贡献毛利",
        "经营利润",
        "扣推广后毛利率",
        "经营利润率",
        "实际ROI",
        "盈亏平衡ROI",
        "百补商家实收",
        "日常商家实收",
        "百补销售占比",
        "日常销售占比",
        "百补有效订单数",
        "日常有效订单数",
    ]
    show_cols = [c for c in show_cols if c in product_df.columns]

    product_show = _format_percent_columns(
        product_df[show_cols],
        ["订单侧毛利率", "推广费率", "商品营销总费率", "结算券占店铺优惠比例", "扣推广后毛利率", "经营利润率", "百补销售占比", "日常销售占比", "退款率"],
    )

    st.dataframe(product_show, use_container_width=True)

    st.markdown("---")
    st.markdown("### 三、商品ID经营明细")
    if link_df is None or len(link_df) == 0:
        st.info("当前无商品ID层面产品分析数据。")
    else:
        link_df = link_df.copy()
        link_cols = [
            "商品ID",
            "链接标题",
            "标准产品名称",
            "有效订单数",
            "商品件数",
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
            "订单侧估算毛利",
            "推广成交花费",
            "商品营销总花费",
            "扣推广后贡献毛利",
            "经营利润",
            "扣推广后利润率",
            "实际ROI",
        ]
        link_cols = [c for c in link_cols if c in link_df.columns]
        link_show = _format_percent_columns(link_df[link_cols], ["扣推广后利润率"])
        st.caption("推广结算券从店铺优惠中拆出展示；扣推广后贡献毛利仅扣推广成交花费，不重复扣结算券。")
        st.dataframe(link_show, use_container_width=True)

    st.markdown("---")
    st.markdown("### 四、产品层级结构")

    if {"产品层级标签", "标准产品名称"}.issubset(product_df.columns):
        tier_df = (
            product_df.groupby("产品层级标签", dropna=False)
            .agg(
                产品数=("标准产品名称", "count"),
                商家实收=("商家实收", "sum"),
                扣推广后贡献毛利=("扣推广后贡献毛利", "sum"),
            )
            .reset_index()
        )
        st.dataframe(tier_df, use_container_width=True)

    st.markdown("---")
    st.markdown("### 五、重点产品提示")

    top_revenue = (
        product_df.sort_values("商家实收", ascending=False)
        .head(10)[["标准产品名称", "商家实收", "扣推广后贡献毛利", "实际ROI"]]
        if {"标准产品名称", "商家实收", "扣推广后贡献毛利", "实际ROI"}.issubset(product_df.columns)
        else pd.DataFrame()
    )

    loss_products = (
        product_df[product_df["扣推广后贡献毛利"] < 0]
        .sort_values("扣推广后贡献毛利")
        [["标准产品名称", "商家实收", "链接推广费合计", "扣推广后贡献毛利", "实际ROI"]]
        if {"标准产品名称", "商家实收", "链接推广费合计", "扣推广后贡献毛利", "实际ROI"}.issubset(product_df.columns)
        else pd.DataFrame()
    )

    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown("#### 商家实收TOP产品")
        if top_revenue.empty:
            st.info("当前无重点产品数据。")
        else:
            st.dataframe(top_revenue, use_container_width=True)

    with right_col:
        st.markdown("#### 扣推广后亏损产品")
        if loss_products.empty:
            st.info("当前无扣推广后亏损产品。")
        else:
            st.dataframe(loss_products, use_container_width=True)
