"""AI经营决策页面。"""

from __future__ import annotations

import streamlit as st

from app.ai_context import build_ai_context
from app.llm_engine import call_llm
from app.prompt_builder import build_business_decision_prompt


def render(ctx: dict, q2_result: dict, notes: list | None = None) -> None:
    st.subheader("🤖 AI经营决策")
    st.caption("LLM 仅用于经营解读、原因归纳、动作建议与管理层汇报文案，不重算核心指标。")

    provider = st.selectbox("模型供应商", ["openai", "gemini", "deepseek"], index=0)
    default_model_map = {
        "openai": "gpt-4o-mini",
        "gemini": "gemini-1.5-pro",
        "deepseek": "deepseek-chat",
    }
    model_name = st.text_input("模型名称（可选覆盖）", value=default_model_map[provider])

    if st.button("生成AI经营决策", type="primary"):
        ai_context = build_ai_context(ctx=ctx, q2_result=q2_result, notes=notes)
        prompt = build_business_decision_prompt(ai_context)
        with st.spinner("正在生成经营建议，请稍候..."):
            try:
                result = call_llm(prompt=prompt, provider=provider, model_name=model_name.strip() or None)
                st.markdown(result)
            except ValueError as exc:
                st.warning(f"无法调用模型：{exc}。请在 Streamlit secrets 或环境变量中配置对应 API Key。")
            except Exception as exc:
                st.error(f"AI经营决策生成失败：{exc}")

    with st.expander("查看发送给模型的结构化数据（已压缩）", expanded=False):
        st.json(build_ai_context(ctx=ctx, q2_result=q2_result, notes=notes))
