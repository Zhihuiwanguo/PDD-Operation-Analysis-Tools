"""推广订单豁免分析页。"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_loader import load_table
from app.exporters import to_excel_bytes
from app.promotion_exemption_analysis import build_promotion_exemption_analysis
from app.utils import clean_columns


def _metric_value(value, kind: str) -> str:
    if kind == "pct":
        return f"{float(value or 0):.2%}"
    if kind == "money":
        return f"¥{float(value or 0):,.2f}"
    return f"{int(value or 0):,}"


def _format_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if "豁免覆盖率" in out.columns:
        out["豁免覆盖率"] = (
            pd.to_numeric(out["豁免覆盖率"], errors="coerce")
            .fillna(0)
            .map(lambda x: f"{x:.2%}")
        )
    return out


def _load_order_table(order_file) -> pd.DataFrame:
    order_file.seek(0)
    return load_table(order_file, order_file.name, key="orders")


def _load_exemption_table(exemption_file) -> pd.DataFrame:
    exemption_file.seek(0)
    # 豁免订单号必须以字符串读取，避免长订单号被 Excel 解析为数字或科学计数法。
    exemption_df = pd.read_excel(exemption_file, dtype=str)
    exemption_df = clean_columns(exemption_df)
    required_columns = ["商品", "订单编号", "订单支付日期", "豁免类型", "红包发放日期"]
    missing_columns = [
        col for col in required_columns if col not in exemption_df.columns
    ]
    if missing_columns:
        raise ValueError(
            "豁免文件缺少固定字段："
            + "、".join(missing_columns)
            + "。请确认字段为："
            + "、".join(required_columns)
        )
    return exemption_df


def _build_file_diagnostics(
    order_file, exemption_file, orders_df: pd.DataFrame, exemption_df: pd.DataFrame
) -> dict[str, object]:
    order_samples: list[str] = []
    order_id_col = "订单号" if "订单号" in orders_df.columns else "订单编号"
    if order_id_col in orders_df.columns:
        order_samples = orders_df[order_id_col].dropna().astype(str).head(10).tolist()

    return {
        "订单文件名": getattr(order_file, "name", ""),
        "豁免文件名": getattr(exemption_file, "name", ""),
        "豁免文件读取行数": int(len(exemption_df)),
        "豁免文件字段名": list(exemption_df.columns),
        "豁免文件前10行": exemption_df.head(10),
        "订单编号样例前10个": order_samples,
    }


def _render_file_diagnostics(diagnostics: dict[str, object]) -> None:
    with st.expander("文件读取诊断", expanded=True):
        st.write("订单文件名：", diagnostics.get("订单文件名", ""))
        st.write("豁免文件名：", diagnostics.get("豁免文件名", ""))
        st.write("豁免文件读取行数：", diagnostics.get("豁免文件读取行数", 0))
        st.write("豁免文件字段名：", diagnostics.get("豁免文件字段名", []))
        st.write("订单编号样例前10个：", diagnostics.get("订单编号样例前10个", []))
        st.dataframe(
            diagnostics.get("豁免文件前10行", pd.DataFrame()),
            use_container_width=True,
        )


def analyze_pdd_exemption(
    order_file, exemption_file, start_date, end_date
) -> tuple[dict, dict]:
    order_file.seek(0)
    exemption_file.seek(0)
    orders_df = _load_order_table(order_file)
    exemption_df = _load_exemption_table(exemption_file)
    diagnostics = _build_file_diagnostics(
        order_file, exemption_file, orders_df, exemption_df
    )
    result = build_promotion_exemption_analysis(
        orders_df,
        exemption_df,
        (
            (start_date, end_date)
            if start_date is not None and end_date is not None
            else None
        ),
    )
    return result, diagnostics


def _read_orders_for_date_defaults(order_file) -> pd.DataFrame | None:
    try:
        return _load_order_table(order_file)
    except Exception as exc:
        st.error(f"订单文件读取失败：{exc}")
        return None


def render(
    default_orders: pd.DataFrame | None = None, key_prefix: str = "promotion_exemption"
) -> None:
    st.subheader("推广订单豁免分析")
    st.caption(
        "用于识别退款成功但未出现在推广豁免清单中的订单，并按商品、订单状态、判定分类汇总。"
    )

    st.markdown("### 数据上传")
    c1, c2 = st.columns(2)
    with c1:
        order_file = st.file_uploader(
            "上传拼多多订单明细", type=["csv", "xlsx"], key="pdd_order_file"
        )
    with c2:
        exemption_file = st.file_uploader(
            "上传拼多多推广豁免订单数据", type=["xlsx"], key="pdd_exemption_file"
        )

    if order_file is None or exemption_file is None:
        st.warning("请上传拼多多订单明细和拼多多推广豁免订单数据后开始分析。")
        return

    orders_for_dates = _read_orders_for_date_defaults(order_file)
    if orders_for_dates is None:
        return

    start_date = None
    end_date = None
    pay_dates = pd.to_datetime(
        orders_for_dates.get("支付时间", pd.Series(dtype=str)), errors="coerce"
    ).dropna()
    if not pay_dates.empty:
        selected_date_range = st.date_input(
            "分析期间（只按订单明细中的支付时间筛选；豁免清单不做日期筛选）",
            value=(pay_dates.min().date(), pay_dates.max().date()),
            key=f"{key_prefix}_date_range",
        )
        if (
            isinstance(selected_date_range, (tuple, list))
            and len(selected_date_range) == 2
        ):
            start_date, end_date = selected_date_range

    try:
        result, diagnostics = analyze_pdd_exemption(
            order_file, exemption_file, start_date, end_date
        )
    except Exception as exc:
        st.error(f"文件读取失败：{exc}")
        return

    _render_file_diagnostics(diagnostics)

    for msg in result.get("messages", []):
        st.warning(msg)

    debug = result.get("debug", {})
    if debug:
        with st.expander("调试信息：豁免订单匹配", expanded=True):
            debug_rows = []
            for label, value in debug.items():
                if isinstance(value, list):
                    value = "、".join(value)
                debug_rows.append({"指标": label, "值": value})
            st.dataframe(
                pd.DataFrame(debug_rows), use_container_width=True, hide_index=True
            )

    overview = result.get("overview", {})
    st.markdown("### 一、总览指标")
    cards = [
        ("支付订单数", overview.get("支付订单数", 0), "int"),
        ("退款成功订单数", overview.get("退款成功订单数", 0), "int"),
        ("已豁免订单数", overview.get("已豁免订单数", 0), "int"),
        ("未豁免订单数", overview.get("未豁免订单数", 0), "int"),
        ("豁免覆盖率", overview.get("豁免覆盖率", 0), "pct"),
        ("已豁免商家实收金额", overview.get("已豁免商家实收金额", 0), "money"),
        ("未豁免商家实收金额", overview.get("未豁免商家实收金额", 0), "money"),
        (
            "疑似应豁免但未豁免订单数",
            overview.get("疑似应豁免但未豁免订单数", 0),
            "int",
        ),
        ("疑似应豁免但未豁免金额", overview.get("疑似应豁免但未豁免金额", 0), "money"),
    ]
    cols = st.columns(3)
    for idx, (label, value, kind) in enumerate(cards):
        cols[idx % 3].metric(label, _metric_value(value, kind))

    st.markdown("### 二、商品汇总")
    st.dataframe(
        _format_table(result.get("product_summary", pd.DataFrame())),
        use_container_width=True,
    )

    st.markdown("### 三、订单状态汇总")
    st.dataframe(
        _format_table(result.get("status_summary", pd.DataFrame())),
        use_container_width=True,
    )

    st.markdown("### 四、判定分类汇总")
    st.dataframe(
        result.get("category_summary", pd.DataFrame()), use_container_width=True
    )

    st.markdown("### 五、未豁免退款订单明细")
    details = result.get("unexempted_details", pd.DataFrame())
    st.dataframe(details, use_container_width=True)

    export_payload = {
        "未豁免退款订单明细": details,
        "疑似应豁免但未豁免": result.get("suspected_details", pd.DataFrame()),
        "商品汇总": result.get("product_summary", pd.DataFrame()),
        "状态汇总": result.get("status_summary", pd.DataFrame()),
        "判定分类汇总": result.get("category_summary", pd.DataFrame()),
        "已解析豁免清单": result.get("exemption_orders", pd.DataFrame()),
    }
    st.download_button(
        "导出推广订单豁免分析 Excel",
        data=to_excel_bytes(export_payload),
        file_name="推广订单豁免分析.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}_download",
    )
