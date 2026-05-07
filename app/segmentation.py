"""经营分层分析。"""

from __future__ import annotations

import pandas as pd


def _to_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def segment_products(product_df: pd.DataFrame) -> pd.DataFrame:
    if product_df is None or product_df.empty:
        return pd.DataFrame()

    out = product_df.copy()

    out["商家实收"] = _to_numeric(out, "商家实收")
    out["有效订单数"] = _to_numeric(out, "有效订单数")
    out["实际ROI"] = _to_numeric(out, "实际ROI")
    out["盈亏平衡ROI"] = _to_numeric(out, "盈亏平衡ROI")
    out["扣推广后贡献毛利"] = _to_numeric(out, "扣推广后贡献毛利")
    out["订单侧毛利率"] = _to_numeric(out, "订单侧毛利率")
    out["推广费率"] = _to_numeric(out, "推广费率")
    out["百补销售占比"] = _to_numeric(out, "百补销售占比")

    high_revenue_threshold = out["商家实收"].quantile(0.6) if len(out) > 1 else out["商家实收"].max()
    high_margin_threshold = out["订单侧毛利率"].quantile(0.7) if len(out) > 1 else out["订单侧毛利率"].max()
    low_fee_threshold = out["推广费率"].quantile(0.4) if len(out) > 1 else out["推广费率"].min()

    def _classify(row: pd.Series) -> pd.Series:
        high_revenue = row["商家实收"] >= high_revenue_threshold
        roi_ok = row["实际ROI"] >= row["盈亏平衡ROI"]
        positive_contrib = row["扣推广后贡献毛利"] > 0
        high_margin = row["订单侧毛利率"] >= high_margin_threshold
        low_fee = row["推广费率"] <= low_fee_threshold

        if high_margin and positive_contrib and low_fee:
            return pd.Series(["利润型", "毛利率高且推广费率低，推广后仍有正毛利", "作为利润盘重点维护，适度增加曝光", "高"])
        if high_revenue and roi_ok and positive_contrib:
            return pd.Series(["放量型", "商家实收高且ROI达标，推广后贡献毛利为正", "继续放量，优先加预算或扩展规格", "高"])
        if high_revenue and ((not roi_ok) or (not positive_contrib)):
            return pd.Series(["控费型", "商家实收高但ROI未达盈亏平衡或贡献毛利为负", "控制推广费，优化出价和转化，优先治理亏损链接", "高"])
        if (not high_revenue) and roi_ok and positive_contrib:
            return pd.Series(["潜力型", "商家实收低但ROI达标且贡献毛利为正", "小预算测试放量，观察转化和投产稳定性", "中"])
        return pd.Series(["拖累型", "商家实收低且ROI未达标，贡献毛利为负", "减少投放或暂停，优先排查价格、成本、转化问题", "高"])

    out[["经营分层", "分层原因", "建议动作", "优先级"]] = out.apply(_classify, axis=1)
    return out


def segment_links(link_df: pd.DataFrame) -> pd.DataFrame:
    if link_df is None or link_df.empty:
        return pd.DataFrame()

    out = link_df.copy()

    out["商家实收"] = _to_numeric(out, "商家实收")
    out["实际成交花费(元)"] = _to_numeric(out, "实际成交花费(元)")
    out["实际ROI"] = _to_numeric(out, "实际ROI")
    out["盈亏平衡ROI"] = _to_numeric(out, "盈亏平衡ROI")
    out["扣推广后贡献毛利"] = _to_numeric(out, "扣推广后贡献毛利")
    out["订单无效率"] = _to_numeric(out, "订单无效率")

    high_revenue_threshold = out["商家实收"].quantile(0.6) if len(out) > 1 else out["商家实收"].max()

    def _classify(row: pd.Series) -> pd.Series:
        is_bb = str(row.get("是否百补", "")).strip() == "是"
        high_revenue = row["商家实收"] >= high_revenue_threshold
        roi_ok = row["实际ROI"] >= row["盈亏平衡ROI"]
        positive_contrib = row["扣推广后贡献毛利"] > 0
        high_invalid = row["订单无效率"] >= 0.25

        reasons = []
        advice = []

        if high_invalid:
            reasons.append("订单无效率偏高")
            advice.append("排查售后/退款原因并优化履约与客服")

        if is_bb and (not positive_contrib):
            reasons.append("百补链接亏损")
            advice.append("执行百补控费，收紧低效投放")

        if (not is_bb) and positive_contrib:
            reasons.append("日常链接贡献毛利为正")
            advice.append("作为日常利润盘稳定投放")

        if high_revenue and roi_ok and positive_contrib:
            layer, base_reason, base_advice, priority = "放量型", "商家实收高且ROI达标，推广后贡献毛利为正", "继续放量，优先加预算和扩词扩人群", "高"
        elif high_revenue and ((not roi_ok) or (not positive_contrib)):
            layer, base_reason, base_advice, priority = "控费型", "商家实收高但ROI未达盈亏平衡或贡献毛利为负", "控制推广费，优化出价和转化，优先治理亏损链接", "高"
        elif (not high_revenue) and roi_ok and positive_contrib:
            layer, base_reason, base_advice, priority = "潜力型", "商家实收低但ROI达标且贡献毛利为正", "小预算测试放量，观察转化和投产稳定性", "中"
        elif positive_contrib and row["实际成交花费(元)"] > 0 and row["实际ROI"] >= row["盈亏平衡ROI"] * 1.1:
            layer, base_reason, base_advice, priority = "利润型", "推广后贡献毛利为正且ROI显著高于盈亏平衡", "作为利润盘重点维护，适度增加曝光", "中"
        else:
            layer, base_reason, base_advice, priority = "拖累型", "商家实收低且ROI未达标，贡献毛利为负", "减少投放或暂停，优先排查价格、成本、转化问题", "高"

        reasons.insert(0, base_reason)
        advice.insert(0, base_advice)
        return pd.Series([layer, "；".join(reasons), "；".join(advice), priority])

    out[["经营分层", "分层原因", "建议动作", "优先级"]] = out.apply(_classify, axis=1)
    return out
