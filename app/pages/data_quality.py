from __future__ import annotations

import pandas as pd
import streamlit as st


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def render(ctx: dict) -> None:
    st.subheader("数据质量检查")

    st.markdown("### 上传数据批次识别")
    batch = ctx.get("upload_batch_info", {})
    st.write(f"批次 ID：{batch.get('batch_id', '-')}")
    rows = []
    for key, info in (batch.get("tables") or {}).items():
        rows.append({
            "表名": info.get("table_name", key),
            "记录数": info.get("rows", 0),
            "字段数": info.get("columns", 0),
            "日期开始": info.get("date_min"),
            "日期结束": info.get("date_max"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.markdown("### 订单/推广日期一致性检查")
    dc = ctx.get("date_consistency", {})
    risk = dc.get("风险等级", "中")
    if risk == "高":
        st.error(dc.get("风险说明", ""))
    elif risk == "中":
        st.warning(dc.get("风险说明", ""))
    else:
        st.success(dc.get("风险说明", ""))
    st.table(pd.DataFrame([dc]))

    st.markdown("### 数据差异诊断")
    sd = ctx.get("sales_difference_diagnosis", {})
    show_keys = ["原始有效订单商家实收", "当前分析商家实收", "差异金额", "差异率", "未映射订单商家实收", "筛选排除商家实收", "无效订单商家实收", "待确认订单商家实收"]
    st.table(pd.DataFrame([{k: sd.get(k) for k in show_keys}]))
    if float(sd.get("差异金额", 0) or 0) > 0:
        st.warning("当前分析商家实收低于原始有效订单商家实收，请优先检查全局筛选器和商品映射异常。")

    st.markdown("### 商品映射待维护清单")
    lists = ctx.get("mapping_maintenance_lists", {})
    names = ["待维护店铺链接规格映射表", "待维护销售规格映射表", "待维护标准产品主档表"]
    for name in names:
        df = lists.get(name, pd.DataFrame())
        st.markdown(f"#### {name}")
        if not isinstance(df, pd.DataFrame) or df.empty:
            st.info("暂无待维护项。")
        else:
            st.dataframe(df, use_container_width=True)
            st.download_button(f"下载{name}.csv", data=_to_csv_bytes(df), file_name=f"{name}.csv", mime="text/csv")
