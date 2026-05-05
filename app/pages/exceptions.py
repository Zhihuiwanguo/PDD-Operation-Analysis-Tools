"""异常清单 / 底表诊断页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st


SECTION_CONFIG = {
    "映射与底表诊断": [
        "未映射规格",
        "未映射商品ID",
        "重复映射",
        "链接映射多候选风险",
        "百补字段缺失提示",
    ],
    "推广挂接诊断": [
        "有订单无推广费",
        "有推广费无订单",
        "推广费挂接异常",
    ],
    "订单特殊项诊断": [
        "差价补款商品",
        "待确认订单",
    ],
}

DESC_CONFIG = {
    "未映射规格": "订单中的 商品ID + 商品规格 未能稳定映射到销售规格ID，优先检查链接规格映射表是否缺少历史别名。",
    "未映射商品ID": "订单侧或推广侧出现了映射表中不存在的商品ID，说明链接映射表未覆盖完整。",
    "重复映射": "同一个商品ID下，同一个商品规格 + 销售规格ID 出现多条记录，属于底表重复维护问题。",
    "链接映射多候选风险": "同一订单特征可能匹配到多个链接规格候选，存在错误归因风险。",
    "百补字段缺失提示": "部分记录缺失是否百补识别字段，可能影响百补 / 日常拆分结果。",
    "有订单无推广费": "订单侧存在有效成交，但推广侧未挂到对应商品ID，需判断是自然单、漏投放数据，还是商品ID挂接失败。",
    "有推广费无订单": "推广侧存在花费，但订单侧没有对应商品ID成交，需判断是纯消耗未转化，还是订单 / 映射缺失。",
    "推广费挂接异常": "推广商品ID存在异常，常见原因是商品ID非法、未在映射表中、或订单侧无该商品ID。",
    "差价补款商品": "当前已被系统识别为非经营剔除项，不纳入经营分析主指标。",
    "待确认订单": "售后处理中订单，单独列示，不并入有效也不直接判无效。",
}


def _ensure_df(obj) -> pd.DataFrame:
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    return pd.DataFrame(obj)


def _render_overview_cards(exceptions: dict) -> None:
    unmapped_specs = len(_ensure_df(exceptions.get("未映射规格")))
    unmapped_goods = len(_ensure_df(exceptions.get("未映射商品ID")))
    duplicate_mapping = len(_ensure_df(exceptions.get("重复映射")))
    promo_attach_issues = len(_ensure_df(exceptions.get("推广费挂接异常")))
    pending_orders = len(_ensure_df(exceptions.get("待确认订单")))
    diff_price_items = len(_ensure_df(exceptions.get("差价补款商品")))

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("未映射规格", f"{unmapped_specs}")
    c2.metric("未映射商品ID", f"{unmapped_goods}")
    c3.metric("重复映射", f"{duplicate_mapping}")
    c4.metric("推广挂接异常", f"{promo_attach_issues}")
    c5.metric("待确认订单", f"{pending_orders}")
    c6.metric("差价补款商品", f"{diff_price_items}")


def _render_section(title: str, names: list[str], exceptions: dict) -> None:
    st.markdown(f"### {title}")

    for name in names:
        df = _ensure_df(exceptions.get(name))
        desc = DESC_CONFIG.get(name, "")

        st.markdown(f"#### {name}（{len(df)}）")
        if desc:
            st.caption(desc)

        if len(df) == 0:
            st.info(f"当前无{name}")
            continue

        st.dataframe(df, use_container_width=True)
        st.markdown("---")


def render(exceptions: dict):
    st.subheader("异常清单 / 底表诊断")
    st.caption("本页用于区分经营问题、映射问题、推广挂接问题。优先先看底表与映射异常，再解释经营结果。")

    _render_overview_cards(exceptions)

    st.markdown("---")

    for section_title, names in SECTION_CONFIG.items():
        _render_section(section_title, names, exceptions)

    # 兜底：防止后续分析层新增了异常项，但这里还没手动归类
    known_names = {name for names in SECTION_CONFIG.values() for name in names}
    extra_names = [name for name in exceptions.keys() if name not in known_names]

    if extra_names:
        st.markdown("### 其他异常项")
        for name in extra_names:
            df = _ensure_df(exceptions.get(name))
            st.markdown(f"#### {name}（{len(df)}）")
            if len(df) == 0:
                st.info(f"当前无{name}")
            else:
                st.dataframe(df, use_container_width=True)
            st.markdown("---")


def render_mapping_coverage(mapping_coverage: pd.DataFrame) -> None:
    st.markdown("### 商品ID / 规格映射异常")
    st.caption("该模块默认基于全部上传订单表识别映射覆盖问题，不受当前筛选器影响。")

    df = _ensure_df(mapping_coverage)
    if df.empty:
        st.info("未发现商品ID / 商品规格映射异常。")
        return

    high_count = int((df.get("异常优先级", pd.Series(dtype=str)).astype(str) == "高").sum())
    if high_count > 0:
        st.warning(f"存在 {high_count} 条高优先级映射异常，建议优先修复。")

    c1, c2, c3 = st.columns(3)
    c1.metric("异常总数", f"{len(df)}")
    c2.metric("涉及商品ID数量", f"{df['商品ID'].astype(str).nunique()}")
    c3.metric("涉及商家实收金额", f"{pd.to_numeric(df['商家实收金额'], errors='coerce').fillna(0).sum():,.2f}")

    show_cols = [
        "异常类型",
        "异常优先级",
        "商品ID",
        "商品名称",
        "商品规格",
        "销售规格ID",
        "标准产品ID",
        "订单数",
        "商家实收金额",
        "风险说明",
        "处理建议",
    ]
    present_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[present_cols], use_container_width=True)
