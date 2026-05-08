from __future__ import annotations

import streamlit as st


def render() -> None:
    st.subheader("历史数据管理")
    st.warning("历史数据库分析模式维护中，当前请使用单次上传分析。")
    st.caption("历史数据库相关代码已保留，待风险修复后再开放入口。")
