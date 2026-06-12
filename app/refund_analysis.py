"""退款/售后分析口径与字段兼容工具。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.marketing_schema import normalize_goods_id_value
from app.utils import safe_divide

GOODS_ID_ALIASES = ("商品ID", "商品id", "商品编号", "商品id/商品ID")
GOODS_NAME_ALIASES = ("商品名称", "商品", "链接标题", "商品标题")
PAY_TIME_ALIASES = ("支付时间", "订单成交时间", "成交时间", "下单时间")
ORDER_STATUS_ALIASES = ("订单状态", "订单状态描述")
AFTER_SALE_STATUS_ALIASES = ("售后状态", "退款状态", "售后/退款状态")
SHIP_STATUS_ALIASES = ("发货状态", "物流状态", "配送状态")
GOODS_PRICE_ALIASES = ("商品总价(元)", "商品总价", "商品金额(元)", "商品金额")
USER_PAY_ALIASES = ("用户实付金额(元)", "消费者实付金额(元)", "实付金额(元)", "支付金额(元)", "用户实付金额", "用户实付")
MERCHANT_INCOME_ALIASES = ("商家实收金额(元)", "商家实收(元)", "商家实收金额", "商家实际收入(元)", "商家实收")
GOODS_QTY_ALIASES = ("商品数量(件)", "商品数量", "数量", "件数")
PRODUCT_NAME_ALIASES = ("标准产品名称", "产品名称")

REFUND_SUCCESS_KEYWORDS = ("退款成功", "已退款", "退货退款成功")
AFTER_SALE_PENDING_KEYWORDS = (
    "售后处理中", "退款中", "退货退款中", "待商家处理", "待平台处理", "待买家退货", "待商家收货",
)
UNSHIPPED_KEYWORDS = ("未发货",)
WAIT_SHIP_KEYWORDS = ("待发货",)
SHIPPED_KEYWORDS = ("已发货", "运输中", "已签收", "已收货", "派送中", "配送中")
RECEIVED_KEYWORDS = ("已收货", "已签收")
UNDEALT_KEYWORDS = ("未成交", "拼单未成功", "交易关闭", "已取消", "订单取消")


def _norm_col(col: object) -> str:
    return str(col or "").strip().replace(" ", "").replace("\n", "").replace("\t", "").replace("（", "(").replace("）", ")")


def pick_alias(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {_norm_col(c): c for c in df.columns}
    for alias in aliases:
        found = normalized.get(_norm_col(alias))
        if found is not None:
            return found
    return None


def _text(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return df[col].fillna("").astype(str).str.strip()


def _num(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    cleaned = df[col].astype(str).str.replace(",", "", regex=False).str.strip().replace({"": np.nan, "--": np.nan, "-": np.nan, "nan": np.nan, "None": np.nan})
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def _contains_any(series: pd.Series, keywords: tuple[str, ...]) -> pd.Series:
    text = series.fillna("").astype(str)
    if not keywords:
        return pd.Series(False, index=series.index)
    pattern = "|".join(keywords)
    return text.str.contains(pattern, na=False, regex=True)


def normalize_order_refund_fields(orders: pd.DataFrame | None) -> tuple[pd.DataFrame, list[str]]:
    """生成退款分析所需的兼容字段，不改变原始上传表。"""
    raw = orders.copy() if orders is not None else pd.DataFrame()
    if raw.empty:
        cols = [
            "支付时间_退款口径", "日期", "商品ID", "商品名称", "标准产品名称", "订单状态_退款口径", "售后状态_退款口径",
            "发货状态_退款口径", "商品总价_退款口径", "用户实付_退款口径", "商家实收_退款口径", "商品件数_退款口径",
            "是否退款成功", "是否售后处理中", "是否未发货退款成功", "是否未成交退款成功", "是否发货后退款成功", "是否收货后退款成功",
        ]
        return pd.DataFrame(columns=cols), ["订单表为空，无法计算退款/售后指标。"]

    messages: list[str] = []
    alias_map = {
        "支付时间": pick_alias(raw, PAY_TIME_ALIASES),
        "商品ID": pick_alias(raw, GOODS_ID_ALIASES),
        "商品名称": pick_alias(raw, GOODS_NAME_ALIASES),
        "标准产品名称": pick_alias(raw, PRODUCT_NAME_ALIASES),
        "订单状态": pick_alias(raw, ORDER_STATUS_ALIASES),
        "售后状态": pick_alias(raw, AFTER_SALE_STATUS_ALIASES),
        "发货状态": pick_alias(raw, SHIP_STATUS_ALIASES),
        "商品总价": pick_alias(raw, GOODS_PRICE_ALIASES),
        "用户实付": pick_alias(raw, USER_PAY_ALIASES),
        "商家实收": pick_alias(raw, MERCHANT_INCOME_ALIASES),
        "商品件数": pick_alias(raw, GOODS_QTY_ALIASES),
    }
    for label in ["支付时间", "商品ID", "订单状态", "售后状态", "商家实收"]:
        if alias_map[label] is None:
            messages.append(f"未找到{label}字段，相关指标将按可用字段降级计算。")

    out = raw.copy()
    out["支付时间_退款口径"] = pd.to_datetime(_text(raw, alias_map["支付时间"]).replace({"\\t": ""}), errors="coerce")
    out["日期"] = out["支付时间_退款口径"].dt.normalize()
    out["商品ID"] = _text(raw, alias_map["商品ID"]).map(normalize_goods_id_value)
    out["商品名称"] = _text(raw, alias_map["商品名称"])
    if alias_map["标准产品名称"] is not None:
        out["标准产品名称"] = _text(raw, alias_map["标准产品名称"])
    elif "标准产品名称" not in out.columns:
        out["标准产品名称"] = out["商品名称"]
    out["订单状态_退款口径"] = _text(raw, alias_map["订单状态"])
    out["售后状态_退款口径"] = _text(raw, alias_map["售后状态"])
    out["发货状态_退款口径"] = _text(raw, alias_map["发货状态"])
    out["商品总价_退款口径"] = _num(raw, alias_map["商品总价"])
    out["用户实付_退款口径"] = _num(raw, alias_map["用户实付"])
    out["商家实收_退款口径"] = _num(raw, alias_map["商家实收"])
    out["商品件数_退款口径"] = _num(raw, alias_map["商品件数"])

    order_status = out["订单状态_退款口径"]
    after_sale_status = out["售后状态_退款口径"]
    ship_status = out["发货状态_退款口径"]
    status_all = order_status + " " + after_sale_status + " " + ship_status

    refund_success = _contains_any(after_sale_status, REFUND_SUCCESS_KEYWORDS) | _contains_any(order_status, REFUND_SUCCESS_KEYWORDS)
    pending = _contains_any(after_sale_status, AFTER_SALE_PENDING_KEYWORDS) & ~refund_success
    unshipped = _contains_any(ship_status, UNSHIPPED_KEYWORDS) | _contains_any(order_status, WAIT_SHIP_KEYWORDS) | (~_contains_any(ship_status, SHIPPED_KEYWORDS))
    shipped = _contains_any(ship_status, SHIPPED_KEYWORDS) | _contains_any(order_status, SHIPPED_KEYWORDS)
    undealt = _contains_any(order_status, UNDEALT_KEYWORDS)
    received = _contains_any(status_all, RECEIVED_KEYWORDS)

    out["是否支付订单"] = out["支付时间_退款口径"].notna()
    out["是否退款成功"] = refund_success
    out["是否售后处理中"] = pending
    out["是否未发货退款成功"] = refund_success & unshipped & ~shipped
    out["是否未成交退款成功"] = refund_success & undealt
    out["是否发货后退款成功"] = refund_success & shipped
    out["是否收货后退款成功"] = refund_success & received
    out["退款成功商家实收金额"] = np.where(out["是否退款成功"], out["商家实收_退款口径"], 0.0)
    out["售后处理中商家实收金额"] = np.where(out["是否售后处理中"], out["商家实收_退款口径"], 0.0)
    return out, messages


def _unique_orders(series: pd.Series) -> pd.Series:
    return series.nunique(dropna=False) if series.name == "订单号" else series.size


def summarize_refund_metrics(df: pd.DataFrame) -> dict[str, float]:
    if df is None or df.empty:
        return {
            "支付订单数": 0, "商品件数": 0.0, "商品总价": 0.0, "用户实付金额": 0.0, "商家实收金额": 0.0,
            "退款成功订单数": 0, "退款成功率": 0.0, "退款金额": 0.0, "退款金额占比": 0.0,
            "剔除退款后商家实收": 0.0, "售后处理中订单数": 0, "售后处理中商家实收金额": 0.0,
            "确认有效商家实收": 0.0, "未发货退款订单数": 0, "未发货退款率": 0.0,
            "未成交退款订单数": 0, "发货后退款订单数": 0, "发货后退款率": 0.0, "已收货后退款订单数": 0,
        }
    order_col = "订单号" if "订单号" in df.columns else None

    def _count(mask: pd.Series) -> int:
        scoped = df.loc[mask]
        if order_col:
            return int(scoped[order_col].nunique(dropna=False))
        return int(mask.sum())

    pay_orders = _count(df["是否支付订单"])
    merchant_income = float(pd.to_numeric(df["商家实收_退款口径"], errors="coerce").fillna(0.0).sum())
    refund_amount = float(pd.to_numeric(df["退款成功商家实收金额"], errors="coerce").fillna(0.0).sum())
    pending_amount = float(pd.to_numeric(df["售后处理中商家实收金额"], errors="coerce").fillna(0.0).sum())
    refund_orders = _count(df["是否退款成功"])
    pending_orders = _count(df["是否售后处理中"])
    unshipped_refunds = _count(df["是否未发货退款成功"])
    shipped_refunds = _count(df["是否发货后退款成功"])
    return {
        "支付订单数": pay_orders,
        "商品件数": float(pd.to_numeric(df["商品件数_退款口径"], errors="coerce").fillna(0.0).sum()),
        "商品总价": float(pd.to_numeric(df["商品总价_退款口径"], errors="coerce").fillna(0.0).sum()),
        "用户实付金额": float(pd.to_numeric(df["用户实付_退款口径"], errors="coerce").fillna(0.0).sum()),
        "商家实收金额": merchant_income,
        "退款成功订单数": refund_orders,
        "退款成功率": safe_divide(refund_orders, pay_orders),
        "退款金额": refund_amount,
        "退款金额占比": safe_divide(refund_amount, merchant_income),
        "剔除退款后商家实收": merchant_income - refund_amount,
        "售后处理中订单数": pending_orders,
        "售后处理中商家实收金额": pending_amount,
        "确认有效商家实收": merchant_income - refund_amount - pending_amount,
        "未发货退款订单数": unshipped_refunds,
        "未发货退款率": safe_divide(unshipped_refunds, pay_orders),
        "未成交退款订单数": _count(df["是否未成交退款成功"]),
        "发货后退款订单数": shipped_refunds,
        "发货后退款率": safe_divide(shipped_refunds, pay_orders),
        "已收货后退款订单数": _count(df["是否收货后退款成功"]),
    }


def aggregate_refund_by(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=group_cols + list(summarize_refund_metrics(pd.DataFrame()).keys()))
    rows = []
    for keys, part in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update(summarize_refund_metrics(part))
        rows.append(row)
    return pd.DataFrame(rows)


def build_refund_analysis(orders: pd.DataFrame) -> dict[str, pd.DataFrame | dict | list[str]]:
    normalized, messages = normalize_order_refund_fields(orders)
    overview = summarize_refund_metrics(normalized)
    daily = aggregate_refund_by(normalized.dropna(subset=["日期"]) if "日期" in normalized.columns else normalized, ["日期"])
    product = aggregate_refund_by(normalized, ["标准产品名称"])
    link = aggregate_refund_by(normalized, ["商品ID", "商品名称"])

    daily_alerts = []
    if not daily.empty and "退款成功率" in daily.columns:
        abnormal = daily[pd.to_numeric(daily["退款成功率"], errors="coerce").fillna(0) > 0.20].copy()
        abnormal["异常类型"] = "当日退款异常"
        daily_alerts.append(abnormal[["日期", "支付订单数", "退款成功订单数", "退款成功率", "异常类型"]])

    alerts = build_refund_alerts(product, link, daily)
    return {
        "orders": normalized,
        "overview": overview,
        "daily": daily.sort_values("日期") if "日期" in daily.columns else daily,
        "product": product.sort_values("退款成功率", ascending=False) if "退款成功率" in product.columns else product,
        "link": link.sort_values("退款成功率", ascending=False) if "退款成功率" in link.columns else link,
        "alerts": alerts,
        "messages": messages,
    }


def build_refund_alerts(product: pd.DataFrame, link: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for scope, df, name_cols in [
        ("产品", product, ["标准产品名称"]),
        ("链接", link, ["商品ID", "商品名称"]),
    ]:
        if df is None or df.empty:
            continue
        tmp = df.copy()
        for col in ["支付订单数", "退款成功订单数", "退款成功率", "未发货退款订单数", "发货后退款率", "售后处理中商家实收金额", "商家实收金额"]:
            if col not in tmp.columns:
                tmp[col] = 0
            tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0.0)
        conditions = [
            (tmp["退款成功率"] > 0.20) & (tmp["支付订单数"] >= 30),
            safe_divide_series(tmp["未发货退款订单数"], tmp["退款成功订单数"]) > 0.70,
            tmp["发货后退款率"] > 0.05,
            safe_divide_series(tmp["售后处理中商家实收金额"], tmp["商家实收金额"]) > 0.03,
        ]
        labels = ["高退款风险", "发货前流失偏高", "履约/商品体验风险", "售后风险偏高"]
        for cond, label in zip(conditions, labels):
            hit = tmp.loc[cond, name_cols + ["支付订单数", "退款成功订单数", "退款成功率", "商家实收金额"]].copy()
            if not hit.empty:
                hit["范围"] = scope
                hit["异常类型"] = label
                frames.append(hit)
    if daily is not None and not daily.empty and "退款成功率" in daily.columns:
        tmp = daily.copy()
        tmp["退款成功率"] = pd.to_numeric(tmp["退款成功率"], errors="coerce").fillna(0.0)
        hit = tmp.loc[tmp["退款成功率"] > 0.20, ["日期", "支付订单数", "退款成功订单数", "退款成功率"]].copy()
        if not hit.empty:
            hit["范围"] = "每日"
            hit["异常类型"] = "当日退款异常"
            frames.append(hit)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame(columns=["范围", "异常类型"])


def safe_divide_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    n = pd.to_numeric(numerator, errors="coerce").fillna(0.0)
    d = pd.to_numeric(denominator, errors="coerce").fillna(0.0)
    return n.div(d.replace(0, np.nan)).fillna(0.0)
