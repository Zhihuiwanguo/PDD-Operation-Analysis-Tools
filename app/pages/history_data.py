from __future__ import annotations

import streamlit as st

from app.history_store import get_history_stats, list_upload_batches


def render() -> None:
    st.subheader("历史数据管理")
    stats = get_history_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("历史订单总行数", stats.get("order_count", 0))
    c2.metric("历史推广总行数", stats.get("promo_count", 0))
    c3.metric("历史订单日期范围", f"{stats.get('order_min') or '-'} ~ {stats.get('order_max') or '-'}")
    c4.metric("历史推广日期范围", f"{stats.get('promo_min') or '-'} ~ {stats.get('promo_max') or '-'}")

    batches = list_upload_batches(100)
    st.markdown("#### 最近上传批次")
    if batches.empty:
        st.info("暂无历史上传批次。")
    else:
        st.dataframe(batches, use_container_width=True)
