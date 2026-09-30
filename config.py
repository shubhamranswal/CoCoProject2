"""Centralized configuration management for Factory Reliability Command Center.

Follows AGENT.md:
- Configuration over hardcoding
- Environment-driven (DEV, TEST, DEMO, PRODUCTION)
- Secrets never hardcoded
- Storage backend selection (in_memory vs snowflake)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

StorageBackendType = Literal["in_memory", "snowflake"]
EnvironmentType = Literal["development", "test", "demo", "production"]


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_ACCOUNT", ""))
    user: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_PASSWORD", ""))
    warehouse: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"))
    database: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_DATABASE", "FACTORY_RELIABILITY_DEV"))
    schema: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_SCHEMA", "FACTORY_CORE"))
    role: str = field(default_factory=lambda: os.getenv("SNOWFLAKE_ROLE", "RELIABILITY_ENGINEER"))

    @property
    def is_configured(self) -> bool:
        """Returns True only if essential credentials are populated."""
        return bool(self.account and self.user and self.password)


@dataclass(frozen=True)
class ReliabilityThresholds:
    anomaly_zscore_threshold: float = field(
        default_factory=lambda: float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "2.5"))
    )
    failure_risk_alert_threshold: float = field(
        default_factory=lambda: float(os.getenv("FAILURE_RISK_ALERT_THRESHOLD", "0.75"))
    )
    bearing_vibration_rms_limit_g: float = field(
        default_factory=lambda: float(os.getenv("BEARING_VIBRATION_RMS_LIMIT_G", "0.75"))
    )
    temperature_warning_limit_c: float = field(
        default_factory=lambda: float(os.getenv("TEMPERATURE_WARNING_LIMIT_C", "75.0"))
    )


@dataclass(frozen=True)
class FeatureFlags:
    enable_auto_work_orders: bool = field(
        default_factory=lambda: os.getenv("ENABLE_AUTO_WORK_ORDERS", "false").lower() == "true"
    )
    require_human_approval_for_critical_assets: bool = field(
        default_factory=lambda: os.getenv("REQUIRE_HUMAN_APPROVAL_FOR_CRITICAL_ASSETS", "true").lower() == "true"
    )


@dataclass(frozen=True)
class AppConfig:
    app_name: str = field(
        default_factory=lambda: os.getenv("APP_NAME", "Factory Reliability Command Center")
    )
    env: EnvironmentType = field(
        default_factory=lambda: os.getenv("APP_ENV", "development")  # type: ignore
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    storage_backend: StorageBackendType = field(
        default_factory=lambda: os.getenv("STORAGE_BACKEND", "in_memory")  # type: ignore
    )
    snowflake: SnowflakeConfig = field(default_factory=SnowflakeConfig)
    thresholds: ReliabilityThresholds = field(default_factory=ReliabilityThresholds)
    features: FeatureFlags = field(default_factory=FeatureFlags)

    def is_production(self) -> bool:
        return self.env == "production"

    def is_snowflake_backend(self) -> bool:
        return self.storage_backend == "snowflake" and self.snowflake.is_configured


def get_config() -> AppConfig:
    """Return active application configuration instance."""
    return AppConfig()
