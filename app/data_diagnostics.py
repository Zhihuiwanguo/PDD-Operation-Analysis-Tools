"""数据质量诊断模块。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd


_ORDER_DATE_CANDIDATES = ["订单成交时间", "支付时间"]
_PROMOTION_DATE_CANDIDATES = ["日期", "统计日期", "开始日期", "结束日期", "推广日期"]


def _safe_df(tables: dict, key: str) -> pd.DataFrame:
    df = tables.get(key)
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _date_range(df: pd.DataFrame, candidates: list[str]) -> tuple[str | None, str | None]:
    if df.empty:
        return None, None

    date_ser = None
    for col in candidates:
        if col in df.columns:
            ser = pd.to_datetime(df[col], errors="coerce")
            date_ser = ser if date_ser is None else date_ser.fillna(ser)

    if date_ser is None:
        return None, None

    date_ser = date_ser.dropna()
    if date_ser.empty:
        return None, None
    return str(date_ser.min().date()), str(date_ser.max().date())


def build_upload_batch_info(tables: dict) -> dict:
    table_labels = {
        "orders": "拼多多原始订单表",
        "promotion": "拼多多推广汇总表",
        "product_master": "艾兰得标准产品主档表",
        "sales_spec_mapping": "艾兰得销售规格映射表",
        "link_spec_mapping": "拼多多艾兰得店铺链接规格映射表",
    }

    out_tables: dict[str, dict] = {}
    for key, table_name in table_labels.items():
        df = _safe_df(tables, key)
        if key == "orders":
            date_min, date_max = _date_range(df, _ORDER_DATE_CANDIDATES)
        elif key == "promotion":
            date_min, date_max = _date_range(df, _PROMOTION_DATE_CANDIDATES)
        else:
            date_min, date_max = None, None

        out_tables[key] = {
            "table_name": table_name,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "date_min": date_min,
            "date_max": date_max,
        }

    return {
        "batch_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "tables": out_tables,
    }


def check_order_promotion_date_consistency(tables: dict) -> dict:
    orders = _safe_df(tables, "orders")
    promotion = _safe_df(tables, "promotion")

    o_min, o_max = _date_range(orders, _ORDER_DATE_CANDIDATES)
    p_min, p_max = _date_range(promotion, _PROMOTION_DATE_CANDIDATES)

    def _to_ts(s):
        return pd.to_datetime(s, errors="coerce") if s else pd.NaT

    o_min_ts, o_max_ts, p_min_ts, p_max_ts = map(_to_ts, [o_min, o_max, p_min, p_max])

    same = all(pd.notna(v) for v in [o_min_ts, o_max_ts, p_min_ts, p_max_ts]) and o_min_ts == p_min_ts and o_max_ts == p_max_ts

    if pd.isna(o_min_ts) or pd.isna(o_max_ts) or pd.isna(p_min_ts) or pd.isna(p_max_ts):
        risk = "中"
        msg = "订单或推广缺少可识别日期范围，日期不一致会导致 ROI、推广费率、扣推广后毛利失真。"
        advice = "请核对订单/推广表日期字段是否完整，并统一统计区间后重算。"
        same = False
    elif same:
        risk = "正常"
        msg = "订单与推广日期范围一致，可用于稳定计算 ROI、推广费率、扣推广后毛利。"
        advice = "保持当前上传口径，继续监控后续批次日期一致性。"
    else:
        overlap = not (o_max_ts < p_min_ts or p_max_ts < o_min_ts)
        if overlap:
            risk = "中"
            msg = "订单与推广日期范围仅部分重叠，日期不一致会导致 ROI、推广费率、扣推广后毛利失真。"
            advice = "建议统一订单与推广统计区间，避免部分日期缺失引发偏差。"
        else:
            risk = "高"
            msg = "订单与推广日期范围完全不重叠，日期不一致会导致 ROI、推广费率、扣推广后毛利严重失真。"
            advice = "请立即检查上传批次是否错月或错表，并重新上传同周期订单与推广数据。"

    return {
        "订单日期开始": o_min,
        "订单日期结束": o_max,
        "推广日期开始": p_min,
        "推广日期结束": p_max,
        "是否一致": bool(same),
        "风险等级": risk,
        "风险说明": msg,
        "处理建议": advice,
    }


def diagnose_sales_difference(ctx: dict, full_ctx: dict | None = None) -> dict:
    cur_sales = float(ctx.get("overview", {}).get("metrics", {}).get("商家实收", 0) or 0)

    base_ctx = full_ctx if isinstance(full_ctx, dict) else ctx
    orders = base_ctx.get("orders_enriched", pd.DataFrame())
    orders = orders.copy() if isinstance(orders, pd.DataFrame) else pd.DataFrame()

    pay_col = "商家实收金额(元)" if "商家实收金额(元)" in orders.columns else "商家实收"
    if pay_col not in orders.columns:
        orders[pay_col] = 0
    orders[pay_col] = pd.to_numeric(orders[pay_col], errors="coerce").fillna(0.0)

    status_col = "订单状态"
    if status_col not in orders.columns:
        status_col = ""

    status_ser = orders[status_col].astype(str) if status_col else pd.Series("", index=orders.index)
    invalid_mask = status_ser.str.contains("无效", na=False)
    pending_mask = status_ser.str.contains("待确认|确认中", na=False)
    non_operating_mask = orders.get("商品", pd.Series("", index=orders.index)).astype(str).str.contains("差价补款", na=False)

    valid_mask = ~invalid_mask & ~pending_mask & ~non_operating_mask
    raw_valid_sales = float(orders.loc[valid_mask, pay_col].sum())

    std_name = orders.get("标准产品名称", pd.Series("", index=orders.index)).astype(str).str.strip()
    spec_id = orders.get("销售规格ID", pd.Series("", index=orders.index)).astype(str).str.strip()
    std_id = orders.get("标准产品ID", pd.Series("", index=orders.index)).astype(str).str.strip()
    unmapped_mask = valid_mask & ((std_name == "") | (spec_id == "") | (std_id == ""))

    unmapped_sales = float(orders.loc[unmapped_mask, pay_col].sum())
    invalid_sales = float(orders.loc[invalid_mask, pay_col].sum())
    pending_sales = float(orders.loc[pending_mask, pay_col].sum())
    non_operating_sales = float(orders.loc[non_operating_mask, pay_col].sum())

    diff_amount = raw_valid_sales - cur_sales
    diff_rate = (diff_amount / raw_valid_sales) if raw_valid_sales else 0.0
    excluded_sales = max(diff_amount, 0.0)

    if diff_amount > 0:
        conclusion = "当前分析商家实收低于原始有效订单商家实收，存在筛选或映射导致的可解释差异。"
        advice = "优先检查全局筛选器、未映射商品、日期筛选范围是否缩小了可计入口径。"
    elif diff_amount < 0:
        conclusion = "当前分析商家实收高于原始有效订单商家实收，请核对有效订单识别与汇总来源。"
        advice = "建议复核订单状态字段、异常剔除项与导入数据完整性。"
    else:
        conclusion = "当前分析商家实收与原始有效订单商家实收一致。"
        advice = "暂无明显差异，建议持续关注新批次映射完整性。"

    return {
        "原始有效订单商家实收": raw_valid_sales,
        "当前分析商家实收": cur_sales,
        "差异金额": diff_amount,
        "差异率": diff_rate,
        "未映射订单商家实收": unmapped_sales,
        "筛选排除商家实收": excluded_sales,
        "无效订单商家实收": invalid_sales,
        "待确认订单商家实收": pending_sales,
        "非经营剔除商家实收": non_operating_sales,
        "诊断结论": conclusion,
        "处理建议": advice,
    }


def build_mapping_maintenance_lists(mapping_coverage: pd.DataFrame) -> dict:
    df = mapping_coverage.copy() if isinstance(mapping_coverage, pd.DataFrame) else pd.DataFrame()
    if "商家实收金额" not in df.columns:
        df["商家实收金额"] = 0.0
    df["商家实收金额"] = pd.to_numeric(df["商家实收金额"], errors="coerce").fillna(0.0)

    def _build(mask_types: list[str], cols: list[str]) -> pd.DataFrame:
        if df.empty or "异常类型" not in df.columns:
            return pd.DataFrame(columns=cols)
        out = df[df["异常类型"].astype(str).isin(mask_types)].copy()
        if out.empty:
            return pd.DataFrame(columns=cols)
        for col in cols:
            if col not in out.columns:
                out[col] = ""
        out = out[cols].drop_duplicates()
        if "商家实收金额" in out.columns:
            out = out.sort_values("商家实收金额", ascending=False)
        return out.reset_index(drop=True)

    link_cols = ["商品ID", "商品名称", "商品规格", "销售规格ID", "是否百补", "订单数", "商家实收金额", "处理建议"]
    sales_cols = ["销售规格ID", "商品ID", "商品规格", "标准产品ID", "规格名称", "销售数量", "产品总成本", "快递费", "订单数", "商家实收金额", "处理建议"]
    product_cols = ["标准产品ID", "标准产品名称", "单规格", "单个产品成本", "处理建议"]

    return {
        "待维护店铺链接规格映射表": _build(["新商品ID未维护", "商品规格未维护", "销售规格ID缺失"], link_cols),
        "待维护销售规格映射表": _build(["销售规格ID未维护", "成本信息缺失"], sales_cols),
        "待维护标准产品主档表": _build(["标准产品ID未维护"], product_cols),
    }
