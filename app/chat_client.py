"""Chat Client Factory.

Creates the appropriate ChatClient based on configuration.
Supports Ollama (default, local) and Azure OpenAI (cloud, optional).
"""

import logging
import os

from app.config import get_config

logger = logging.getLogger("workflow.chat_client")


def create_chat_client(purpose: str = "agent"):
    """Create a chat client based on the configured provider.

    The provider is determined by the ``provider`` field in the models
    config (config.yaml ``models.provider``).  Defaults to ``"ollama"``.

    - **ollama**: Uses ``OllamaChatClient`` with local inference.
    - **azure_openai**: Uses ``AzureOpenAIChatClient`` with Azure credentials.

    Args:
        purpose: Description of what this client is for (for logging).

    Returns:
        A ChatClient instance (OllamaChatClient or AzureOpenAIChatClient).

    Raises:
        ImportError: If the required provider package is not installed.
        ValueError: If the configured provider is unknown.
    """
    config = get_config()
    provider = config.models.provider

    if provider == "ollama":
        from agent_framework.ollama import OllamaChatClient

        client = OllamaChatClient(
            host=config.models.ollama.host,
            model_id=config.models.ollama.model_id,
        )
        logger.debug(
            f"Created OllamaChatClient for {purpose}: "
            f"model={config.models.ollama.model_id}"
        )
        return client

    elif provider == "azure_openai":
        try:
            from agent_framework.azure import AzureOpenAIChatClient
            from azure.identity import DefaultAzureCredential
        except ImportError as e:
            raise ImportError(
                "Azure OpenAI provider requires 'agent-framework-azure-ai' and "
                "'azure-identity' packages. Install with:\n"
                "  pip install agent-framework-azure-ai azure-identity"
            ) from e

        endpoint = config.models.azure_openai.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = config.models.azure_openai.deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

        if not endpoint or not deployment:
            raise ValueError(
                "Azure OpenAI requires 'endpoint' and 'deployment_name' in config, "
                "or AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT environment variables."
            )

        client = AzureOpenAIChatClient(
            azure_endpoint=endpoint,
            deployment_name=deployment,
            credential=DefaultAzureCredential(),
        )
        logger.debug(
            f"Created AzureOpenAIChatClient for {purpose}: "
            f"deployment={deployment}"
        )
        return client

    else:
        raise ValueError(
            f"Unknown model provider: '{provider}'. "
            f"Supported providers: 'ollama', 'azure_openai'"
        )
