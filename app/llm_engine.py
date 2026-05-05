"""LLM provider adapters for OpenAI, Gemini, and DeepSeek."""

from __future__ import annotations

import os

import requests
import streamlit as st
from openai import OpenAI
import google.generativeai as genai


SYSTEM_INSTRUCTION = "你是资深电商经营分析专家，擅长拼多多渠道、ROI、毛利、产品结构和经营复盘。"


def get_secret(name: str) -> str | None:
    """Read secret from Streamlit secrets first, then env vars."""
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value:
                return str(value)
    except Exception:
        # st.secrets may not be available in some local run contexts
        pass
    return os.getenv(name)


def call_openai(prompt: str, model_name: str = "gpt-4o-mini") -> str:
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未配置 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model_name,
            instructions=SYSTEM_INSTRUCTION,
            input=prompt,
            temperature=0.2,
            max_output_tokens=1800,
        )
        output_text = getattr(response, "output_text", "")
        if output_text:
            return output_text
        raise RuntimeError("OpenAI Responses API 返回为空")
    except Exception:
        fallback = client.chat.completions.create(
            model=model_name,
            temperature=0.2,
            max_tokens=1800,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
        )
        content = fallback.choices[0].message.content if fallback.choices else ""
        return content or ""


def call_gemini(prompt: str, model_name: str = "gemini-1.5-pro") -> str:
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("未配置 GEMINI_API_KEY")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name, system_instruction=SYSTEM_INSTRUCTION)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.2),
        )
        return (response.text or "").strip()
    except Exception as exc:
        raise RuntimeError(f"Gemini 调用失败: {exc}") from exc


def call_deepseek(prompt: str, model_name: str = "deepseek-chat") -> str:
    api_key = get_secret("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未配置 DEEPSEEK_API_KEY")

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1800,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def call_llm(prompt: str, provider: str, model_name: str | None = None) -> str:
    provider_norm = (provider or "").strip().lower()
    if provider_norm == "openai":
        return call_openai(prompt, model_name or "gpt-4o-mini")
    if provider_norm == "gemini":
        return call_gemini(prompt, model_name or "gemini-1.5-pro")
    if provider_norm == "deepseek":
        return call_deepseek(prompt, model_name or "deepseek-chat")
    raise ValueError("不支持的模型供应商")
