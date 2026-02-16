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
    
    def test_valid_endpoint_with_port(self):
        """Test valid OTLP endpoint with explicit port."""
        config = TracingConfig(otlp_endpoint="http://localhost:4317")
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.get_port() == 4317
    
    def test_valid_endpoint_https(self):
        """Test valid HTTPS OTLP endpoint."""
        config = TracingConfig(otlp_endpoint="https://otel.example.com:4318")
        assert config.otlp_endpoint == "https://otel.example.com:4318"
        assert config.get_port() == 4318
    
    def test_valid_endpoint_with_ip(self):
        """Test valid OTLP endpoint with IP address."""
        config = TracingConfig(otlp_endpoint="http://192.168.1.100:4317")
        assert config.otlp_endpoint == "http://192.168.1.100:4317"
        assert config.get_port() == 4317
    
    def test_endpoint_with_trailing_slash(self):
        """Test endpoint with trailing slash - should validate but extract port correctly."""
        config = TracingConfig(otlp_endpoint="http://localhost:4317/")
        assert config.get_port() == 4317
    
    def test_endpoint_with_path(self):
        """Test endpoint with path - should validate and extract port correctly."""
        # Note: This produces a warning in logs but doesn't raise
        config = TracingConfig(otlp_endpoint="http://localhost:4317/v1/traces")
        assert config.get_port() == 4317
    
    def test_endpoint_with_query(self):
        """Test endpoint with query parameters - should validate and extract port correctly."""
        # Note: This produces a warning in logs but doesn't raise
        config = TracingConfig(otlp_endpoint="http://localhost:4317?timeout=5000")
        assert config.get_port() == 4317
    
    def test_endpoint_without_port_fails(self):
        """Test that endpoint without explicit port raises ValueError."""
        with pytest.raises(ValueError, match="must include an explicit port"):
            TracingConfig(otlp_endpoint="http://localhost")
    
    def test_endpoint_without_port_with_path_fails(self):
        """Test that endpoint without port but with path raises ValueError."""
        with pytest.raises(ValueError, match="must include an explicit port"):
            TracingConfig(otlp_endpoint="http://localhost/v1/traces")
    
    def test_endpoint_invalid_scheme_fails(self):
        """Test that endpoint with invalid scheme raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scheme"):
            TracingConfig(otlp_endpoint="ftp://localhost:4317")
    
    def test_endpoint_no_scheme_fails(self):
        """Test that endpoint without scheme raises ValueError."""
        with pytest.raises(ValueError, match="Invalid scheme"):
            TracingConfig(otlp_endpoint="localhost:4317")
    
    def test_endpoint_invalid_port_range_fails(self):
        """Test that endpoint with port out of range raises ValueError."""
        # urlparse catches this with "Port out of range" message
        with pytest.raises(ValueError, match="Port out of range|out of valid range"):
            TracingConfig(otlp_endpoint="http://localhost:99999")
    
    def test_endpoint_port_zero_fails(self):
        """Test that endpoint with port 0 raises ValueError."""
        with pytest.raises(ValueError, match="out of valid range"):
            TracingConfig(otlp_endpoint="http://localhost:0")
    
    def test_get_port_method(self):
        """Test the get_port() convenience method."""
        config = TracingConfig(otlp_endpoint="http://example.com:8080")
        assert config.get_port() == 8080
    
    def test_default_endpoint_valid(self):
        """Test that the default endpoint is valid."""
        config = TracingConfig()
        assert config.otlp_endpoint == "http://localhost:4317"
        assert config.get_port() == 4317
