"""通用上传组件。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_loader import load_table
from app.validators import detect_promotion_columns

UPLOAD_FILE_TYPES = ["csv", "xls", "xlsx"]


def render_common_upload_inputs(mode_key: str = "common") -> dict:
    st.markdown("### 经营主数据")

    result: dict[str, pd.DataFrame | dict[str, str]] = {}
    file_names: dict[str, str] = {}

    upload_defs = [
        ("orders", "订单明细上传"),
        ("product_master", "标准产品主档上传"),
        ("sales_spec_mapping", "商品规格映射上传"),
        ("link_spec_mapping", "店铺链接规格映射上传"),
    ]

    for key, label in upload_defs:
        f = st.file_uploader(label, type=UPLOAD_FILE_TYPES, key=f"upload_{mode_key}_{key}")
        if f is not None:
            result[key] = load_table(f, f.name, key=key)
            file_names[key] = f.name

    st.markdown("### 推广数据")
    promo = st.file_uploader("每日商品ID推广数据上传", type=UPLOAD_FILE_TYPES, key=f"upload_{mode_key}_promotion")
    if promo is not None:
        result["promotion"] = load_table(promo, promo.name, key="promotion")
        file_names["promotion"] = promo.name
        promo_fields = detect_promotion_columns(result["promotion"])
        st.caption(f"识别到的日期字段：{promo_fields.get('date') or '未识别'}")
        st.caption(f"识别到的商品ID字段：{promo_fields.get('goods_id') or '未识别'}")
        st.caption(f"识别到的推广费字段：{promo_fields.get('spend') or '未识别'}")
        if not all(promo_fields.values()):
            st.caption("当前实际列名：" + "、".join(map(str, result["promotion"].columns.tolist())))

    cashflow = st.file_uploader("店铺每日推广费流水上传", type=UPLOAD_FILE_TYPES, key=f"upload_{mode_key}_cashflow")
    if cashflow is not None:
        result["cashflow"] = load_table(cashflow, cashflow.name, key="cashflow")
        file_names["cashflow"] = cashflow.name

    result["_file_names"] = file_names
    return result
