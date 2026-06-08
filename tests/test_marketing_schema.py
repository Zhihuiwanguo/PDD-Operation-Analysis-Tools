import pandas as pd

from app.marketing_schema import build_discount_split, standardize_promotion_table


def test_old_promotion_may_spend_maps_to_promo_only():
    df = pd.DataFrame({"日期": ["2026-05-20"], "商品ID": ["1001"], "实际成交花费(元)": [12.5], "实际成交金额": [100]})
    out = standardize_promotion_table(df)
    row = out.iloc[0]
    assert row["promo_spend"] == 12.5
    assert row["settlement_coupon_spend"] == 0
    assert row["marketing_total_spend"] == 12.5
    assert row["data_version"] == "old_promotion"


def test_new_marketing_after_20260602_uses_promo_plus_coupon():
    df = pd.DataFrame({"日期": ["2026-06-02"], "商品ID": ["1001"], "推广成交花费": [20], "结算券花费": [5], "总营销花费": [25]})
    out = standardize_promotion_table(df)
    row = out.iloc[0]
    assert row["promo_spend"] == 20
    assert row["settlement_coupon_spend"] == 5
    assert row["marketing_total_spend"] == 25
    assert row["data_version"] == "new_marketing"


def test_mixed_file_detects_version_by_row_date():
    df = pd.DataFrame({
        "日期": ["2026-06-01", "2026-06-02"],
        "商品ID": ["1001", "1001"],
        "实际成交花费(元)": [10, 0],
        "推广成交花费": [0, 20],
        "结算券花费": [7, 5],
    })
    out = standardize_promotion_table(df)
    assert out.loc[out["date"] == pd.Timestamp("2026-06-01"), "data_version"].iloc[0] == "old_promotion"
    assert out.loc[out["date"] == pd.Timestamp("2026-06-01"), "settlement_coupon_spend"].iloc[0] == 0
    assert out.loc[out["date"] == pd.Timestamp("2026-06-02"), "data_version"].iloc[0] == "new_marketing"


def test_profit_formula_only_deducts_promo_spend():
    merchant_income = 100
    product_cost = 30
    shipping = 8
    platform_fee = 2
    promo_spend = 10
    settlement_coupon_spend = 5
    correct_profit = merchant_income - product_cost - shipping - platform_fee - promo_spend
    wrong_profit = correct_profit - settlement_coupon_spend
    assert correct_profit == 50
    assert wrong_profit != correct_profit


def test_discount_split_store_discount_minus_settlement_coupon():
    orders = pd.DataFrame({
        "订单分类": ["有效"], "订单成交时间": ["2026-06-02"], "店铺名称": ["A店"], "商品id": ["1001"], "商品": ["商品A"],
        "标准产品名称": ["产品A"], "商品总价(元)": [100], "店铺优惠折扣(元)": [12], "平台优惠折扣(元)": [3],
        "用户实付金额(元)": [85], "商家实收金额(元)": [88],
    })
    promo = standardize_promotion_table(pd.DataFrame({"日期": ["2026-06-02"], "店铺名称": ["A店"], "商品ID": ["1001"], "推广成交花费": [10], "结算券花费": [5]}))
    out = build_discount_split(orders, promo)
    assert out.iloc[0]["店铺设置优惠金额"] == 7


def test_total_row_is_removed_from_marketing_table():
    df = pd.DataFrame({"日期": ["2026-06-02", "总计"], "商品ID": ["1001", "总计"], "推广成交花费": [20, 999], "结算券花费": [5, 999]})
    out = standardize_promotion_table(df)
    assert len(out) == 1
    assert out["promo_spend"].sum() == 20
    assert out["marketing_total_spend"].sum() == 25
