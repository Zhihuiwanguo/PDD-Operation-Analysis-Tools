import pandas as pd

from app.promotion_exemption_analysis import (
    build_promotion_exemption_analysis,
    clean_order_id,
    parse_exemption_orders,
    parse_pdd_exemption_date,
)


def test_clean_order_id_removes_whitespace_and_excel_suffix():
    assert clean_order_id(" 123\t456 ") == "123456"
    assert clean_order_id(123456.0) == "123456"


def test_parse_exemption_orders_extracts_goods_id_and_deduplicates():
    df = pd.DataFrame(
        {
            "商品": ["商品 ID：844471753679 名称A", "商品 ID：844471753679 名称A"],
            "订单编号": [" A001 ", "A001"],
            "订单支付日期": ["2026-06-01", "2026-06-01"],
            "豁免类型": ["退款豁免", "退款豁免"],
            "红包发放日期": ["2026-06-02", "2026-06-02"],
        }
    )
    out = parse_exemption_orders(df)
    assert len(out) == 1
    assert out.loc[0, "商品ID"] == "844471753679"
    assert out.loc[0, "订单编号"] == "A001"


def test_parse_pdd_exemption_date_handles_excel_serial_numbers():
    assert parse_pdd_exemption_date("46174.0") == pd.Timestamp("2026-06-01")
    assert parse_pdd_exemption_date("46183.0") == pd.Timestamp("2026-06-10")
    assert parse_pdd_exemption_date("2026-06-01") == pd.Timestamp("2026-06-01")


def test_exemption_matching_uses_excel_serial_pay_date_without_filter_and_debug_stats():
    orders = pd.DataFrame(
        {
            "订单号": ["1001", "1002", "1003"],
            "支付时间": ["2026-06-01", "2026-06-10", "2026-06-10"],
            "商品id": ["G1", "G1", "G1"],
            "订单状态": ["未发货退款成功"] * 3,
            "售后状态": ["退款成功"] * 3,
            "商家实收金额(元)": [10, 20, 30],
        }
    )
    exemptions = pd.DataFrame(
        {
            "商品": ["商品 ID：G1", "商品 ID：G1", "商品 ID：G1", "商品 ID：G1"],
            "订单编号": ["1001.0", " 1002 ", "1003", ""],
            "订单支付日期": ["46174.0", "46183.0", "46184.0", "46174.0"],
            "豁免类型": ["退款豁免"] * 4,
            "红包发放日期": ["2026-06-02"] * 4,
        }
    )

    result = build_promotion_exemption_analysis(
        orders, exemptions, ("2026-06-01", "2026-06-10")
    )

    assert result["overview"]["已豁免订单数"] == 3
    assert result["overview"]["未豁免订单数"] == 0
    assert set(result["exemption_orders"]["订单编号_clean"]) == {"1001", "1002", "1003"}
    assert result["debug"]["豁免文件原始行数"] == 4
    assert result["debug"]["去掉空订单编号后的行数"] == 3
    assert result["debug"]["订单支付日期_parsed非空行数"] == 3
    assert result["debug"]["用于匹配的豁免行数"] == 3
    assert result["debug"]["两边订单号交集数量"] == 3


def test_build_promotion_exemption_analysis_outputs_metrics_and_categories():
    orders = pd.DataFrame(
        {
            "订单号": ["A001", "A002", "A003", "A004", "A005"],
            "支付时间": ["2026-06-01"] * 5,
            "商品id": ["G1", "G1", "G2", "G3", "G1"],
            "商品": ["商品1", "商品1", "商品2", "商品3", "商品1"],
            "商品规格": ["规格"] * 5,
            "商品数量(件)": [1] * 5,
            "订单状态": [
                "未发货退款成功",
                "未发货退款成功",
                "已发货退款成功",
                "已收货退款成功",
                "已支付",
            ],
            "售后状态": ["退款成功", "退款成功", "", "", ""],
            "商品总价(元)": [10, 20, 30, 40, 50],
            "店铺优惠折扣(元)": [0] * 5,
            "平台优惠折扣(元)": [0] * 5,
            "用户实付金额(元)": [10, 20, 30, 40, 50],
            "商家实收金额(元)": [10, 20, 30, 40, 50],
            "发货时间": ["", "", "2026-06-02", "2026-06-02", ""],
            "确认收货时间": ["", "", "", "2026-06-05", ""],
            "快递公司": [""] * 5,
            "快递单号": [""] * 5,
        }
    )
    exemptions = pd.DataFrame(
        {
            "商品": ["商品 ID：G1"],
            "订单编号": ["A001"],
            "订单支付日期": ["2026-06-01"],
            "豁免类型": ["退款豁免"],
            "红包发放日期": ["2026-06-02"],
        }
    )
    result = build_promotion_exemption_analysis(
        orders, exemptions, ("2026-06-01", "2026-06-01")
    )

    assert result["overview"]["支付订单数"] == 5
    assert result["overview"]["退款成功订单数"] == 4
    assert result["overview"]["已豁免订单数"] == 1
    assert result["overview"]["未豁免订单数"] == 3
    assert result["overview"]["疑似应豁免但未豁免订单数"] == 1
    assert set(result["unexempted_details"]["判定分类"]) == {
        "疑似应豁免但未豁免",
        "发货后退款未豁免",
        "收货后退款未豁免",
    }


def test_exemption_matching_uses_clean_order_ids_without_exemption_pay_date_filter():
    orders = pd.DataFrame(
        {
            "订单号": [" 1001\t", "1002.0", "1003", "1004"],
            "支付时间": ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"],
            "商品id": ["G1", "G1", "G1", "G1"],
            "订单状态": ["未发货退款成功"] * 4,
            "售后状态": ["退款成功"] * 4,
            "商家实收金额(元)": [10, 20, 30, 40],
        }
    )
    exemptions = pd.DataFrame(
        {
            "商品": ["商品 ID：G1", "商品 ID：G1", "商品 ID：G1"],
            "订单编号": ["1001", "1002", "1003"],
            "订单支付日期": ["2026-06-01", "2026-06-02", "2026-06-11"],
            "豁免类型": ["退款豁免"] * 3,
            "红包发放日期": ["2026-06-02", "2026-06-03", "2026-06-12"],
        }
    )

    result = build_promotion_exemption_analysis(
        orders, exemptions, ("2026-06-01", "2026-06-10")
    )

    assert result["overview"]["退款成功订单数"] == 4
    assert result["overview"]["已豁免订单数"] == 3
    assert result["overview"]["未豁免订单数"] == 1
    assert set(result["exemption_orders"]["订单编号_clean"]) == {"1001", "1002", "1003"}


def test_unexempted_reason_classification_uses_goods_history_shipping_receipt_and_amount():
    orders = pd.DataFrame(
        {
            "订单号": ["A001", "A002", "A003", "A004", "A005"],
            "支付时间": ["2026-06-01"] * 5,
            "商品id": ["G1", "G1", "G2", "G3", "G1"],
            "订单状态": [
                "未发货退款成功",
                "退款成功",
                "退款成功",
                "退款成功",
                "未发货退款成功",
            ],
            "售后状态": ["退款成功"] * 5,
            "商家实收金额(元)": [10, 20, 30, 40, 0],
            "发货时间": ["", "2026-06-02", "", "", ""],
            "确认收货时间": ["", "", "2026-06-05", "", ""],
            "快递单号": ["", "", "", "", ""],
        }
    )
    exemptions = pd.DataFrame(
        {
            "商品": ["商品 ID：G1"],
            "订单编号": ["EXEMPTED_OTHER_ORDER"],
            "订单支付日期": ["2026-06-01"],
            "豁免类型": ["退款豁免"],
            "红包发放日期": ["2026-06-02"],
        }
    )

    result = build_promotion_exemption_analysis(orders, exemptions)
    categories = dict(
        zip(
            result["unexempted_details"]["订单号"],
            result["unexempted_details"]["判定分类"],
        )
    )

    assert categories == {
        "A001": "疑似应豁免但未豁免",
        "A002": "发货后退款未豁免",
        "A003": "收货后退款未豁免",
        "A004": "商品ID在豁免清单无记录",
        "A005": "0元/异常订单",
    }
