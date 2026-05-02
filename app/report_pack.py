"""PPT 汇报数据包构建。"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import pandas as pd


def _to_records_top_n(obj: Any, limit: int = 10) -> list[dict]:
    if isinstance(obj, pd.DataFrame):
        if obj.empty:
            return []
        return obj.head(limit).to_dict(orient="records")
    return []


def build_ppt_report_pack(ctx: dict, q2_result: dict, filters: dict | None = None) -> dict:
    """将当前筛选后的经营分析结果整理为 PPT 可消费的 JSON 结构。"""
    overview_metrics = ctx.get("overview", {}).get("metrics", {})

    link_top = _to_records_top_n(ctx.get("link_summary", pd.DataFrame()))
    product_top = _to_records_top_n(ctx.get("product_summary", pd.DataFrame()))
    baibu_vs_normal = _to_records_top_n(ctx.get("baibu_vs_normal", pd.DataFrame()))

    exceptions_ctx = ctx.get("exceptions", {})
    exception_table = _to_records_top_n(exceptions_ctx.get("exception_rows", pd.DataFrame()))
    if not exception_table:
        exception_table = _to_records_top_n(exceptions_ctx.get("rows", pd.DataFrame()))

    advice_text = str(q2_result.get("经营建议", "")).strip()
    advice_bullets = [line.strip("-• ") for line in advice_text.splitlines() if line.strip()]

    gap_fields = [
        "销售额达成率",
        "ROI达成率",
        "销售额缺口",
        "达标所需日均销售额",
        "剩余天数",
    ]
    gap_bullets = [f"{key}: {q2_result[key]}" for key in gap_fields if key in q2_result]

    return {
        "report_meta": {
            "report_title": "艾兰得拼多多经营分析报告",
            "channel": "拼多多",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "date_field_used": ctx.get("date_field_used"),
            "filters": filters or {},
        },
        "summary": {
            "overview_metrics": overview_metrics,
            "q2_kpi": q2_result,
        },
        "slides": [
            {
                "type": "cover",
                "title": "艾兰得拼多多经营分析报告",
                "subtitle": "经营总览 / Q2考核 / 推广效率 / 异常清单",
            },
            {
                "type": "kpi",
                "title": "经营总览",
                "metrics": overview_metrics,
            },
            {
                "type": "kpi",
                "title": "Q2考核达成率",
                "metrics": q2_result,
            },
            {
                "type": "content",
                "title": "达标缺口测算",
                "bullets": gap_bullets,
            },
            {
                "type": "table",
                "title": "产品表现 Top",
                "table": product_top,
            },
            {
                "type": "table",
                "title": "链接表现 Top",
                "table": link_top,
            },
            {
                "type": "table",
                "title": "百补 vs 日常",
                "table": baibu_vs_normal,
            },
            {
                "type": "table",
                "title": "经营异常清单",
                "table": exception_table,
            },
            {
                "type": "summary",
                "title": "下阶段经营建议",
                "bullets": advice_bullets,
            },
        ],
    }


def to_ppt_report_pack_json(pack: dict) -> str:
    """输出中文友好的 JSON 字符串。"""
    return json.dumps(pack, ensure_ascii=False, indent=2, default=str)
