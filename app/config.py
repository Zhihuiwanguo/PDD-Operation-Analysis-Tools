"""业务规则配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BusinessRules:
    bb_platform_fee_rate: float = 0.024
    normal_platform_fee_rate: float = 0.006
    invalid_order_statuses: tuple[str, ...] = ("已取消",)
    invalid_after_sale_statuses: tuple[str, ...] = (
        "未发货退款成功",
        "已发货退款成功",
        "已收货退款成功",
        "退款成功",
        "其他退款成功",
    )
    pending_after_sale_statuses: tuple[str, ...] = ("售后处理中",)
    non_operating_keywords: tuple[str, ...] = ("差价补款", "补差价")
    bb_keywords: tuple[str, ...] = ("百补",)
    effective_order_status_keywords: tuple[str, ...] = ("成交", "已发货", "已收货", "已完成", "已成团")


@dataclass(frozen=True)
class SpecSuggestionThresholds:
    weaken_loss_threshold: float = 0.0
    weaken_invalid_rate_threshold: float = 0.40
    weaken_low_orders_threshold: int = 20
    weaken_low_sales_qty_threshold: float = 30

    main_push_orders_threshold: int = 80
    main_push_sales_qty_threshold: float = 120
    main_push_margin_threshold: float = 0.18
    main_push_avg_profit_threshold: float = 6.0

    traffic_sales_qty_threshold: float = 150
    traffic_avg_profit_upper: float = 5.5

    profit_margin_threshold: float = 0.40
    profit_per_order_threshold: float = 10.0


@dataclass(frozen=True)
class BaibuConclusionThresholds:
    scale_advantage_ratio: float = 1.2
    profit_advantage_ratio: float = 1.1
    efficiency_advantage_delta: float = 0.1


@dataclass(frozen=True)
class AlertThresholds:
    loss_link_contribution_threshold: float = 0.0
    spec_high_invalid_rate_threshold: float = 0.35
    spec_high_profit_margin_threshold: float = 0.35
    spec_low_sales_qty_threshold: float = 50
    spec_low_valid_orders_threshold: int = 30
    product_profit_positive_threshold: float = 0.0
    product_unscaled_revenue_threshold: float = 20000.0


@dataclass
class AppConfig:
    business_rules: BusinessRules = field(default_factory=BusinessRules)
    spec_thresholds: SpecSuggestionThresholds = field(default_factory=SpecSuggestionThresholds)
    baibu_conclusion_thresholds: BaibuConclusionThresholds = field(default_factory=BaibuConclusionThresholds)
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    sample_data_dir: str = field(default_factory=lambda: str(Path(__file__).resolve().parent.parent / "sample_data"))


CONFIG = AppConfig()
