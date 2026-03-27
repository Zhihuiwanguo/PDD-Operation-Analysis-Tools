"""异常清单页。"""

from __future__ import annotations

import streamlit as st


def render(exceptions: dict):
    st.subheader("异常清单")
    for name, df in exceptions.items():
        st.markdown(f"#### {name}（{len(df)}）")
        st.dataframe(df, use_container_width=True)
