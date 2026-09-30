"""Tests for configuration layer."""

import os
from config import AppConfig, SnowflakeConfig, get_config


def test_default_config_loading():
    cfg = get_config()
    assert cfg.app_name == "Factory Reliability Command Center"
    assert cfg.env in ("development", "test", "demo", "production")
    assert cfg.thresholds.anomaly_zscore_threshold > 0.0
    assert cfg.thresholds.bearing_vibration_rms_limit_g == 0.75


def test_snowflake_config_empty_detection():
    # When account or user is empty, is_configured should be False
    empty_sf = SnowflakeConfig(account="", user="", password="")
    assert not empty_sf.is_configured

    partial_sf = SnowflakeConfig(account="test-acc", user="", password="secret")
    assert not partial_sf.is_configured

    valid_sf = SnowflakeConfig(account="test-acc", user="admin", password="secret")
    assert valid_sf.is_configured


def test_custom_environment_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("STORAGE_BACKEND", "snowflake")
    monkeypatch.setenv("BEARING_VIBRATION_RMS_LIMIT_G", "0.85")

    cfg = AppConfig()
    assert cfg.is_production()
    assert cfg.storage_backend == "snowflake"
    assert cfg.thresholds.bearing_vibration_rms_limit_g == 0.85
