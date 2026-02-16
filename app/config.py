"""Configuration management for Multi-Agent Workflow."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Logger for this module
logger = logging.getLogger("workflow.config")


class OllamaConfig(BaseModel):
    """Ollama model configuration."""
    host: str = Field(default="http://localhost:11434")
    model_id: str = Field(default="qwen3:1.7b")


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI model configuration."""
    endpoint: str | None = Field(
        default=None,
        description="Azure OpenAI endpoint URL (or set AZURE_OPENAI_ENDPOINT env var)",
    )
    deployment_name: str | None = Field(
        default=None,
        description="Model deployment name (or set AZURE_OPENAI_DEPLOYMENT env var)",
    )


class ModelsConfig(BaseModel):
    """Models configuration."""
    provider: str = Field(
        default="ollama",
        description="LLM provider: 'ollama' (local) or 'azure_openai' (cloud)",
    )
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    azure_openai: AzureOpenAIConfig = Field(default_factory=AzureOpenAIConfig)


class AgentConfig(BaseModel):
    """Individual agent configuration."""
    name: str
    description: str
    instructions_file: str | None = Field(
        default=None,
        description="Path to markdown file containing agent instructions"
    )


class AgentsConfig(BaseModel):
    """Agents configuration."""
    triage: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="Triage",
            description="Classifies user intent and extracts domain/tags",
            instructions_file="config/instructions/triage.md",
        )
    )
    question_handler: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="QuestionHandler",
            description="Answers questions using knowledge context and retrieval tools",
            instructions_file="config/instructions/question_handler.md",
        )
    )
    ingestion_preview: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            name="IngestionPreview",
            description="Proposes knowledge-base writes for user approval",
            instructions_file="config/instructions/ingestion_preview.md",
        )
    )


class ScraperConfig(BaseModel):
    """Web scraper configuration."""
    timeout: int = Field(default=30)
    user_agent: str = Field(default="MultiAgentWorkflow/0.1")
    max_content_length: int = Field(default=50000)


class NoteTopicConfig(BaseModel):
    """Configuration for a single notes topic."""
    directory: str = Field(description="Directory path for notes in this topic")
    template: str = Field(description="Path to the template file for this topic")
    description: str = Field(default="", description="Description of this topic")
    frontmatter_defaults: dict[str, str | int | bool] = Field(
        default_factory=dict,
        description="Default frontmatter values for notes in this topic"
    )


class KnowledgeConfig(BaseModel):
    """Knowledge ingestion configuration."""
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence threshold below which human review is required"
    )
    relevance_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Relevance threshold below which human review is required"
    )
    context_file: str = Field(
        default="knowledge/context.md",
        description="Path to the org context file"
    )
    url_index_file: str = Field(
        default="knowledge/sources/url_index.yaml",
        description="Path to the URL index file"
    )
    notes_topics: dict[str, NoteTopicConfig] = Field(
        default_factory=lambda: {
            "default": NoteTopicConfig(
                directory="knowledge/notes",
                template="config/templates/note_template.md",
                description="General notes and documentation",
                frontmatter_defaults={
                    "category": "general",
                    "priority": "medium",
                    "reviewed": False
                }
            )
        },
        description="Notes configuration by topic"
    )


class TracingConfig(BaseModel):
    """OpenTelemetry tracing configuration."""
    enabled: bool = Field(default=False, description="Enable/disable OpenTelemetry tracing")
    vs_code_extension_port: int = Field(
        default=4317,
        ge=1,
        le=65535,
        description="Port number for AI Toolkit Agent Inspector (default: 4317, localhost only)",
    )
    enable_sensitive_data: bool = Field(
        default=False,
        description="Capture prompts and completions in traces",
    )


class MetricsConfig(BaseModel):
    """Metrics collection configuration."""
    enabled: bool = Field(default=True, description="Enable/disable metrics collection")
    directory: str = Field(default="metrics", description="Directory to store metrics files")


class ProgressConfig(BaseModel):
    """Progress indicator configuration."""
    enabled: bool = Field(default=True, description="Enable progress indicators")
    style: str = Field(default="dots", description="Style: spinner, dots, elapsed, message")
    update_interval: float = Field(default=2.0, description="Seconds between updates")
    show_elapsed: bool = Field(default=True, description="Show elapsed time")
    streaming_idle_threshold: float = Field(
        default=5.0,
        description="Seconds of idle before showing 'still working' in streaming mode"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    file: str | None = Field(default=None)


class WorkflowConfig(BaseModel):
    """Workflow routing configuration."""
    answer_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to display an answer without suggesting web search",
    )
    max_sources_displayed: int = Field(
        default=10,
        description="Maximum number of source references to show the user",
    )


class AppConfig(BaseModel):
    """Application configuration."""
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    progress: ProgressConfig = Field(default_factory=ProgressConfig)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file and environment variables.
    
    Args:
        config_path: Path to config.yaml. Defaults to config/config.yaml.
        
    Returns:
        AppConfig instance with merged configuration.
    """
    # Load environment variables from .env file
    load_dotenv()
    logger.debug("Loaded environment variables from .env file")
    
    # Determine config path
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    else:
        config_path = Path(config_path)
    
    logger.debug(f"Loading configuration from: {config_path}")
    
    # Load YAML config if exists
    config_data: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        logger.debug(f"Loaded YAML config with keys: {list(config_data.keys())}")
    else:
        logger.warning(f"Config file not found: {config_path}, using defaults")
    
    # Override with environment variables
    if "models" not in config_data:
        config_data["models"] = {}
    if "ollama" not in config_data["models"]:
        config_data["models"]["ollama"] = {}
    
    # Environment variables take precedence
    if os.getenv("OLLAMA_HOST"):
        config_data["models"]["ollama"]["host"] = os.getenv("OLLAMA_HOST")
        logger.debug(f"Using OLLAMA_HOST from environment: {os.getenv('OLLAMA_HOST')}")
    if os.getenv("OLLAMA_MODEL_ID"):
        config_data["models"]["ollama"]["model_id"] = os.getenv("OLLAMA_MODEL_ID")
        logger.debug(f"Using OLLAMA_MODEL_ID from environment: {os.getenv('OLLAMA_MODEL_ID')}")

    # Provider selection
    if os.getenv("LLM_PROVIDER"):
        config_data["models"]["provider"] = os.getenv("LLM_PROVIDER")
        logger.debug(f"Using LLM_PROVIDER from environment: {os.getenv('LLM_PROVIDER')}")

    # Azure OpenAI overrides
    if "azure_openai" not in config_data["models"]:
        config_data["models"]["azure_openai"] = {}
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        config_data["models"]["azure_openai"]["endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT")
    if os.getenv("AZURE_OPENAI_DEPLOYMENT"):
        config_data["models"]["azure_openai"]["deployment_name"] = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    config = AppConfig(**config_data)
    provider = config.models.provider
    if provider == "ollama":
        logger.info(f"Configuration loaded: provider=ollama, model={config.models.ollama.model_id}, host={config.models.ollama.host}")
    else:
        logger.info(f"Configuration loaded: provider={provider}, deployment={config.models.azure_openai.deployment_name}")
    return config


# Global config instance (lazy loaded)
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the global configuration instance.
    
    Returns:
        AppConfig instance.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from disk.
    
    This clears the cached config and reloads from config.yaml.
    Useful when config has been modified externally.
    
    Returns:
        Newly loaded AppConfig instance.
    """
    global _config
    logger.info("Reloading configuration from disk")
    _config = load_config()
    return _config


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def load_instructions(instructions_file: str | None, **format_kwargs) -> str | None:
    """Load agent instructions from a markdown file.
    
    Args:
        instructions_file: Path to the instructions file (relative to project root).
        **format_kwargs: Keyword arguments to format into the instructions template.
        
    Returns:
        The instructions string, or None if the file doesn't exist.
    """
    if instructions_file is None:
        return None
    
    project_root = _get_project_root()
    instructions_path = project_root / instructions_file
    
    if not instructions_path.exists():
        logger.warning(f"Instructions file not found: {instructions_path}")
        return None
    
    try:
        with open(instructions_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Apply format kwargs if any provided
        if format_kwargs:
            content = content.format(**format_kwargs)
        
        logger.debug(f"Loaded instructions from {instructions_file} ({len(content)} chars)")
        return content
    except Exception as e:
        logger.error(f"Failed to load instructions from {instructions_file}: {e}")
        return None
