"""异常清单页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render(exceptions: dict):
    st.subheader("异常清单")

    for name, df in exceptions.items():
        if df is None:
            df = pd.DataFrame()

        st.markdown(f"#### {name}（{len(df)}）")

        if len(df) == 0:
            st.info(f"当前无{name}")
        else:
            st.dataframe(df, use_container_width=True)
