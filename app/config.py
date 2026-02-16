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


# ============================================================================
# Model / Provider configuration
# ============================================================================

class ModelEntry(BaseModel):
    """A single model available within a provider."""
    id: str = Field(description="Model identifier (e.g. 'llama3.1:8b', 'gpt-4o')")
    description: str = Field(default="", description="Human-readable description")


class OllamaProviderConfig(BaseModel):
    """Ollama provider settings."""
    host: str = Field(default="http://localhost:11434")
    models: list[ModelEntry] = Field(
        default_factory=lambda: [ModelEntry(id="llama3.1:8b", description="Good tool calling, ~6GB RAM")],
    )
    default_model: str = Field(default="llama3.1:8b")


class OpenAIProviderConfig(BaseModel):
    """OpenAI provider settings."""
    api_key: str | None = Field(
        default=None,
        description="OpenAI API key (or set OPENAI_API_KEY env var)",
    )
    models: list[ModelEntry] = Field(default_factory=list)
    default_model: str = Field(default="gpt-4o-mini")


class AzureOpenAIProviderConfig(BaseModel):
    """Azure OpenAI provider settings."""
    endpoint: str | None = Field(
        default=None,
        description="Azure OpenAI endpoint URL (or set AZURE_OPENAI_ENDPOINT env var)",
    )
    models: list[ModelEntry] = Field(default_factory=list)
    default_model: str | None = Field(default=None)


class ModelsConfig(BaseModel):
    """Multi-provider models configuration."""
    default_provider: str = Field(
        default="ollama",
        description="Active LLM provider: 'ollama', 'openai', or 'azure_openai'",
    )
    providers: dict[str, OllamaProviderConfig | OpenAIProviderConfig | AzureOpenAIProviderConfig] = Field(
        default_factory=lambda: {"ollama": OllamaProviderConfig()},
    )

    # ---- backward-compat helpers ----
    @property
    def provider(self) -> str:
        """Alias kept for backward compatibility."""
        return self.default_provider

    @property
    def ollama(self) -> OllamaProviderConfig:
        """Shorthand access for legacy code paths."""
        p = self.providers.get("ollama")
        if isinstance(p, OllamaProviderConfig):
            return p
        return OllamaProviderConfig()

    @property
    def azure_openai(self) -> AzureOpenAIProviderConfig:
        """Shorthand access for legacy code paths."""
        p = self.providers.get("azure_openai")
        if isinstance(p, AzureOpenAIProviderConfig):
            return p
        return AzureOpenAIProviderConfig()

    @property
    def openai(self) -> OpenAIProviderConfig:
        """Shorthand access for legacy code paths."""
        p = self.providers.get("openai")
        if isinstance(p, OpenAIProviderConfig):
            return p
        return OpenAIProviderConfig()

    def get_active_model_id(self) -> str:
        """Return the model id currently selected for the active provider."""
        prov = self.providers.get(self.default_provider)
        if prov is None:
            return "unknown"
        return prov.default_model or (prov.models[0].id if prov.models else "unknown")

    def get_active_provider_config(self):
        """Return the config object for the active provider."""
        return self.providers.get(self.default_provider)


# ============================================================================
# Agent configuration
# ============================================================================

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


# ============================================================================
# Scraper, Knowledge, Workflow, UI configuration
# ============================================================================

class ScraperConfig(BaseModel):
    """Web scraper configuration."""
    timeout: int = Field(default=30)
    user_agent: str = Field(default="MultiAgentWorkflow/0.1")
    max_content_length: int = Field(default=50000)


class DomainConfig(BaseModel):
    """Configuration for a single knowledge domain.

    Each domain has its own notes directory, context file, URL index,
    and (optionally) a custom notes template.
    """
    description: str = Field(default="", description="Human-readable description")
    notes_directory: str = Field(description="Directory for notes files")
    context_file: str = Field(description="Path to domain-specific context file")
    url_index_file: str = Field(description="Path to domain-specific URL index")
    template: str = Field(
        default="config/templates/note_template.md",
        description="Path to the domain's notes template (generated from default if missing)",
    )
    default_template: str = Field(
        default="config/templates/note_template.md",
        description="Path to the default/base notes template used to seed domain templates",
    )
    frontmatter_defaults: dict[str, str | int | bool] = Field(
        default_factory=dict,
        description="Default frontmatter values for notes in this domain",
    )


class KnowledgeConfig(BaseModel):
    """Knowledge configuration — domain-first layout."""
    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Confidence threshold below which human review is required",
    )
    relevance_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Relevance threshold below which human review is required",
    )
    domains: dict[str, DomainConfig] = Field(
        default_factory=lambda: {
            "general": DomainConfig(
                description="General notes and documentation",
                notes_directory="../knowledge/general/notes",
                context_file="../knowledge/general/context.md",
                url_index_file="../knowledge/general/url_index.yaml",
                template="../knowledge/general/note_template.md",
                frontmatter_defaults={"category": "general", "priority": "medium", "reviewed": False},
            ),
            "social": DomainConfig(
                description="Social and people-related knowledge",
                notes_directory="../knowledge/social/notes",
                context_file="../knowledge/social/context.md",
                url_index_file="../knowledge/social/url_index.yaml",
                template="../knowledge/social/note_template.md",
                frontmatter_defaults={"category": "social", "priority": "medium", "reviewed": False},
            ),
        },
    )

    # ---- backward-compat shims ----

    @property
    def context_file(self) -> str:
        """Return the first domain's context file (legacy single-file callers)."""
        for cfg in self.domains.values():
            return cfg.context_file
        return "../knowledge/general/context.md"

    @property
    def url_index_file(self) -> str:
        """Return the first domain's URL index (legacy single-file callers)."""
        for cfg in self.domains.values():
            return cfg.url_index_file
        return "../knowledge/general/url_index.yaml"

    @property
    def notes_topics(self) -> dict[str, "DomainConfig"]:
        """Alias for ``domains`` — keeps old code working until fully migrated."""
        return self.domains

    def domain_names(self) -> list[str]:
        """Ordered list of configured domain names."""
        return list(self.domains.keys())

    def get_domain(self, name: str | None) -> DomainConfig:
        """Look up a domain by name with fallback to 'general'."""
        if name and name in self.domains:
            return self.domains[name]
        return next(iter(self.domains.values()))


class TracingConfig(BaseModel):
    """OpenTelemetry tracing configuration."""
    enabled: bool = Field(default=False, description="Enable/disable OpenTelemetry tracing")
    otlp_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC endpoint (AI Toolkit default: localhost:4317)",
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
        description="Seconds of idle before showing 'still working' in streaming mode",
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    file: str | None = Field(default=None)


class WorkflowConfig(BaseModel):
    """Workflow routing configuration."""
    answer_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Minimum confidence to display an answer without suggesting web search",
    )
    max_sources_displayed: int = Field(
        default=10,
        description="Maximum number of source references to show the user",
    )


class UIConfig(BaseModel):
    """UI preferences."""
    theme: str = Field(
        default="dark",
        description="Color theme: 'dark' or 'light'",
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
    ui: UIConfig = Field(default_factory=UIConfig)


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
    
    # ── Normalise the models block ──────────────────────────────────────
    # The YAML schema uses ``providers:`` with typed sub-keys.  We need to
    # coerce each provider dict into the correct Pydantic type so that the
    # union field resolves properly.
    models_raw = config_data.get("models", {})
    providers_raw: dict[str, Any] = models_raw.get("providers", {})

    _PROVIDER_TYPES = {
        "ollama": OllamaProviderConfig,
        "openai": OpenAIProviderConfig,
        "azure_openai": AzureOpenAIProviderConfig,
    }
    for name, cls in _PROVIDER_TYPES.items():
        if name in providers_raw and isinstance(providers_raw[name], dict):
            providers_raw[name] = cls(**providers_raw[name])

    # ── Environment-variable overrides ──────────────────────────────────
    if os.getenv("LLM_PROVIDER"):
        models_raw["default_provider"] = os.getenv("LLM_PROVIDER")

    # Ollama env overrides
    if "ollama" not in providers_raw:
        providers_raw["ollama"] = OllamaProviderConfig()
    ollama_prov = providers_raw["ollama"]
    if isinstance(ollama_prov, dict):
        ollama_prov = OllamaProviderConfig(**ollama_prov)
        providers_raw["ollama"] = ollama_prov
    if os.getenv("OLLAMA_HOST"):
        ollama_prov.host = os.getenv("OLLAMA_HOST")
    if os.getenv("OLLAMA_MODEL_ID"):
        ollama_prov.default_model = os.getenv("OLLAMA_MODEL_ID")

    # Azure OpenAI env overrides
    if os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_OPENAI_DEPLOYMENT"):
        if "azure_openai" not in providers_raw:
            providers_raw["azure_openai"] = AzureOpenAIProviderConfig()
        az_prov = providers_raw["azure_openai"]
        if isinstance(az_prov, dict):
            az_prov = AzureOpenAIProviderConfig(**az_prov)
            providers_raw["azure_openai"] = az_prov
        if os.getenv("AZURE_OPENAI_ENDPOINT"):
            az_prov.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if os.getenv("AZURE_OPENAI_DEPLOYMENT"):
            az_prov.default_model = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    # OpenAI env overrides
    if os.getenv("OPENAI_API_KEY"):
        if "openai" not in providers_raw:
            providers_raw["openai"] = OpenAIProviderConfig()
        oa_prov = providers_raw["openai"]
        if isinstance(oa_prov, dict):
            oa_prov = OpenAIProviderConfig(**oa_prov)
            providers_raw["openai"] = oa_prov
        oa_prov.api_key = os.getenv("OPENAI_API_KEY")

    models_raw["providers"] = providers_raw
    config_data["models"] = models_raw

    # ── Build config ────────────────────────────────────────────────────
    config = AppConfig(**config_data)
    provider = config.models.default_provider
    model_id = config.models.get_active_model_id()
    logger.info(f"Configuration loaded: provider={provider}, model={model_id}")
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


def initialize_domain(domain_key: str, domain_config: DomainConfig) -> list[str]:
    """Create the directory structure and seed files for a knowledge domain.

    Creates:
      - notes directory (with empty ``_index.yaml``)
      - context file (scaffold markdown)
      - url_index file (empty ``urls: []``)

    Args:
        domain_key: The domain identifier (e.g. ``"general"``).
        domain_config: The ``DomainConfig`` for this domain.

    Returns:
        List of paths that were created.
    """
    project_root = _get_project_root()
    created: list[str] = []

    # Notes directory + _index.yaml
    notes_dir = project_root / domain_config.notes_directory
    notes_dir.mkdir(parents=True, exist_ok=True)
    index_path = notes_dir / "_index.yaml"
    if not index_path.exists():
        import yaml as _yaml

        _yaml.dump(
            {"domain": domain_key, "description": domain_config.description, "notes": []},
            index_path.open("w", encoding="utf-8"),
            default_flow_style=False,
            sort_keys=False,
        )
        created.append(str(index_path))

    # Context file
    ctx_path = project_root / domain_config.context_file
    ctx_path.parent.mkdir(parents=True, exist_ok=True)
    if not ctx_path.exists():
        from datetime import datetime as _dt

        ctx_path.write_text(
            f"# {domain_key.title()} Context\n\n"
            f"Last Updated: {_dt.now().strftime('%Y-%m-%d')}\n\n"
            "<!-- Add organizational context for this domain here -->\n",
            encoding="utf-8",
        )
        created.append(str(ctx_path))

    # URL index file
    url_path = project_root / domain_config.url_index_file
    url_path.parent.mkdir(parents=True, exist_ok=True)
    if not url_path.exists():
        import yaml as _yaml

        _yaml.dump(
            {"urls": []},
            url_path.open("w", encoding="utf-8"),
            default_flow_style=False,
            sort_keys=False,
        )
        created.append(str(url_path))

    # Domain-specific notes template
    tmpl_path = project_root / domain_config.template
    if not tmpl_path.exists():
        default_tmpl_path = project_root / domain_config.default_template
        if default_tmpl_path.exists():
            import re as _re

            content = default_tmpl_path.read_text(encoding="utf-8")
            # Update domain field in frontmatter
            content = _re.sub(
                r'^(domain:\s*)".*?"',
                f'\\1"{domain_key}"',
                content,
                flags=_re.MULTILINE,
            )
            # Apply frontmatter_defaults overrides
            defaults = domain_config.frontmatter_defaults
            if "category" in defaults:
                content = _re.sub(
                    r'^(category:\s*)".*?"',
                    f'\\1"{defaults["category"]}"',
                    content,
                    flags=_re.MULTILINE,
                )
            if "priority" in defaults:
                content = _re.sub(
                    r'^(priority:\s*)".*?"',
                    f'\\1"{defaults["priority"]}"',
                    content,
                    flags=_re.MULTILINE,
                )
            if "reviewed" in defaults:
                content = _re.sub(
                    r'^(reviewed:\s*)\S+',
                    f'\\1{str(defaults["reviewed"]).lower()}',
                    content,
                    flags=_re.MULTILINE,
                )
            tmpl_path.parent.mkdir(parents=True, exist_ok=True)
            tmpl_path.write_text(content, encoding="utf-8")
        else:
            logger.warning(
                f"Default template not found at {default_tmpl_path}; "
                f"skipping template generation for domain '{domain_key}'"
            )
            tmpl_path = None
        if tmpl_path is not None:
            created.append(str(tmpl_path))

    return created


class DomainStatus:
    """Holds the validation result for one domain."""

    def __init__(self, key: str, missing: list[str]):
        self.key = key
        self.missing = missing

    @property
    def ok(self) -> bool:
        return len(self.missing) == 0


def validate_knowledge_domains(
    config: AppConfig | None = None,
    *,
    auto_initialize: bool = False,
) -> list[DomainStatus]:
    """Check every configured domain for its expected directory / seed files.

    Args:
        config: Application config (uses ``get_config()`` when *None*).
        auto_initialize: When *True*, automatically create any missing
            domain stores instead of just reporting them.

    Returns:
        A list of ``DomainStatus`` objects — one per domain.  Each
        contains a ``missing`` list of human-readable labels
        (e.g. ``"notes directory"``).  The list is empty when
        everything is present.
    """
    if config is None:
        config = get_config()

    project_root = _get_project_root()
    results: list[DomainStatus] = []

    for domain_key, domain_config in config.knowledge.domains.items():
        missing: list[str] = []

        notes_dir = project_root / domain_config.notes_directory
        if not notes_dir.exists():
            missing.append("notes directory")
        elif not (notes_dir / "_index.yaml").exists():
            missing.append("notes _index.yaml")

        ctx_path = project_root / domain_config.context_file
        if not ctx_path.exists():
            missing.append("context file")

        url_path = project_root / domain_config.url_index_file
        if not url_path.exists():
            missing.append("url index file")

        tmpl_path = project_root / domain_config.template
        if not tmpl_path.exists():
            missing.append("notes template")

        if missing and auto_initialize:
            created = initialize_domain(domain_key, domain_config)
            logger.info(
                f"Initialized domain '{domain_key}': created {len(created)} files"
            )
            missing.clear()

        results.append(DomainStatus(domain_key, missing))

    return results


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
