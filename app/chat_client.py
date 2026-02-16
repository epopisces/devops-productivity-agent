"""Chat Client Factory.

Creates the appropriate ChatClient based on configuration.
Supports Ollama (default, local) and Azure OpenAI (cloud, optional).
"""

import logging
import os

from app.config import get_config, OllamaProviderConfig, AzureOpenAIProviderConfig

logger = logging.getLogger("workflow.chat_client")


def create_chat_client(purpose: str = "agent"):
    """Create a chat client based on the configured provider.

    The provider is determined by ``models.default_provider`` in config.yaml.
    Each provider has its own settings under ``models.providers.<name>``.

    Supported providers:
    - **ollama**: Uses ``OllamaChatClient`` with local inference.
    - **openai**: Uses ``OpenAIChatClient`` with OpenAI API.
    - **azure_openai**: Uses ``AzureOpenAIChatClient`` with Azure credentials.

    Args:
        purpose: Description of what this client is for (for logging).

    Returns:
        A ChatClient instance.

    Raises:
        ImportError: If the required provider package is not installed.
        ValueError: If the configured provider is unknown or misconfigured.
    """
    config = get_config()
    provider = config.models.default_provider
    prov_config = config.models.get_active_provider_config()

    if provider == "ollama":
        from agent_framework.ollama import OllamaChatClient

        if not isinstance(prov_config, OllamaProviderConfig):
            prov_config = config.models.ollama

        model_id = prov_config.default_model
        client = OllamaChatClient(
            host=prov_config.host,
            model_id=model_id,
        )
        logger.debug(f"Created OllamaChatClient for {purpose}: model={model_id}")
        return client

    elif provider == "openai":
        try:
            from openai import OpenAI
            from agent_framework.openai import OpenAIChatClient
        except ImportError as e:
            raise ImportError(
                "OpenAI provider requires 'agent-framework-openai' and 'openai' packages. "
                "Install with:\n  pip install agent-framework-openai openai"
            ) from e

        if not isinstance(prov_config, OpenAIProviderConfig):
            prov_config = config.models.openai

        api_key = prov_config.api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "OpenAI provider requires an API key. Set 'api_key' in config "
                "or set the OPENAI_API_KEY environment variable."
            )

        model_id = prov_config.default_model
        openai_client = OpenAI(api_key=api_key)
        client = OpenAIChatClient(
            openai_client=openai_client,
            model=model_id,
        )
        logger.debug(f"Created OpenAIChatClient for {purpose}: model={model_id}")
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

        if not isinstance(prov_config, AzureOpenAIProviderConfig):
            prov_config = config.models.azure_openai

        endpoint = prov_config.endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = prov_config.default_model or os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

        if not endpoint or not deployment:
            raise ValueError(
                "Azure OpenAI requires 'endpoint' and a model/deployment in config, "
                "or AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT environment variables."
            )

        client = AzureOpenAIChatClient(
            azure_endpoint=endpoint,
            deployment_name=deployment,
            credential=DefaultAzureCredential(),
        )
        logger.debug(f"Created AzureOpenAIChatClient for {purpose}: deployment={deployment}")
        return client

    else:
        raise ValueError(
            f"Unknown model provider: '{provider}'. "
            f"Supported providers: 'ollama', 'openai', 'azure_openai'"
        )
