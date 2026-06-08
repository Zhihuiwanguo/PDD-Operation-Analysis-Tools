"""价格链路与店铺优惠拆分页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render(price_chain_df: pd.DataFrame) -> None:
    st.subheader("价格链路分析 / 店铺优惠拆分")
    st.caption("商品总价 → 店铺优惠 → 平台优惠 → 用户实付 → 商家实收；店铺优惠进一步拆为推广结算券 + 店铺设置优惠。")

    if price_chain_df is None or price_chain_df.empty:
        st.info("当前无价格链路数据。")
        return

    df = price_chain_df.copy()
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce").dt.date

    c1, c2, c3 = st.columns(3)
    stores = sorted(df.get("店铺", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    products = sorted(df.get("标准产品", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    goods_ids = sorted(df.get("商品ID", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    selected_stores = c1.multiselect("店铺", stores, default=stores)
    selected_products = c2.multiselect("标准产品", products, default=products)
    selected_goods = c3.multiselect("商品ID", goods_ids, default=goods_ids)

    if selected_stores:
        df = df[df["店铺"].astype(str).isin(selected_stores)]
    if selected_products:
        df = df[df["标准产品"].astype(str).isin(selected_products)]
    if selected_goods:
        df = df[df["商品ID"].astype(str).isin(selected_goods)]

    st.markdown("### 汇总指标")
    totals = df[[c for c in ["商品总价", "店铺优惠折扣", "平台优惠折扣", "用户实付金额", "商家实收金额", "推广结算券金额", "店铺设置优惠金额", "推广成交花费", "商品营销总花费"] if c in df.columns]].sum(numeric_only=True)
    cols = st.columns(3)
    for idx, (key, val) in enumerate(totals.items()):
        cols[idx % 3].metric(key, f"¥{val:,.2f}")

    st.markdown("### 明细")
    show_cols = [c for c in [
        "日期", "店铺", "商品ID", "商品名称", "标准产品", "商品总价", "店铺优惠折扣", "平台优惠折扣",
        "用户实付金额", "商家实收金额", "推广结算券金额", "店铺设置优惠金额", "推广成交花费", "商品营销总花费", "是否异常",
    ] if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)

    abnormal = df[df.get("是否异常", "否") != "否"] if "是否异常" in df.columns else pd.DataFrame()
    if not abnormal.empty:
        st.warning("存在店铺设置优惠金额 < 0 的行，已标记为“口径差异/退款结算差异”，可能由取消、退款或结算周期差异导致。")
        st.dataframe(abnormal[show_cols], use_container_width=True)
