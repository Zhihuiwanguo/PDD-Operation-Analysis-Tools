"""艾兰得拼多多经营分析系统 - Streamlit MVP。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analyzers import build_analysis_context, compute_kpi_assessment
from app.config import CONFIG
from app.constants import DATE_CANDIDATE_COLUMNS, NUMERIC_COLUMNS, UPLOAD_SPECS
from app.data_loader import load_sample_tables, load_table
from app.database import (
    add_note,
    add_product_tag,
    get_notes,
    get_product_tags,
    init_db,
    load_config as load_config_db,
    load_latest_analysis as load_latest_analysis_db,
    save_analysis,
    save_config as save_config_db,
)
from app.exporters import to_excel_bytes
from app.report_pack import build_ppt_report_pack, to_ppt_report_pack_json
from app.storage import *
from app.pages import (
    baibu_vs_normal,
    business_alerts,
    kpi_assessment,
    exceptions,
    links,
    overview,
    products,
    promotion,
    specs,
    ai_decision,
)
from app.utils import to_numeric
from app.validators import validate_all

st.set_page_config(page_title="艾兰得拼多多经营分析系统", layout="wide")
st.title("艾兰得拼多多经营分析系统")
init_db()


def _prepare_tables(raw_tables):
    out = {}
    for key, df in raw_tables.items():
        out[key] = to_numeric(df, NUMERIC_COLUMNS.get(key, tuple()))
    return out


def _render_uploads() -> dict:
    st.header("A/B. 数据上传与校验")
    use_sample = st.checkbox("使用 sample_data 样例文件快速调试", value=True)

    if use_sample:
        st.info("当前使用 sample_data 样例文件。")
        tables = load_sample_tables(CONFIG.sample_data_dir)
    else:
        tables = {}
        for spec in UPLOAD_SPECS:
            file = st.file_uploader(
                f"上传{spec.label}",
                type=["csv", "xlsx", "xls"],
                key=f"upload_{spec.key}",
            )
            if file is not None:
                tables[spec.key] = load_table(file, file.name, key=spec.key)

    if not tables:
        st.warning("请上传全部必需文件后再分析。")
        return {}

    required_table_keys = {
        "product_master": "标准产品主档表",
        "sales_spec_mapping": "销售规格映射表",
        "link_spec_mapping": "店铺链接规格映射表",
        "orders": "拼多多原始订单表",
        "promotion": "拼多多推广汇总表",
    }

    missing_required = [
        label for key, label in required_table_keys.items() if key not in tables
    ]
    if missing_required:
        st.error("缺少必需数据表：" + "、".join(missing_required))
        st.info(
            "请上传完整的订单表、推广表、产品主档表、销售规格映射表、店铺链接规格映射表后再分析。"
        )
        st.stop()

    tables.setdefault("cashflow", pd.DataFrame())

    checks = validate_all(tables)
    st.subheader("校验结果")
    for r in checks:
        with st.container(border=True):
            st.markdown(f"**{r.label}**")
            st.write(f"记录数: {r.record_count}")
            date_cols = DATE_CANDIDATE_COLUMNS.get(r.key, tuple())
            if date_cols and r.date_min and r.date_max:
                st.write(f"日期范围: {r.date_min} ~ {r.date_max}")
            if r.ok:
                st.success("字段校验通过")
            else:
                st.error(f"缺失关键字段: {', '.join(r.missing_columns)}")
            if r.extra_message:
                st.warning(r.extra_message)

    if not all(r.ok for r in checks):
        st.stop()

    return _prepare_tables(tables)


def _build_global_filters(orders_df: pd.DataFrame) -> dict:
    st.sidebar.header("全局筛选器")

    date_ser = pd.to_datetime(
        orders_df.get("订单成交时间", "").replace({"\\t": ""}),
        errors="coerce",
    )
    if "支付时间" in orders_df.columns:
        pay_ser = pd.to_datetime(
            orders_df.get("支付时间", "").replace({"\\t": ""}),
            errors="coerce",
        )
        date_ser = date_ser.fillna(pay_ser)

    date_ser = date_ser.dropna()
    if not date_ser.empty:
        min_d, max_d = date_ser.min().date(), date_ser.max().date()
        date_range = st.sidebar.date_input(
            "日期范围（订单成交时间，空值回退支付时间）",
            value=(min_d, max_d),
        )
    else:
        date_range = None

    stores = sorted(
        orders_df.get("店铺名称", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    )
    products_opt = sorted(
        orders_df.get("标准产品名称", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    )
    goods_ids = sorted(
        orders_df.get("商品id", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    )
    bb_opts = sorted(
        orders_df.get("是否百补", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    )

    selected_stores = st.sidebar.multiselect("店铺名称", stores, default=stores)
    selected_products = st.sidebar.multiselect("标准产品名称", products_opt, default=products_opt)
    selected_goods = st.sidebar.multiselect("商品ID", goods_ids, default=goods_ids)
    selected_bb = st.sidebar.multiselect("是否百补", bb_opts, default=bb_opts)

    return {
        "date_range": date_range if isinstance(date_range, (tuple, list)) else None,
        "stores": selected_stores,
        "product_names": selected_products,
        "goods_ids": selected_goods,
        "baibu": selected_bb,
    }


def main() -> None:
    tables = _render_uploads()
    if not tables:
        return

    full_ctx = build_analysis_context(tables)
    filters = _build_global_filters(full_ctx["orders_enriched"])
    computed_ctx = build_analysis_context(tables, filters=filters)
    st.session_state.setdefault("current_ctx", computed_ctx)

    st.sidebar.markdown("---")
    st.sidebar.subheader("经营参数设置")
    cfg = load_config_db()
    q2_sales_target = st.sidebar.number_input("Q2销售目标", min_value=0.0, value=float(cfg.get("q2_sales_target", 0)), step=1000.0)
    q2_roi_target = st.sidebar.number_input("Q2 ROI目标", min_value=0.1, value=float(cfg.get("q2_roi_target", 1.0)), step=0.1)
    gross_margin_warn_pct = st.sidebar.number_input("毛利率预警线(%)", min_value=-100.0, max_value=100.0, value=float(cfg.get("gross_margin_warning", 0.5)), step=0.5)
    personal_score_pct = st.sidebar.number_input("个人指标得分(%)", min_value=0.0, max_value=200.0, value=float(cfg.get("personal_score", 100)), step=1.0)
    q2_remaining_days = st.sidebar.number_input("Q2剩余天数", min_value=1, value=30, step=1)

    if st.sidebar.button("保存经营配置"):
        save_config_db(
            {
                "q2_sales_target": float(q2_sales_target),
                "q2_roi_target": float(q2_roi_target),
                "gross_margin_warning": float(gross_margin_warn_pct),
                "personal_score": float(personal_score_pct),
            }
        )
        st.sidebar.success("经营配置已保存")

    if st.button("加载最近一次分析"):
        latest = load_latest_analysis_db()
        if latest is None:
            st.warning("未找到历史分析结果。")
        else:
            st.session_state["current_ctx"] = latest
            st.success("已加载最近一次分析。")

    if st.button("保存本次分析"):
        save_raw_data(computed_ctx["orders_enriched"], computed_ctx.get("promotion_df"))
        save_analysis_result(computed_ctx)
        save_analysis(computed_ctx)
        st.success("本次分析已保存。")

    ctx = st.session_state.get("current_ctx", computed_ctx)

    st.success("分析完成。")
    st.caption(f"当前日期筛选字段：{ctx['date_field_used']}")

    q2_result = compute_kpi_assessment(
        ctx["orders_enriched"],
        ctx["promotion_analysis"]["detail"],
        q2_sales_target=q2_sales_target,
        q2_roi_target=q2_roi_target,
        personal_score=personal_score_pct / 100.0,
        remaining_days=int(q2_remaining_days),
    )
    if q2_result["当前毛利率"] < gross_margin_warn_pct / 100.0:
        q2_result["经营建议"] = (
            "当前毛利率低于预警线，放量时要优先选择高毛利规格和ROI更接近目标的链接，"
            "避免为了冲销售额牺牲过多利润。\n"
            + q2_result["经营建议"]
        )

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs(
        [
            "经营总览",
            "链接分析",
            "产品分析",
            "规格分析",
            "百补 vs 日常",
            "推广分析",
            "经营异常",
            "异常清单",
            "Q2考核达成率",
            "🤖 AI经营决策",
        ]
    )

    with tab1:
        overview.render(ctx["overview"])
    with tab2:
        links.render(ctx["link_summary"])
    with tab3:
        products.render(ctx["product_summary"])
    with tab4:
        specs.render(ctx["spec_summary"])
    with tab5:
        baibu_vs_normal.render(ctx["baibu_vs_normal"])
    with tab6:
        promotion.render(ctx["promotion_analysis"])
    with tab7:
        business_alerts.render(ctx["business_alerts"])
    with tab8:
        exceptions.render(ctx["exceptions"])
        exceptions.render_mapping_coverage(ctx.get("mapping_coverage", pd.DataFrame()))
    with tab9:
        kpi_assessment.render(q2_result)
    with tab10:
        ai_decision.render(ctx=ctx, q2_result=q2_result, notes=get_notes()[:10])

    st.markdown("---")
    st.subheader("产品标签（简单版）")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        tag_product = st.text_input("产品名称", key="tag_product")
    with c2:
        tag_value = st.selectbox("标签", ["主推", "清库存", "高利润", "低ROI"], key="tag_value")
    with c3:
        st.write("")
        if st.button("为该产品添加标签"):
            if tag_product.strip():
                add_product_tag(tag_product.strip(), tag_value)
                st.success("产品标签已保存")
            else:
                st.warning("请先输入产品名称")

    if tag_product.strip():
        tags = get_product_tags(tag_product.strip())
        if tags:
            st.caption(f"当前产品已有标签：{', '.join(tags[:10])}")

    st.subheader("经营备注")
    n1, n2 = st.columns([1, 2])
    with n1:
        note_date = st.date_input("备注日期")
        note_type_cn = st.selectbox("类型", ["整体", "产品", "链接"])
    with n2:
        note_target = st.text_input("目标（产品名或链接名）")
        note_text = st.text_area("备注内容")

    note_type_map = {"整体": "overall", "产品": "product", "链接": "link"}
    if st.button("保存备注"):
        if note_text.strip():
            add_note(str(note_date), note_type_map[note_type_cn], note_target.strip(), note_text.strip())
            st.success("备注已保存")
        else:
            st.warning("备注内容不能为空")

    st.markdown("**最近10条备注**")
    recent_notes = get_notes()[:10]
    if recent_notes:
        st.table(pd.DataFrame(recent_notes))
    else:
        st.caption("暂无经营备注")

    export_payload = {
        "经营总览": pd.DataFrame([ctx["overview"]["metrics"]]),
        "经营总览-每日趋势": ctx["overview"]["daily_trend"],
        "链接分析": ctx["link_summary"],
        "产品分析": ctx["product_summary"],
        "规格分析": ctx["spec_summary"],
        "百补vs日常": ctx["baibu_vs_normal"],
        "推广分析-每日": ctx["promotion_analysis"]["daily"],
        "推广分析-商品汇总": ctx["promotion_analysis"]["goods"],
        "推广分析-单品明细": ctx["promotion_analysis"]["detail"],
        **{f"推广异常-{k}": v for k, v in ctx["promotion_analysis"]["anomalies"].items()},
        **{f"经营异常-{k}": v for k, v in ctx["business_alerts"].items()},
        **{f"异常-{k}": v for k, v in ctx["exceptions"].items()},
        "商品映射异常": ctx.get("mapping_coverage", pd.DataFrame()),
        "Q2考核达成率": pd.DataFrame([q2_result]),
    }

    excel_blob = to_excel_bytes(export_payload)

    st.download_button(
        "导出结果 Excel（当前筛选结果）",
        data=excel_blob,
        file_name="艾兰得拼多多经营分析系统_筛选结果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    report_pack = build_ppt_report_pack(ctx=ctx, q2_result=q2_result, filters=filters)
    report_pack_json = to_ppt_report_pack_json(report_pack)
    st.download_button(
        "导出 PPT 汇报数据包 JSON",
        data=report_pack_json,
        file_name="艾兰得拼多多经营分析报告_数据包.json",
        mime="application/json",
    )


if __name__ == "__main__":
    main()
