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
    weaken_invalid_rate_threshold: float = 0.45
    profit_margin_threshold: float = 0.35
    profit_per_order_threshold: float = 8.0
    main_push_orders_threshold: int = 100
    main_push_margin_threshold: float = 0.15


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
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)
    sample_data_dir: str = field(default_factory=lambda: str(Path(__file__).resolve().parent.parent / "sample_data"))


CONFIG = AppConfig()
