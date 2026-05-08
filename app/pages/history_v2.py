from __future__ import annotations
import streamlit as st
import pandas as pd
from app.upload_components import render_common_upload_inputs
from app.history_v2_store import init_history_v2_db, preview_history_import, commit_history_import, load_history_v2_tables, list_history_v2_batches, diagnose_history_v2_duplicates
from app.db_connection import get_backend_label
from app.analyzers import build_analysis_context
from app.pages import overview, links, products, specs, baibu_vs_normal, promotion, kpi_assessment, ai_decision

def render() -> None:
    st.subheader('历史数据分析 V2（周期覆盖）')
    st.info('历史数据分析 V2 采用“周期覆盖导入”：重复上传同一周期数据时，系统会先覆盖旧周期数据，再写入新数据，不会重复累计。')
    try:
        init_history_v2_db(); st.success(f'数据库后端：{get_backend_label()}，历史 V2 表初始化成功')
    except Exception as e:
        st.error(f'历史 V2 建表失败：{e}'); return
    uploaded = render_common_upload_inputs('history_v2')
    if st.button('预检本次历史导入'):
        st.session_state['history_v2_preview'] = preview_history_import(uploaded)
    p = st.session_state.get('history_v2_preview')
    if p:
        st.json(p)
        st.caption('此操作会覆盖同平台、同店铺、同日期范围的历史数据。')
        if st.button('确认覆盖导入历史数据库'):
            st.success(commit_history_import(uploaded, p).get('message','完成'))
    st.markdown('---')
    c1,c2=st.columns(2)
    with c1: ds=st.date_input('开始日期')
    with c2: de=st.date_input('结束日期')
    if st.button('从历史 V2 加载并分析'):
        tables = load_history_v2_tables(ds, de)
        if tables.get('orders', pd.DataFrame()).empty:
            st.warning('查询范围无数据'); return
        ctx=build_analysis_context(tables)
        overview.render(ctx['overview']); links.render(ctx['link_summary']); products.render(ctx['product_summary']); specs.render(ctx['spec_summary']); baibu_vs_normal.render(ctx['baibu_vs_normal']); promotion.render(ctx['promotion_analysis']);
        kpi_assessment.render({'说明':'历史V2已加载，请在主页面查看完整Q2指标'}); ai_decision.render(ctx=ctx, q2_result={'经营建议':'请结合主页面Q2目标查看'}, notes=[])
    st.markdown('---')
    st.write('最近导入批次')
    st.dataframe(list_history_v2_batches(20))
    d=diagnose_history_v2_duplicates(); st.json(d)
    if (d['orders_total']-d['orders_unique'])>0 or (d['promotion_total']-d['promotion_unique'])>0 or (d['cashflow_total']-d['cashflow_unique'])>0:
        st.warning('检测到重复 business_key，请检查导入数据。')
