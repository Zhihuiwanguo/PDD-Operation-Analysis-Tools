from __future__ import annotations

import streamlit as st

from app.history_store import get_database_url, get_history_stats, list_upload_batches


def render() -> None:
    st.subheader("历史数据管理")
    db_url = get_database_url()
    backend = "PostgreSQL / Supabase" if "postgres" in db_url else "SQLite"
    st.info(f"当前数据库后端：{backend}")
    if backend == "SQLite":
        st.warning("SQLite 仅适合测试，长期使用请配置 Supabase/PostgreSQL 的 DATABASE_URL。")

    st.caption("重复上传同一周期数据时，系统将按业务唯一键自动更新已有记录，不会重复累计。")
    stats = get_history_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("历史订单总行数", stats.get("order_count", 0), f"{stats.get('order_min') or '-'} ~ {stats.get('order_max') or '-'}")
    c2.metric("历史推广总行数", stats.get("promo_count", 0), f"{stats.get('promo_min') or '-'} ~ {stats.get('promo_max') or '-'}")
    c3.metric("历史推广流水总行数", stats.get("cashflow_count", 0), f"{stats.get('cashflow_min') or '-'} ~ {stats.get('cashflow_max') or '-'}")

    batches = list_upload_batches(100)
    st.markdown("#### 最近上传批次")
    if batches.empty:
        st.info("暂无历史上传批次。")
    else:
        st.dataframe(batches, use_container_width=True)
