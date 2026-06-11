"""推广订单豁免分析。"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.utils import safe_divide


ORDER_ID_COL = "订单号"
EXEMPT_ORDER_ID_COL = "订单编号"


ORDER_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "订单号": ("订单号", "订单编号"),
    "支付时间": ("支付时间", "订单支付时间", "订单成交时间"),
    "商品ID": ("商品ID", "商品id", "商品 Id", "商品ID\t"),
    "商品名称": ("商品名称", "商品", "商品标题"),
    "商品规格": ("商品规格", "规格", "商品属性"),
    "商品数量": ("商品数量", "商品数量(件)", "数量"),
    "订单状态": ("订单状态",),
    "售后状态": ("售后状态",),
    "商品总价": ("商品总价", "商品总价(元)"),
    "店铺优惠": ("店铺优惠", "店铺优惠折扣(元)", "店铺优惠金额"),
    "平台优惠": ("平台优惠", "平台优惠折扣(元)", "平台优惠金额"),
    "用户实付金额": ("用户实付金额", "用户实付金额(元)"),
    "商家实收金额": ("商家实收金额", "商家实收金额(元)", "商家实收"),
    "发货时间": ("发货时间",),
    "确认收货时间": ("确认收货时间",),
    "快递公司": ("快递公司",),
    "快递单号": ("快递单号",),
}

EXEMPTION_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "商品": ("商品", "商品信息"),
    "订单编号": ("订单编号", "订单号"),
    "订单支付日期": ("订单支付日期", "支付日期", "订单支付时间"),
    "豁免类型": ("豁免类型",),
    "红包发放日期": ("红包发放日期", "红包发放时间"),
}

DETAIL_COLUMNS = [
    "订单号",
    "支付时间",
    "商品ID",
    "商品名称",
    "商品规格",
    "商品数量",
    "订单状态",
    "售后状态",
    "商品总价",
    "店铺优惠",
    "平台优惠",
    "用户实付金额",
    "商家实收金额",
    "同商品ID是否有豁免记录",
    "判定分类",
    "发货时间",
    "确认收货时间",
    "快递公司",
    "快递单号",
]


def _empty_result(messages: list[str] | None = None) -> dict[str, Any]:
    return {
        "messages": messages or [],
        "overview": {},
        "product_summary": pd.DataFrame(),
        "status_summary": pd.DataFrame(),
        "category_summary": pd.DataFrame(),
        "unexempted_details": pd.DataFrame(columns=DETAIL_COLUMNS),
        "suspected_details": pd.DataFrame(columns=DETAIL_COLUMNS),
        "exemption_orders": pd.DataFrame(),
    }


def clean_order_id(value: Any) -> str:
    """清洗订单号，始终按字符串处理以避免科学计数法造成订单号丢失。"""
    if pd.isna(value):
        return ""
    text = str(value)
    text = text.replace("\t", "").replace(" ", "").strip()
    if text.endswith(".0") and re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return text


def _pick_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {str(c).strip(): c for c in df.columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    return None


def _ensure_standard_columns(df: pd.DataFrame, alias_map: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for standard_col, aliases in alias_map.items():
        source_col = _pick_column(df, aliases)
        out[standard_col] = df[source_col] if source_col is not None else pd.NA
    return out


def _parse_goods_id_from_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    patterns = [
        r"商品\s*ID\s*[：:]\s*([A-Za-z0-9]+)",
        r"商品\s*Id\s*[：:]\s*([A-Za-z0-9]+)",
        r"商品\s*id\s*[：:]\s*([A-Za-z0-9]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def parse_exemption_orders(exemption_df: pd.DataFrame, date_range: tuple[Any, Any] | None = None) -> pd.DataFrame:
    if exemption_df is None or exemption_df.empty:
        return pd.DataFrame(columns=["商品", "商品ID", "订单编号", "订单编号_clean", "订单支付日期", "豁免类型", "红包发放日期"])

    out = _ensure_standard_columns(exemption_df.copy(), EXEMPTION_COLUMN_ALIASES)
    out["订单编号_clean"] = out["订单编号"].map(clean_order_id)
    out["订单编号"] = out["订单编号_clean"]
    out["商品ID"] = out["商品"].map(_parse_goods_id_from_text)
    out["订单支付日期"] = pd.to_datetime(out["订单支付日期"], errors="coerce")
    out["红包发放日期"] = pd.to_datetime(out["红包发放日期"], errors="coerce")

    if date_range and len(date_range) == 2 and out["订单支付日期"].notna().any():
        start = pd.to_datetime(date_range[0])
        end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        out = out[(out["订单支付日期"] >= start) & (out["订单支付日期"] <= end)].copy()

    out = out[out["订单编号_clean"] != ""].copy()
    out = out.drop_duplicates(subset=["订单编号_clean"], keep="first").reset_index(drop=True)
    return out[["商品", "商品ID", "订单编号", "订单编号_clean", "订单支付日期", "豁免类型", "红包发放日期"]]


def _prepare_orders(orders_df: pd.DataFrame, date_range: tuple[Any, Any] | None = None) -> pd.DataFrame:
    orders = _ensure_standard_columns(orders_df.copy(), ORDER_COLUMN_ALIASES)
    orders["订单号_clean"] = orders["订单号"].map(clean_order_id)
    orders["订单号"] = orders["订单号_clean"]
    orders["商品ID"] = orders["商品ID"].map(clean_order_id)
    orders["支付时间"] = pd.to_datetime(orders["支付时间"], errors="coerce")
    for col in ["商品总价", "店铺优惠", "平台优惠", "用户实付金额", "商家实收金额", "商品数量"]:
        orders[col] = pd.to_numeric(orders[col], errors="coerce")
    for col in ["订单状态", "售后状态", "商品名称", "商品规格", "发货时间", "确认收货时间", "快递公司", "快递单号"]:
        orders[col] = orders[col].fillna("").astype(str).str.strip()

    if date_range and len(date_range) == 2:
        start = pd.to_datetime(date_range[0])
        end = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        orders = orders[(orders["支付时间"] >= start) & (orders["支付时间"] <= end)].copy()

    return orders[orders["订单号_clean"] != ""].copy()


def _is_refund_success(orders: pd.DataFrame) -> pd.Series:
    after_sale = orders["售后状态"].fillna("").astype(str)
    status = orders["订单状态"].fillna("").astype(str)
    return after_sale.eq("退款成功") | status.str.contains("退款成功", na=False)


def _classify_unexempted(row: pd.Series) -> str:
    amount = row.get("商家实收金额")
    if pd.isna(amount) or float(amount) <= 0:
        return "0元/异常订单"

    status = str(row.get("订单状态", ""))
    has_goods_exemption = bool(row.get("同商品ID是否有豁免记录", False))

    if "已收货退款成功" in status:
        return "收货后退款未豁免"
    if "已发货退款成功" in status:
        return "发货后退款未豁免"
    if not has_goods_exemption:
        return "商品ID在豁免清单无记录"
    if "未发货退款成功" in status:
        return "疑似应豁免但未出现在清单"
    return "疑似应豁免但未出现在清单" if has_goods_exemption else "商品ID在豁免清单无记录"


def _summarize_by_group(df: pd.DataFrame, group_cols: list[str], amount_col: str | None = None) -> pd.DataFrame:
    if df.empty:
        base_cols = group_cols + ["退款成功订单数", "已豁免订单数", "未豁免订单数", "豁免覆盖率"]
        if amount_col:
            base_cols.append(amount_col)
        return pd.DataFrame(columns=base_cols)

    agg_dict = {
        "退款成功订单数": ("订单号", "nunique"),
        "已豁免订单数": ("已豁免", "sum"),
        "未豁免订单数": ("未豁免", "sum"),
    }
    if amount_col:
        agg_dict[amount_col] = ("未豁免商家实收金额_calc", "sum")
    out = df.groupby(group_cols, dropna=False).agg(**agg_dict).reset_index()
    out["已豁免订单数"] = out["已豁免订单数"].astype(int)
    out["未豁免订单数"] = out["未豁免订单数"].astype(int)
    out["豁免覆盖率"] = out.apply(lambda r: safe_divide(r["已豁免订单数"], r["退款成功订单数"]), axis=1)
    return out.sort_values(["未豁免订单数", "退款成功订单数"], ascending=False).reset_index(drop=True)


def build_promotion_exemption_analysis(
    orders_df: pd.DataFrame,
    exemption_df: pd.DataFrame,
    date_range: tuple[Any, Any] | None = None,
) -> dict[str, Any]:
    messages: list[str] = []
    if orders_df is None or orders_df.empty:
        return _empty_result(["请先上传拼多多订单明细。"])
    if exemption_df is None or exemption_df.empty:
        return _empty_result(["请先上传拼多多推广豁免订单数据。"])

    orders = _prepare_orders(orders_df, date_range)
    exemptions = parse_exemption_orders(exemption_df, date_range)

    if orders.empty:
        return _empty_result(["按支付时间筛选后没有可分析订单。"])

    if exemptions.empty:
        messages.append("豁免清单为空或按订单支付日期筛选后没有有效订单编号，所有退款成功订单都会暂按未豁免处理。")

    exempt_order_set = set(exemptions["订单编号_clean"].dropna().astype(str).tolist())
    exemption_goods_ids = set(exemptions["商品ID"].dropna().astype(str).tolist()) - {""}

    refund_orders = orders[_is_refund_success(orders)].copy()
    refund_orders["已豁免"] = refund_orders["订单号_clean"].isin(exempt_order_set)
    refund_orders["未豁免"] = ~refund_orders["已豁免"]
    refund_orders["同商品ID是否有豁免记录"] = refund_orders["商品ID"].isin(exemption_goods_ids)
    refund_orders["未豁免商家实收金额_calc"] = refund_orders["商家实收金额"].where(refund_orders["未豁免"], 0).fillna(0)

    unexempted = refund_orders[refund_orders["未豁免"]].copy()
    if not unexempted.empty:
        unexempted["判定分类"] = unexempted.apply(_classify_unexempted, axis=1)
        unexempted["同商品ID是否有豁免记录"] = unexempted["同商品ID是否有豁免记录"].map(lambda x: "是" if x else "否")
    else:
        unexempted["判定分类"] = pd.Series(dtype=str)

    details = unexempted[[c for c in DETAIL_COLUMNS if c in unexempted.columns]].copy()
    for col in DETAIL_COLUMNS:
        if col not in details.columns:
            details[col] = pd.NA
    details = details[DETAIL_COLUMNS]
    suspected = details[details["判定分类"] == "疑似应豁免但未出现在清单"].copy()

    paid_order_count = int(orders["订单号"].nunique())
    refund_success_count = int(refund_orders["订单号"].nunique())
    exempted_count = int(refund_orders.loc[refund_orders["已豁免"], "订单号"].nunique())
    unexempted_count = int(refund_orders.loc[refund_orders["未豁免"], "订单号"].nunique())

    overview = {
        "支付订单数": paid_order_count,
        "退款成功订单数": refund_success_count,
        "已豁免订单数": exempted_count,
        "未豁免订单数": unexempted_count,
        "豁免覆盖率": safe_divide(exempted_count, refund_success_count),
        "已豁免商家实收金额": float(refund_orders.loc[refund_orders["已豁免"], "商家实收金额"].fillna(0).sum()),
        "未豁免商家实收金额": float(refund_orders.loc[refund_orders["未豁免"], "商家实收金额"].fillna(0).sum()),
        "疑似应豁免但未豁免订单数": int(suspected["订单号"].nunique()) if not suspected.empty else 0,
        "疑似应豁免但未豁免金额": float(pd.to_numeric(suspected.get("商家实收金额", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
    }

    product_summary = _summarize_by_group(refund_orders, ["商品ID"], "未豁免商家实收金额")
    if not product_summary.empty:
        names = refund_orders.groupby("商品ID", dropna=False)["商品名称"].first().reset_index()
        product_summary = product_summary.merge(names, on="商品ID", how="left")
        cols = ["商品ID", "商品名称", "退款成功订单数", "已豁免订单数", "未豁免订单数", "豁免覆盖率", "未豁免商家实收金额"]
        product_summary = product_summary[[c for c in cols if c in product_summary.columns]]

    status_summary = _summarize_by_group(refund_orders, ["订单状态"])

    if details.empty:
        category_summary = pd.DataFrame(columns=["判定分类", "未豁免订单数", "未豁免商家实收金额"])
    else:
        category_summary = (
            details.assign(商家实收金额=pd.to_numeric(details["商家实收金额"], errors="coerce").fillna(0))
            .groupby("判定分类", dropna=False)
            .agg(未豁免订单数=("订单号", "nunique"), 未豁免商家实收金额=("商家实收金额", "sum"))
            .reset_index()
            .sort_values("未豁免订单数", ascending=False)
        )

    messages.append(
        "提示：未出现在豁免清单不等于一定是平台漏识别，可能存在非商品推广成交、部分退款、退货退款、平台数据延迟等情况。"
        "若上传商品推广成交明细和售后退款明细，后续可进一步判断是否真正符合豁免规则。"
    )

    return {
        "messages": messages,
        "overview": overview,
        "product_summary": product_summary,
        "status_summary": status_summary,
        "category_summary": category_summary,
        "unexempted_details": details.reset_index(drop=True),
        "suspected_details": suspected.reset_index(drop=True),
        "exemption_orders": exemptions,
    }
