from __future__ import annotations

import pandas as pd

from app.analyzers import build_analysis_context
from app.refund_analysis import build_refund_analysis


def test_refund_analysis_classifies_core_refund_types():
    orders = pd.DataFrame(
        [
            {"订单号": "1", "支付时间": "2026-06-01 10:00:00", "订单状态": "待发货", "售后状态": "退款成功", "发货状态": "未发货", "商品ID": "100", "商品名称": "A", "商家实收": 10, "用户实付": 10, "商品总价": 12, "商品数量": 1},
            {"订单号": "2", "支付时间": "2026-06-01 11:00:00", "订单状态": "已收货", "售后状态": "退款成功", "发货状态": "已签收", "商品ID": "100", "商品名称": "A", "商家实收": 20, "用户实付": 20, "商品总价": 22, "商品数量": 2},
            {"订单号": "3", "支付时间": "2026-06-02 11:00:00", "订单状态": "交易关闭", "售后状态": "退款成功", "发货状态": "", "商品ID": "200", "商品名称": "B", "商家实收": 30, "用户实付": 30, "商品总价": 32, "商品数量": 3},
            {"订单号": "4", "支付时间": "2026-06-02 12:00:00", "订单状态": "已发货", "售后状态": "待商家处理", "发货状态": "运输中", "商品ID": "200", "商品名称": "B", "商家实收": 40, "用户实付": 40, "商品总价": 42, "商品数量": 4},
        ]
    )

    result = build_refund_analysis(orders)
    overview = result["overview"]

    assert overview["支付订单数"] == 4
    assert overview["退款成功订单数"] == 3
    assert overview["未发货退款订单数"] == 2
    assert overview["未成交退款订单数"] == 1
    assert overview["发货后退款订单数"] == 1
    assert overview["售后处理中订单数"] == 1
    assert overview["剔除退款后商家实收"] == 40
    assert overview["确认有效商家实收"] == 0


def test_link_analysis_groups_only_by_goods_id_and_merges_promo_once():
    orders = pd.DataFrame(
        [
            {"订单号": "1", "支付时间": "2026-06-01", "订单成交时间": "2026-06-01", "订单状态": "已收货", "售后状态": "", "发货状态": "已签收", "商品ID": "100", "商品": "商品A-规格1", "商品规格": "规格1", "商家实收": 100, "用户实付": 100, "商品总价": 100, "商品数量": 1},
            {"订单号": "2", "支付时间": "2026-06-01", "订单成交时间": "2026-06-01", "订单状态": "已收货", "售后状态": "退款成功", "发货状态": "已签收", "商品ID": "100", "商品": "商品A-规格2", "商品规格": "规格2", "商家实收": 50, "用户实付": 50, "商品总价": 50, "商品数量": 1},
        ]
    )
    tables = {
        "orders": orders,
        "link_spec_mapping": pd.DataFrame({"商品ID": ["100", "100"], "商品规格": ["规格1", "规格2"], "销售规格ID": ["s1", "s2"], "销售规格名称": ["规格1", "规格2"]}),
        "sales_spec_mapping": pd.DataFrame({"销售规格ID": ["s1", "s2"], "标准产品ID": ["p1", "p1"], "产品总成本": [10, 10], "快递费": [2, 2]}),
        "product_master": pd.DataFrame({"标准产品ID": ["p1"], "标准产品名称": ["产品A"], "单个产品成本": [10]}),
        "promotion": pd.DataFrame({"日期": ["2026-06-01"], "商品ID": ["100"], "成交花费": [30]}),
        "cashflow": pd.DataFrame({"时间": ["2026-06-01"], "流水类型": ["支出"], "交易金额": [30], "交易摘要": ["商品推广现金"]}),
    }

    ctx = build_analysis_context(tables)
    link = ctx["link_summary"]

    assert len(link) == 1
    row = link.iloc[0]
    assert row["商品ID"] == "100"
    assert row["商家实收"] == 150
    assert row["成交花费"] == 30
    assert row["退款金额"] == 50
    assert row["剔除退款后商家实收"] == 100
    assert row["ROI"] == 5
    assert row["退款后ROI"] == 100 / 30
