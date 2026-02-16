"""Tests for tracing module."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.config import TracingConfig
from app.tracing import configure_tracing


class TestConfigureTracing:
    """Tests for configure_tracing function."""
    
    def test_tracing_disabled_by_default(self, caplog):
        """Test that tracing is disabled when enabled=False (default behavior)."""
        config = TracingConfig(enabled=False)
        
        with caplog.at_level(logging.DEBUG, logger="workflow.tracing"):
            configure_tracing(config)
        
        # Should log that tracing is disabled
        assert "Tracing is disabled" in caplog.text
        # Should not attempt to import or configure anything
        assert "OpenTelemetry tracing enabled" not in caplog.text
    
    def test_tracing_disabled_explicit(self, caplog):
        """Test that tracing is disabled when explicitly set to False."""
        config = TracingConfig(enabled=False, otlp_endpoint="http://localhost:4317")
        
        with caplog.at_level(logging.DEBUG, logger="workflow.tracing"):
            configure_tracing(config)
        
        assert "Tracing is disabled" in caplog.text
    
    def test_successful_tracing_configuration(self, caplog):
        """Test successful tracing configuration."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317",
            enable_sensitive_data=False
        )
        
        # Mock the observability module
        mock_configure = MagicMock()
        with patch.dict("sys.modules", {"agent_framework.observability": MagicMock(configure_otel_providers=mock_configure)}):
            with caplog.at_level(logging.INFO, logger="workflow.tracing"):
                configure_tracing(config)
        
        # Verify configure_otel_providers was called with correct args
        mock_configure.assert_called_once_with(
            vs_code_extension_port=4317,
            enable_sensitive_data=False,
        )
        
        # Verify success log message
        assert "OpenTelemetry tracing enabled" in caplog.text
        assert "http://localhost:4317" in caplog.text
        assert "sensitive_data=off" in caplog.text
    
    def test_successful_tracing_with_sensitive_data(self, caplog):
        """Test successful tracing configuration with sensitive data enabled."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317",
            enable_sensitive_data=True
        )
        
        mock_configure = MagicMock()
        with patch.dict("sys.modules", {"agent_framework.observability": MagicMock(configure_otel_providers=mock_configure)}):
            with caplog.at_level(logging.INFO, logger="workflow.tracing"):
                configure_tracing(config)
        
        mock_configure.assert_called_once_with(
            vs_code_extension_port=4317,
            enable_sensitive_data=True,
        )
        
        assert "sensitive_data=on" in caplog.text
    
    def test_successful_tracing_with_custom_port(self, caplog):
        """Test successful tracing configuration with custom port."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://localhost:8080",
            enable_sensitive_data=False
        )
        
        mock_configure = MagicMock()
        with patch.dict("sys.modules", {"agent_framework.observability": MagicMock(configure_otel_providers=mock_configure)}):
            with caplog.at_level(logging.INFO, logger="workflow.tracing"):
                configure_tracing(config)
        
        mock_configure.assert_called_once_with(
            vs_code_extension_port=8080,
            enable_sensitive_data=False,
        )
        
        assert "http://localhost:8080" in caplog.text
    
    def test_import_error_handling(self, caplog):
        """Test handling of ImportError when observability module is missing."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317"
        )
        
        # Simulate ImportError from missing module
        def mock_import(name, *args):
            if name == "agent_framework.observability":
                error = ImportError("No module named 'agent_framework.observability'")
                error.name = "agent_framework.observability"
                raise error
            return __import__(name, *args)
        
        with patch("builtins.__import__", side_effect=mock_import):
            with caplog.at_level(logging.WARNING, logger="workflow.tracing"):
                configure_tracing(config)
        
        # Should log warning about missing module
        assert "required observability module is missing" in caplog.text
        assert "agent_framework.observability" in caplog.text
        # Should not crash or raise exception
    
    def test_import_error_without_name_attribute(self, caplog):
        """Test ImportError handling when error has None as name attribute."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317"
        )
        
        # Simulate ImportError with name=None (default behavior)
        def mock_import(name, *args):
            if name == "agent_framework.observability":
                raise ImportError("Cannot import observability")
            return __import__(name, *args)
        
        with patch("builtins.__import__", side_effect=mock_import):
            with caplog.at_level(logging.WARNING, logger="workflow.tracing"):
                configure_tracing(config)
        
        # Should log warning - ImportError has name=None by default
        assert "required observability module is missing" in caplog.text
        # The error will show (None) since ImportError.name defaults to None
        assert "(None)" in caplog.text
    
    def test_general_exception_handling(self, caplog):
        """Test handling of general exceptions during configuration."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://localhost:4317"
        )
        
        # Mock configure_otel_providers to raise a general exception
        mock_configure = MagicMock(side_effect=RuntimeError("OTLP server not reachable"))
        with patch.dict("sys.modules", {"agent_framework.observability": MagicMock(configure_otel_providers=mock_configure)}):
            with caplog.at_level(logging.ERROR, logger="workflow.tracing"):
                configure_tracing(config)
        
        # Should log error with exception details
        assert "Failed to configure tracing" in caplog.text
        assert "OTLP server not reachable" in caplog.text
    
    def test_invalid_endpoint_caught_by_config_validation(self):
        """Test that invalid endpoints are caught by TracingConfig validation."""
        # This should raise during config creation, not during configure_tracing
        with pytest.raises(ValueError, match="must include an explicit port"):
            TracingConfig(
                enabled=True,
                otlp_endpoint="http://localhost"  # Missing port
            )
    
    def test_get_port_extracts_correctly(self):
        """Test that get_port() correctly extracts port from endpoint."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="http://example.com:9999"
        )
        assert config.get_port() == 9999
    
    def test_https_endpoint(self, caplog):
        """Test tracing configuration with HTTPS endpoint."""
        config = TracingConfig(
            enabled=True,
            otlp_endpoint="https://otel.example.com:4318",
            enable_sensitive_data=False
        )
        
        mock_configure = MagicMock()
        with patch.dict("sys.modules", {"agent_framework.observability": MagicMock(configure_otel_providers=mock_configure)}):
            with caplog.at_level(logging.INFO, logger="workflow.tracing"):
                configure_tracing(config)
        
        mock_configure.assert_called_once_with(
            vs_code_extension_port=4318,
            enable_sensitive_data=False,
        )
        
        assert "https://otel.example.com:4318" in caplog.text
