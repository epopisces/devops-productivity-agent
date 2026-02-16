"""Tests for configuration module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from app.config import load_config, get_config, AppConfig, TracingConfig


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_config_defaults(self):
        """Test loading config with no file and no env vars."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.config.load_dotenv"):
                config = load_config(config_path="/nonexistent/path.yaml")
        
        assert config.models.ollama.host == "http://localhost:11434"
        assert config.models.ollama.model_id == "qwen3:1.7b"
        assert config.scraper.timeout == 30
    
    def test_load_config_from_yaml(self):
        """Test loading config from YAML file."""
        yaml_content = {
            "models": {
                "ollama": {
                    "host": "http://custom:11434",
                    "model_id": "custom-model"
                }
            },
            "scraper": {
                "timeout": 60
            }
        }
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_path = f.name
        
        try:
            with patch.dict(os.environ, {}, clear=True):
                with patch("app.config.load_dotenv"):
                    config = load_config(config_path=temp_path)
            
            assert config.models.ollama.host == "http://custom:11434"
            assert config.models.ollama.model_id == "custom-model"
            assert config.scraper.timeout == 60
        finally:
            os.unlink(temp_path)
    
    def test_load_config_env_override(self):
        """Test that environment variables override YAML config."""
        yaml_content = {
            "models": {
                "ollama": {
                    "host": "http://yaml:11434",
                    "model_id": "yaml-model"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(yaml_content, f)
            temp_path = f.name
        
        try:
            env_vars = {
                "OLLAMA_HOST": "http://env:11434",
                "OLLAMA_MODEL_ID": "env-model"
            }
            with patch.dict(os.environ, env_vars, clear=True):
                with patch("app.config.load_dotenv"):
                    config = load_config(config_path=temp_path)
            
            # Env vars should take precedence
            assert config.models.ollama.host == "http://env:11434"
            assert config.models.ollama.model_id == "env-model"
        finally:
            os.unlink(temp_path)


class TestAppConfig:
    """Tests for AppConfig model."""
    
    def test_config_validation(self):
        """Test config model validation."""
        config = AppConfig()
        
        assert isinstance(config.models.ollama.host, str)
        assert isinstance(config.models.ollama.model_id, str)
        assert isinstance(config.scraper.timeout, int)
    
    def test_config_with_custom_values(self):
        """Test creating config with custom values."""
        from app.config import OllamaConfig, ModelsConfig, ScraperConfig
        
        config = AppConfig(
            models=ModelsConfig(
                ollama=OllamaConfig(
                    host="http://test:1234",
                    model_id="test-model"
                )
            ),
            scraper=ScraperConfig(
                timeout=120,
                max_content_length=100000
            )
        )
        
        assert config.models.ollama.host == "http://test:1234"
        assert config.scraper.timeout == 120
        assert config.scraper.max_content_length == 100000


class TestTracingConfig:
    """Tests for TracingConfig validation."""
    
    def test_valid_port_default(self):
        """Test default port value."""
        config = TracingConfig()
        assert config.vs_code_extension_port == 4317
    
    def test_valid_port_custom(self):
        """Test custom port value."""
        config = TracingConfig(vs_code_extension_port=8080)
        assert config.vs_code_extension_port == 8080
    
    def test_port_minimum_valid(self):
        """Test minimum valid port (1)."""
        config = TracingConfig(vs_code_extension_port=1)
        assert config.vs_code_extension_port == 1
    
    def test_port_maximum_valid(self):
        """Test maximum valid port (65535)."""
        config = TracingConfig(vs_code_extension_port=65535)
        assert config.vs_code_extension_port == 65535
    
    def test_port_zero_fails(self):
        """Test that port 0 raises ValidationError."""
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            TracingConfig(vs_code_extension_port=0)
    
    def test_port_negative_fails(self):
        """Test that negative port raises ValidationError."""
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            TracingConfig(vs_code_extension_port=-1)
    
    def test_port_too_large_fails(self):
        """Test that port > 65535 raises ValidationError."""
        with pytest.raises(ValueError, match="less than or equal to 65535"):
            TracingConfig(vs_code_extension_port=99999)
    
    def test_port_type_coercion(self):
        """Test that string port is coerced to int."""
        config = TracingConfig(vs_code_extension_port="4317")
        assert config.vs_code_extension_port == 4317
        assert isinstance(config.vs_code_extension_port, int)
