"""异常清单页。"""

from __future__ import annotations

import streamlit as st


def _empty_message(name: str) -> str:
    return f"当前无{name}"


def render(exceptions: dict):
    st.subheader("异常清单")
    for name, df in exceptions.items():
        st.markdown(f"#### {name}（{len(df)}）")
        if len(df) == 0:
            st.success(_empty_message(name))
            continue
        st.dataframe(df, use_container_width=True)
