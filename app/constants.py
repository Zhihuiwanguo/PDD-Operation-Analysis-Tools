"""字段常量与文件类型定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadSpec:
    key: str
    label: str
    required_columns: tuple[str, ...]


UPLOAD_SPECS: tuple[UploadSpec, ...] = (
    UploadSpec(
        key="product_master",
        label="标准产品主档上传",
        required_columns=("标准产品ID", "标准产品名称", "单个产品成本"),
    ),
    UploadSpec(
        key="sales_spec_mapping",
        label="商品规格映射上传",
        required_columns=("销售规格ID", "标准产品ID", "产品总成本", "快递费"),
    ),
    UploadSpec(
        key="link_spec_mapping",
        label="店铺链接规格映射上传",
        required_columns=("商品ID", "商品规格", "销售规格ID", "销售规格名称"),
    ),
    UploadSpec(
        key="orders",
        label="订单明细上传",
        required_columns=(
            "订单号",
            "订单状态",
            "售后状态",
            "商品id",
            "商品规格",
            "订单成交时间",
            "用户实付金额(元)",
            "商家实收金额(元)",
        ),
    ),
    UploadSpec(
        key="promotion",
        label="每日商品ID推广数据上传",
        required_columns=("日期", "商品ID", "实际成交花费(元)"),
    ),
    UploadSpec(
        key="cashflow",
        label="店铺每日推广费流水上传",
        required_columns=("时间", "流水类型", "交易金额", "交易摘要"),
    ),
)

UPLOAD_SPEC_MAP = {spec.key: spec for spec in UPLOAD_SPECS}

PROMOTION_SPEND_COLUMN_ALIASES: tuple[str, ...] = (
    "实际成交花费(元)",
    "实际成交花费",
    "成交花费",
    "花费",
    "推广花费",
    "消耗",
)

PROMOTION_DATE_COLUMN_ALIASES: tuple[str, ...] = ("日期", "时间", "统计日期", "推广日期")
PROMOTION_GOODS_ID_COLUMN_ALIASES: tuple[str, ...] = ("商品ID", "商品id", "商品 Id", "goods_id")


DATE_CANDIDATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "orders": ("订单成交时间", "支付时间"),
    "promotion": PROMOTION_DATE_COLUMN_ALIASES,
    "cashflow": ("时间", "日期"),
}

NUMERIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "orders": ("用户实付金额(元)", "商家实收金额(元)", "商品数量(件)"),
    "sales_spec_mapping": ("产品总成本", "快递费"),
    "promotion": (
        "实际成交花费(元)",
        "结算金额(元)",
        "曝光量",
        "点击量",
        "成交订单数",
        "净交易额(元)",
    ),
    "cashflow": ("交易金额", "现金支出"),
}
