"""艾兰得拼多多经营分析系统 - Streamlit MVP。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analyzers import build_analysis_context, compute_kpi_assessment
from app.config import CONFIG
from app.constants import DATE_CANDIDATE_COLUMNS, NUMERIC_COLUMNS, UPLOAD_SPECS
from app.data_loader import load_sample_tables, load_table
from app.exporters import to_excel_bytes
from app.report_pack import build_ppt_report_pack, to_ppt_report_pack_json
from app.pages import (
    baibu_vs_normal,
    business_alerts,
    creative_material,
    kpi_assessment,
    exceptions,
    links,
    overview,
    products,
    promotion,
    specs,
)
from app.utils import to_numeric
from app.validators import validate_all

st.set_page_config(page_title="艾兰得拼多多经营分析系统", layout="wide")
st.title("艾兰得拼多多经营分析系统")


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
    ctx = build_analysis_context(tables, filters=filters)

    st.success("分析完成。")
    st.caption(f"当前日期筛选字段：{ctx['date_field_used']}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Q2考核参数")
    q2_sales_target = st.sidebar.number_input("Q2销售目标", min_value=0.0, value=0.0, step=1000.0)
    q2_roi_target = st.sidebar.number_input("Q2 ROI目标", min_value=0.1, value=1.9, step=0.1)
    q2_remaining_days = st.sidebar.number_input("Q2剩余天数", min_value=1, value=30, step=1)
    personal_score_pct = st.sidebar.number_input("个人指标得分(%)", min_value=0.0, max_value=200.0, value=100.0, step=1.0)
    gross_margin_warn_pct = st.sidebar.number_input("毛利率预警线(%)", min_value=-100.0, max_value=100.0, value=0.0, step=0.5)

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
            "推广素材分析",
            "经营异常",
            "异常清单",
            "Q2考核达成率",
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
        creative_material.render(ctx["creative_material_analysis"])
    with tab8:
        business_alerts.render(ctx["business_alerts"])
    with tab9:
        exceptions.render(ctx["exceptions"])
    with tab10:
        kpi_assessment.render(q2_result)

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
        "Q2考核达成率": pd.DataFrame([q2_result]),
    }

    creative_ctx = ctx.get("creative_material_analysis", {})
    if creative_ctx:
        export_payload.update(
            {
                "推广素材分析-商品ID汇总": creative_ctx.get("goods_rollup", pd.DataFrame()),
                "推广素材分析-素材明细": creative_ctx.get("material_detail", pd.DataFrame()),
                "推广素材分析-素材类型汇总": creative_ctx.get("type_summary", pd.DataFrame()),
                **{
                    f"推广素材异常-{k}": v
                    for k, v in creative_ctx.get("anomalies", {}).items()
                },
            }
        )

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
