import pandas as pd

from app.analyzers import _analyze_overview, _analyze_promotion
from app.marketing_schema import standardize_promotion_table


def _orders():
    return pd.DataFrame(
        {
            "订单分类": ["有效", "有效", "无效"],
            "商品id": ["1001", "1002", "1001"],
            "商品": ["商品A", "商品B", "商品A"],
            "标准产品名称": ["产品A", "产品B", "产品A"],
            "商品总价(元)": [120, 80, 120],
            "用户实付金额(元)": [100, 70, 100],
            "商家实收金额(元)": [90, 60, 90],
            "产品总成本": [30, 50, 30],
            "快递费": [8, 7, 8],
            "平台扣点": [2, 1, 2],
            "商品数量(件)": [2, 1, 2],
            "产品毛利额": [60, 10, 60],
            "产品毛利率": [60 / 90, 10 / 60, 60 / 90],
            "扣快递费毛利额": [52, 3, 52],
            "扣快递费毛利率": [52 / 90, 3 / 60, 52 / 90],
            "订单侧估算毛利": [50, 2, 50],
            "是否支付订单": [True, True, True],
            "是否退款成功": [False, False, True],
            "是否售后处理中": [False, False, False],
            "是否未发货退款成功": [False, False, False],
            "是否未成交退款成功": [False, False, False],
            "是否发货后退款成功": [False, False, True],
            "是否收货后退款成功": [False, False, False],
            "商品件数_退款口径": [2, 1, 2],
            "商品总价_退款口径": [120, 80, 120],
            "用户实付_退款口径": [100, 70, 100],
            "商家实收_退款口径": [90, 60, 90],
            "退款成功商家实收金额": [0, 0, 90],
            "售后处理中商家实收金额": [0, 0, 0],
        }
    )


def test_settlement_coupon_aliases_and_numeric_cleanup_are_supported():
    promo = pd.DataFrame(
        {
            "日期": ["2026-06-02"],
            "商品ID": ["1001"],
            "推广成交花费(元)": ["1,000.50"],
            "推广结算券优惠金额(元)": ["--"],
            "推广成交金额(元)": ["3,000"],
        }
    )

    out = standardize_promotion_table(promo)

    assert out.iloc[0]["promo_spend"] == 1000.5
    assert out.iloc[0]["settlement_coupon_spend"] == 0
    assert out.iloc[0]["ad_transaction_amount"] == 3000


def test_overview_uses_merchant_income_for_margin_and_does_not_double_deduct_coupon():
    promo_by_product = pd.DataFrame(
        {
            "商品ID": ["1001", "1002"],
            "推广成交花费": [10, 20],
            "结算券花费": [5, 6],
            "商品营销总花费": [15, 26],
        }
    )

    result = _analyze_overview(_orders(), 30, promo_by_product)
    metrics = result["metrics"]

    assert metrics["商家实收"] == 150
    assert metrics["产品总成本"] == 80
    assert metrics["产品毛利额"] == 70
    assert metrics["产品毛利率"] == 70 / 150
    assert metrics["快递费"] == 15
    assert metrics["扣快递费毛利额"] == 55
    assert metrics["扣快递费毛利率"] == 55 / 150
    assert metrics["结算券总额"] == 11
    assert metrics["店铺扣推广后贡献毛利"] == 22  # (50 + 2) - (10 + 20), no coupon double deduction


def test_promotion_performance_has_platform_and_financial_roi():
    promo = pd.DataFrame(
        {
            "日期": ["2026-06-02", "2026-06-02"],
            "商品ID": ["1001", "1002"],
            "商品名称": ["商品A", "商品B"],
            "推广成交花费(元)": [10, 20],
            "推广成交金额(元)": [100, 80],
            "结算券金额(元)": [5, 6],
            "成交订单数": [1, 1],
            "成交件数": [2, 1],
        }
    )

    result = _analyze_promotion(promo, orders=_orders())
    overview = result["overview"]
    perf = result["performance"].set_index("商品ID")

    assert overview["平台ROI"] == 180 / 30
    assert overview["财务ROI"] == 150 / 30
    assert overview["推广费率"] == 30 / 150
    assert overview["结算券总额"] == 11
    assert overview["扣推广后毛利"] == 22
    assert perf.loc["1001", "平台ROI"] == 10
    assert perf.loc["1001", "财务ROI"] == 9
    assert perf.loc["1002", "扣推广后毛利"] == -18
    assert "建议停投" in perf.loc["1002", "判断标签"]


def test_empty_promotion_analysis_returns_zero_overview_without_error():
    result = _analyze_promotion(pd.DataFrame(), orders=_orders())
    assert result["overview"]["推广成交花费"] == 0
    assert result["performance"].empty
