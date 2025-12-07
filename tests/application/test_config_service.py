"""Tests for configuration loading and ConfigService."""
import sys
import os
import json
import tempfile
from pathlib import Path
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo74.fastapi_openai_rag.application.services.config_service import ConfigService
from ygo74.fastapi_openai_rag.domain.models.configuration import AppConfig
from ygo74.fastapi_openai_rag.domain.models.rate_limit_config import (
    GlobalRateLimitConfig,
    TimeWindowConfig
)


class TestConfigServiceGlobalRateLimits:
    """Test suite for ConfigService rate limit loading."""

    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create a temporary config file for testing."""
        config_file = tmp_path / "test_config.json"
        yield config_file
        # Cleanup after test
        if config_file.exists():
            config_file.unlink()

    @pytest.fixture
    def config_service_with_temp_file(self, temp_config_file):
        """Create ConfigService instance pointing to temp file."""
        # Reset singleton state
        ConfigService._instance = None
        ConfigService._config = None
        ConfigService._last_modified = None
        ConfigService._config_file_path = str(temp_config_file)

        # Create service (but don't initialize DB)
        service = ConfigService.__new__(ConfigService)
        service._initialized = False
        service._config_file_path = str(temp_config_file)
        service._last_modified = None
        service._config = None

        return service

    def test_load_config_with_rate_limits_section(self, temp_config_file, config_service_with_temp_file):
        """Test loading config.json with rate_limits section."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "00:00",
                            "to_time": "23:59",
                            "max_requests": 1000,
                            "max_tokens": 500000
                        }
                    ]
                }
            }
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is not None
        assert global_limits.enabled is True
        assert len(global_limits.windows) == 1
        assert global_limits.windows[0].from_time == "00:00"
        assert global_limits.windows[0].to_time == "23:59"
        assert global_limits.windows[0].max_requests == 1000
        assert global_limits.windows[0].max_tokens == 500000

    def test_load_config_without_rate_limits_section(self, temp_config_file, config_service_with_temp_file):
        """Test loading config.json without rate_limits section."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db"
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is None

    def test_load_config_with_disabled_rate_limits(self, temp_config_file, config_service_with_temp_file):
        """Test loading config with disabled global rate limits."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": False,
                    "windows": []
                }
            }
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is not None
        assert global_limits.enabled is False
        assert len(global_limits.windows) == 0

    def test_load_config_with_multiple_time_windows(self, temp_config_file, config_service_with_temp_file):
        """Test loading config with multiple time windows."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "00:00",
                            "to_time": "08:00",
                            "max_requests": 100,
                            "max_tokens": 50000
                        },
                        {
                            "from_time": "08:00",
                            "to_time": "17:00",
                            "max_requests": 1000,
                            "max_tokens": 500000
                        },
                        {
                            "from_time": "17:00",
                            "to_time": "23:59",
                            "max_requests": 200,
                            "max_tokens": 100000
                        }
                    ]
                }
            }
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is not None
        assert len(global_limits.windows) == 3
        assert global_limits.windows[0].max_requests == 100
        assert global_limits.windows[1].max_requests == 1000
        assert global_limits.windows[2].max_requests == 200

    def test_reload_config_detects_file_changes(self, temp_config_file, config_service_with_temp_file):
        """Test ConfigService detects config file changes."""
        # arrange - initial config
        initial_config = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "00:00",
                            "to_time": "23:59",
                            "max_requests": 100,
                            "max_tokens": None
                        }
                    ]
                }
            }
        }
        temp_config_file.write_text(json.dumps(initial_config))
        config_service_with_temp_file.reload_config()

        # act - update config file
        import time
        time.sleep(0.1)  # Ensure different modification time

        updated_config = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "00:00",
                            "to_time": "23:59",
                            "max_requests": 2000,
                            "max_tokens": None
                        }
                    ]
                }
            }
        }
        temp_config_file.write_text(json.dumps(updated_config))

        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert - should have new value
        assert global_limits is not None
        assert global_limits.windows[0].max_requests == 2000

    def test_get_global_rate_limits_returns_none_when_no_config_loaded(self, config_service_with_temp_file):
        """Test get_global_rate_limits() returns None when no config loaded."""
        # arrange - no config file
        # config_service_with_temp_file has no file created

        # act
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is None

    def test_load_config_with_time_window_using_seconds(self, temp_config_file, config_service_with_temp_file):
        """Test loading time window with HH:MM:SS format."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "09:30:15",
                            "to_time": "17:45:30",
                            "max_requests": 500,
                            "max_tokens": None
                        }
                    ]
                }
            }
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is not None
        assert global_limits.windows[0].from_time == "09:30:15"
        assert global_limits.windows[0].to_time == "17:45:30"

        # Verify conversion to time objects works
        from_time = global_limits.windows[0].get_from_time()
        to_time = global_limits.windows[0].get_to_time()
        assert from_time.hour == 9
        assert from_time.minute == 30
        assert from_time.second == 15
        assert to_time.hour == 17
        assert to_time.minute == 45
        assert to_time.second == 30

    def test_load_config_with_only_token_limits(self, temp_config_file, config_service_with_temp_file):
        """Test loading config with only token limits (no request limits)."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "00:00",
                            "to_time": "23:59",
                            "max_requests": None,
                            "max_tokens": 1000000
                        }
                    ]
                }
            }
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config_service_with_temp_file.reload_config()
        global_limits = config_service_with_temp_file.get_global_rate_limits()

        # assert
        assert global_limits is not None
        assert global_limits.windows[0].max_requests is None
        assert global_limits.windows[0].max_tokens == 1000000


class TestAppConfigRateLimitsIntegration:
    """Test AppConfig loading rate_limits section."""

    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create a temporary config file for testing."""
        config_file = tmp_path / "test_config.json"
        yield config_file
        if config_file.exists():
            config_file.unlink()

    def test_app_config_loads_rate_limits_from_json(self, temp_config_file):
        """Test AppConfig.load_from_json() parses rate_limits section."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db",
            "rate_limits": {
                "global": {
                    "enabled": True,
                    "windows": [
                        {
                            "from_time": "00:00",
                            "to_time": "23:59",
                            "max_requests": 1500,
                            "max_tokens": 750000
                        }
                    ]
                }
            }
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config = AppConfig.load_from_json(str(temp_config_file))

        # assert
        assert config.rate_limits is not None
        assert config.rate_limits.global_limits is not None
        assert config.rate_limits.global_limits.enabled is True
        assert len(config.rate_limits.global_limits.windows) == 1
        assert config.rate_limits.global_limits.windows[0].max_requests == 1500

    def test_app_config_handles_missing_rate_limits_section(self, temp_config_file):
        """Test AppConfig handles missing rate_limits section gracefully."""
        # arrange
        config_data = {
            "model_configs": [],
            "db_type": "sqlite",
            "db_url": "sqlite:///test.db"
        }

        temp_config_file.write_text(json.dumps(config_data))

        # act
        config = AppConfig.load_from_json(str(temp_config_file))

        # assert
        assert config.rate_limits is None
