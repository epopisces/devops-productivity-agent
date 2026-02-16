"""OpenTelemetry tracing configuration.

Integrates Agent Framework's built-in observability with the AI Toolkit
Agent Inspector for trace viewing and debugging.
"""

import logging

from app.config import TracingConfig

logger = logging.getLogger("workflow.tracing")


def configure_tracing(config: TracingConfig) -> None:
    """Set up OpenTelemetry tracing if enabled.

    Uses Agent Framework's ``configure_otel_providers()`` which automatically
    instruments chat clients, agents, and workflow operations — no manual
    span creation required.

    Args:
        config: Tracing configuration from AppConfig.
    """
    if not config.enabled:
        logger.debug("Tracing is disabled")
        return

    try:
        from agent_framework.observability import configure_otel_providers

        configure_otel_providers(
            vs_code_extension_port=config.get_port(),
            enable_sensitive_data=config.enable_sensitive_data,
        )
        logger.info(
            f"OpenTelemetry tracing enabled → {config.otlp_endpoint} "
            f"(sensitive_data={'on' if config.enable_sensitive_data else 'off'})"
        )
    except ImportError:
        logger.warning(
            "Tracing enabled in config but opentelemetry packages not installed. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-grpc"
        )
    except Exception as e:
        logger.error(f"Failed to configure tracing: {e}", exc_info=True)
