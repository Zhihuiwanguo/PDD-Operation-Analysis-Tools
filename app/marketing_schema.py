"""拼多多 2026-06-02 商品营销新旧口径统一层。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils import safe_divide

MARKETING_SCHEMA_CHANGE_DATE = pd.Timestamp("2026-06-02")
OLD_VERSION = "old_promotion"
NEW_VERSION = "new_marketing"
MIXED_VERSION = "mixed"

DATE_ALIASES = ("日期", "统计日期", "统计日期文本", "时间", "推广日期")
SHOP_ALIASES = ("店铺名称", "店铺", "shop_name")
GOODS_ID_ALIASES = ("商品ID", "商品id", "商品 Id", "goods_id")
GOODS_NAME_ALIASES = ("商品名称", "链接标题", "商品", "计划名称", "goods_name")
OLD_PROMO_SPEND_ALIASES = ("实际成交花费(元)", "实际成交花费", "成交花费", "成交花费(元)", "成交花费（元）", "花费", "推广花费", "消耗", "推广消耗", "实际消耗")
NEW_PROMO_SPEND_ALIASES = ("推广成交花费", "推广成交花费(元)", "推广成交花费（元）")
COUPON_SPEND_ALIASES = ("结算券花费", "结算券花费(元)", "结算券花费（元）")
TOTAL_SPEND_ALIASES = ("成交营销花费", "成交营销花费(元)", "总营销花费", "总营销花费(元)", "商品营销总花费")
AD_AMOUNT_ALIASES = ("交易额", "交易额(元)", "实际成交金额", "结算金额", "结算金额(元)")
AD_NET_AMOUNT_ALIASES = ("净交易额", "净交易额(元)", "净交易额（元）")
OLD_ROI_ALIASES = ("ROI", "投产比", "旧口径实际净推广投产比")
NET_ROI_ALIASES = ("实际净投产比", "净投产比")
SETTLEMENT_ROI_ALIASES = ("结算投产比",)
_TOTAL_ROW_TOKENS = {"总计", "合计", "汇总", "全部"}


def _norm_col(col: object) -> str:
    return str(col or "").strip().replace(" ", "").replace("\n", "").replace("\t", "").replace("（", "(").replace("）", ")")


def _pick(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    normalized = {_norm_col(c): c for c in df.columns}
    for alias in aliases:
        found = normalized.get(_norm_col(alias))
        if found is not None:
            return found
    return None


def _num(df: pd.DataFrame, col: str | None, default: float = 0.0) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def _text(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return df[col].fillna("").astype(str).str.strip()


def normalize_goods_id_value(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s in {"", "nan", "None", "null", "-"}:
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    try:
        f = float(s)
        if pd.notna(f) and f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return s


def _is_total_row(raw: pd.DataFrame, goods_col: str | None, name_col: str | None, date_col: str | None) -> pd.Series:
    mask = pd.Series(False, index=raw.index)
    for col in [goods_col, name_col, date_col]:
        if col and col in raw.columns:
            values = raw[col].fillna("").astype(str).str.strip()
            mask = mask | values.isin(_TOTAL_ROW_TOKENS) | values.str.contains("总计|合计", na=False)
    return mask


def standardize_promotion_table(promo_df: pd.DataFrame | None) -> pd.DataFrame:
    """把旧推广表/新商品营销表逐行标准化为统一字段。"""
    if promo_df is None or promo_df.empty:
        return pd.DataFrame(columns=[
            "date", "shop_name", "goods_id", "goods_name", "promo_spend",
            "settlement_coupon_spend", "marketing_total_spend", "ad_transaction_amount",
            "ad_net_transaction_amount", "old_roi", "net_roi", "settlement_roi", "data_version",
            "口径提示", "总营销花费校验差异", "is_total_row",
        ])

    raw = promo_df.copy()
    date_col = _pick(raw, DATE_ALIASES)
    shop_col = _pick(raw, SHOP_ALIASES)
    goods_col = _pick(raw, GOODS_ID_ALIASES)
    name_col = _pick(raw, GOODS_NAME_ALIASES)
    old_spend_col = _pick(raw, OLD_PROMO_SPEND_ALIASES)
    new_spend_col = _pick(raw, NEW_PROMO_SPEND_ALIASES)
    coupon_col = _pick(raw, COUPON_SPEND_ALIASES)
    total_col = _pick(raw, TOTAL_SPEND_ALIASES)

    out = pd.DataFrame(index=raw.index)
    out["date"] = pd.to_datetime(raw[date_col], errors="coerce").dt.normalize() if date_col else pd.NaT
    out["shop_name"] = _text(raw, shop_col)
    out["goods_id"] = _text(raw, goods_col).apply(normalize_goods_id_value)
    out["goods_name"] = _text(raw, name_col)

    is_total = _is_total_row(raw, goods_col, name_col, date_col)
    is_new_by_date = out["date"].ge(MARKETING_SCHEMA_CHANGE_DATE).fillna(False)
    has_new_fields = new_spend_col is not None or coupon_col is not None or total_col is not None
    is_new = is_new_by_date & has_new_fields

    old_spend = _num(raw, old_spend_col)
    new_spend = _num(raw, new_spend_col)
    coupon_spend = _num(raw, coupon_col)

    out["promo_spend"] = np.where(is_new, new_spend, old_spend)
    if new_spend_col is None and old_spend_col is not None:
        out["promo_spend"] = old_spend
    out["settlement_coupon_spend"] = np.where(is_new, coupon_spend, 0.0)
    out["marketing_total_spend"] = out["promo_spend"] + out["settlement_coupon_spend"]
    out["ad_transaction_amount"] = _num(raw, _pick(raw, AD_AMOUNT_ALIASES))
    out["ad_net_transaction_amount"] = _num(raw, _pick(raw, AD_NET_AMOUNT_ALIASES))
    out["old_roi"] = _num(raw, _pick(raw, OLD_ROI_ALIASES), np.nan)
    out["net_roi"] = _num(raw, _pick(raw, NET_ROI_ALIASES), np.nan)
    out["settlement_roi"] = _num(raw, _pick(raw, SETTLEMENT_ROI_ALIASES), np.nan)
    out["data_version"] = np.where(is_new, NEW_VERSION, OLD_VERSION)
    out["口径提示"] = np.where(is_new, "2026-06-02 后商品营销口径", "2026-06-01 及以前旧推广口径")
    out["is_total_row"] = is_total

    provided_total = _num(raw, total_col, np.nan)
    out["总营销花费校验差异"] = provided_total - out["marketing_total_spend"]
    out = out[~out["is_total_row"]].copy()
    for col in ["promo_spend", "settlement_coupon_spend", "marketing_total_spend", "ad_transaction_amount", "ad_net_transaction_amount"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def promotion_batch_version(standardized: pd.DataFrame) -> str:
    versions = set(standardized.get("data_version", pd.Series(dtype=str)).dropna().astype(str))
    if len(versions) > 1:
        return MIXED_VERSION
    return next(iter(versions), OLD_VERSION)


def add_standard_promotion_columns(promo_df: pd.DataFrame | None) -> pd.DataFrame:
    raw = promo_df.copy() if promo_df is not None else pd.DataFrame()
    std = standardize_promotion_table(raw)
    for col in ["date", "shop_name", "goods_id", "goods_name", "promo_spend", "settlement_coupon_spend", "marketing_total_spend", "ad_transaction_amount", "ad_net_transaction_amount", "old_roi", "net_roi", "settlement_roi", "data_version"]:
        raw[col] = std.reindex(raw.index).get(col)
    raw = raw.loc[std.index].copy() if len(std.index) else raw.iloc[0:0].copy()
    raw["日期"] = raw.get("日期", std.get("date"))
    raw["商品ID"] = raw.get("商品ID", std.get("goods_id"))
    raw["实际成交花费(元)"] = raw.get("promo_spend", std.get("promo_spend"))
    return raw


def build_discount_split(orders: pd.DataFrame, promo_std: pd.DataFrame) -> pd.DataFrame:
    valid = orders[orders.get("订单分类", "") == "有效"].copy() if "订单分类" in orders.columns else orders.copy()
    for col in ["商品总价(元)", "店铺优惠折扣(元)", "平台优惠折扣(元)", "用户实付金额(元)", "商家实收金额(元)"]:
        if col not in valid.columns:
            valid[col] = 0.0
        valid[col] = pd.to_numeric(valid[col], errors="coerce").fillna(0.0)
    if "商品id" not in valid.columns:
        valid["商品id"] = ""
    valid["商品id"] = valid["商品id"].fillna("").astype(str).map(normalize_goods_id_value)
    if "订单成交时间" in valid.columns:
        valid["日期"] = pd.to_datetime(valid["订单成交时间"].replace({"\\t": ""}), errors="coerce").dt.normalize()
    else:
        valid["日期"] = pd.NaT
    if "支付时间" in valid.columns:
        pay = pd.to_datetime(valid["支付时间"].replace({"\\t": ""}), errors="coerce").dt.normalize()
        valid["日期"] = valid["日期"].fillna(pay)
    if "店铺名称" not in valid.columns:
        valid["店铺名称"] = ""
    if "商品" not in valid.columns:
        valid["商品"] = ""
    if "标准产品名称" not in valid.columns:
        valid["标准产品名称"] = ""

    order_daily = valid.groupby(["日期", "店铺名称", "商品id", "商品", "标准产品名称"], dropna=False).agg(
        商品总价=("商品总价(元)", "sum"), 店铺优惠折扣=("店铺优惠折扣(元)", "sum"),
        平台优惠折扣=("平台优惠折扣(元)", "sum"), 用户实付金额=("用户实付金额(元)", "sum"),
        商家实收金额=("商家实收金额(元)", "sum"),
    ).reset_index().rename(columns={"店铺名称": "店铺", "商品id": "商品ID", "商品": "商品名称", "标准产品名称": "标准产品"})

    promo = promo_std.copy()
    if promo.empty:
        promo_daily = pd.DataFrame(columns=["日期", "店铺", "商品ID", "推广结算券金额", "推广成交花费", "商品营销总花费"])
    else:
        promo["日期"] = pd.to_datetime(promo["date"], errors="coerce").dt.normalize()
        promo["店铺"] = promo.get("shop_name", "")
        promo["商品ID"] = promo.get("goods_id", "")
        promo_daily = promo.groupby(["日期", "店铺", "商品ID"], dropna=False).agg(
            推广结算券金额=("settlement_coupon_spend", "sum"),
            推广成交花费=("promo_spend", "sum"),
            商品营销总花费=("marketing_total_spend", "sum"),
        ).reset_index()

    result = order_daily.merge(promo_daily, on=["日期", "店铺", "商品ID"], how="left")
    for col in ["推广结算券金额", "推广成交花费", "商品营销总花费"]:
        result[col] = pd.to_numeric(result.get(col, 0), errors="coerce").fillna(0.0)
    result["店铺设置优惠金额"] = result["店铺优惠折扣"] - result["推广结算券金额"]
    result["是否异常"] = np.where(result["店铺设置优惠金额"] < -0.01, "口径差异/退款结算差异", "否")
    return result


def classify_cashflow(cashflow_df: pd.DataFrame | None) -> pd.DataFrame:
    df = cashflow_df.copy() if cashflow_df is not None else pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=["日期", "店铺", "流水项目", "金额"])
    for col in ["时间", "日期", "店铺名称", "流水类型", "交易摘要", "交易金额", "资金类型"]:
        if col not in df.columns:
            df[col] = ""
    date_col = "时间" if "时间" in df.columns else "日期"
    text = (df["流水类型"].fillna("").astype(str) + " " + df["交易摘要"].fillna("").astype(str) + " " + df["资金类型"].fillna("").astype(str))
    amount = pd.to_numeric(df["交易金额"], errors="coerce").fillna(0.0).abs()
    out = pd.DataFrame({"日期": pd.to_datetime(df[date_col], errors="coerce").dt.normalize(), "店铺": df["店铺名称"].fillna("").astype(str), "金额": amount})
    out["流水项目"] = "其他"
    out.loc[text.str.contains("商品推广", na=False) & text.str.contains("现金", na=False), "流水项目"] = "商品推广现金支出"
    out.loc[text.str.contains("商品推广", na=False) & text.str.contains("红包", na=False), "流水项目"] = "商品推广红包支出"
    out.loc[text.str.contains("明星店铺", na=False) & text.str.contains("现金", na=False), "流水项目"] = "明星店铺现金支出"
    out.loc[text.str.contains("明星店铺", na=False) & text.str.contains("红包", na=False), "流水项目"] = "明星店铺红包支出"
    out.loc[text.str.contains("充值", na=False), "流水项目"] = "充值"
    out.loc[text.str.contains("退款", na=False), "流水项目"] = "退款"
    out.loc[text.str.contains("冻结|解冻", na=False), "流水项目"] = "冻结/解冻"
    promo_mask = text.str.contains("推广", na=False) & text.str.contains("支出", na=False) & ~text.str.contains("明星店铺", na=False)
    out.loc[(out["流水项目"] == "其他") & promo_mask, "流水项目"] = "商品推广现金支出"
    return out


def build_account_flow_validation(promo_std: pd.DataFrame, cashflow_df: pd.DataFrame | None) -> pd.DataFrame:
    promo = promo_std.copy()
    if promo.empty:
        return pd.DataFrame(columns=["日期", "店铺", "商品营销表promo_spend", "账户流水商品推广支出", "差异金额", "差异率", "差异原因提示"])
    promo["日期"] = pd.to_datetime(promo["date"], errors="coerce").dt.normalize()
    promo["店铺"] = promo.get("shop_name", "")
    promo_daily = promo.groupby(["日期", "店铺"], dropna=False)["promo_spend"].sum().reset_index(name="商品营销表promo_spend")
    cash = classify_cashflow(cashflow_df)
    product_cash = cash[cash["流水项目"].isin(["商品推广现金支出", "商品推广红包支出"])].copy()
    cash_daily = product_cash.groupby(["日期", "店铺"], dropna=False)["金额"].sum().reset_index(name="账户流水商品推广支出")
    out = promo_daily.merge(cash_daily, on=["日期", "店铺"], how="left")
    out["账户流水商品推广支出"] = pd.to_numeric(out["账户流水商品推广支出"], errors="coerce").fillna(0.0)
    out["差异金额"] = out["商品营销表promo_spend"] - out["账户流水商品推广支出"]
    out["差异率"] = out.apply(lambda r: safe_divide(r["差异金额"], r["商品营销表promo_spend"]), axis=1)
    out["差异原因提示"] = np.where(out["差异金额"].abs() <= 0.01, "一致", "请核对现金/红包、退款、冻结解冻或推广表与流水日期范围差异；明星店铺未默认并入商品ID推广费")
    return out


def build_marketing_diagnostics(raw_promo: pd.DataFrame, promo_std: pd.DataFrame, orders: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rows = []
    raw = raw_promo.copy() if raw_promo is not None else pd.DataFrame()
    raw_total_rows = int(_is_total_row(raw, _pick(raw, GOODS_ID_ALIASES), _pick(raw, GOODS_NAME_ALIASES), _pick(raw, DATE_ALIASES)).sum()) if not raw.empty else 0
    rows.append({"检查项": "是否上传新商品营销表", "异常数": int((promo_std.get("data_version", pd.Series(dtype=str)) == NEW_VERSION).sum()), "提示": "检测到 new_marketing 行"})
    rows.append({"检查项": "总计行自动剔除", "异常数": raw_total_rows, "提示": "总计/合计行不会参与汇总"})
    rows.append({"检查项": "商品ID为空", "异常数": int((promo_std.get("goods_id", pd.Series(dtype=str)).fillna("").astype(str) == "").sum()), "提示": "商品ID为空会导致推广费无法挂接"})
    rows.append({"检查项": "日期为空", "异常数": int(pd.to_datetime(promo_std.get("date", pd.Series(dtype=str)), errors="coerce").isna().sum()), "提示": "日期为空会影响按日和跨月分析"})
    rows.append({"检查项": "promo_spend为负数", "异常数": int((pd.to_numeric(promo_std.get("promo_spend", 0), errors="coerce").fillna(0) < 0).sum()), "提示": "推广成交花费不应为负"})
    rows.append({"检查项": "settlement_coupon_spend为负数", "异常数": int((pd.to_numeric(promo_std.get("settlement_coupon_spend", 0), errors="coerce").fillna(0) < 0).sum()), "提示": "结算券花费不应为负"})
    diff = (pd.to_numeric(promo_std.get("marketing_total_spend", 0), errors="coerce").fillna(0) - pd.to_numeric(promo_std.get("promo_spend", 0), errors="coerce").fillna(0) - pd.to_numeric(promo_std.get("settlement_coupon_spend", 0), errors="coerce").fillna(0)).abs()
    rows.append({"检查项": "marketing_total_spend等式", "异常数": int((diff > 0.01).sum()), "提示": "系统优先按推广成交花费+结算券花费计算"})
    od = orders.copy() if orders is not None else pd.DataFrame()
    for c in ["商品总价(元)", "店铺优惠折扣(元)", "平台优惠折扣(元)", "用户实付金额(元)", "商家实收金额(元)"]:
        if c not in od.columns:
            od[c] = 0.0
        od[c] = pd.to_numeric(od[c], errors="coerce").fillna(0.0)
    user_diff = (od["用户实付金额(元)"] - (od["商品总价(元)"] - od["店铺优惠折扣(元)"] - od["平台优惠折扣(元)"])).abs()
    merchant_diff = (od["商家实收金额(元)"] - (od["商品总价(元)"] - od["店铺优惠折扣(元)"])).abs()
    rows.append({"检查项": "用户实付价格链路", "异常数": int((user_diff > 0.01).sum()), "提示": "用户实付≈商品总价-店铺优惠-平台优惠"})
    rows.append({"检查项": "商家实收价格链路", "异常数": int((merchant_diff > 0.01).sum()), "提示": "商家实收≈商品总价-店铺优惠"})
    return {"summary": pd.DataFrame(rows)}
