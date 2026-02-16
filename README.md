# Multi-Agent Workflow Assistant - MVP
---

This is a knowledge worker, a multi-agent workflow application using the Microsoft Agent Framework that retrieves, synthesizes, and stores information. Out of the box this is a locally-hosted Python application that uses the **Microsoft Agent Framework** with a **WorkflowBuilder graph** to provide intelligent query triaging, knowledge retrieval, and structured responses.

It is currently in a Minimum Viable Product (MVP) state, and additional features will be added presently.

## Features (MVP)

- **WorkflowBuilder Graph**: Structured workflow with conditional routing based on user intent
- **Intelligent Triage**: Automatically classifies queries as questions, knowledge ingestion, or both
- **Knowledge Retrieval**: Tag-based search across organizational context, notes, and indexed URLs
- **Question Answering**: Synthesizes answers from retrieved context with confidence scoring
- **Ingestion Previews**: Generates previews of proposed knowledge base writes (URLs, notes, context updates)
- **URL Scraping**: Fetches and parses web content with JS-only page detection
- **Dual Interface**: CLI and Streamlit web UI
- **Provider-Agnostic LLM**: Supports Ollama (default, local) and Azure OpenAI

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) installed and running
- 8GB RAM minimum (for running local models)

## Quick Start

### 1. Install Ollama

Download and install Ollama from [ollama.com](https://ollama.com/).

### 2. Pull a Model

For systems with 8GB RAM and integrated graphics, we recommend `qwen3:4b` or `llama3.2:3b`:

```bash
ollama pull llama3.2:3b
```

Other lightweight options:
- `phi3:mini` - Fast, good for simple tasks
- `qwen3:4b` - Good tool calling support

### 3. Install Dependencies

```bash
# Create virtual environment
uv venv --python=3.13.11

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install package with dependencies (--pre required for agent-framework preview)
uv pip install -e ".[dev]" --pre
```

### 4. Configure

Copy the example environment file:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Edit `.env` to match your Ollama setup:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL_ID=llama3.2:3b
```

### 5. Run

```bash
# Make sure Ollama is running
ollama serve

# In another terminal, start the CLI
python -m app.cli
```

Or use the entry point:

```bash
workflow
```

### Web Interface (Streamlit)

For a browser-based experience:

```bash
# Using the entry point
workflow-web

# Or directly with streamlit
streamlit run app/web.py
```

The web interface includes:
- **Chat tab**: Conversational interface with message history
- **Knowledge Base tab**: Browse instructions, indexed URLs, and notes
- **Metrics tab**: View session statistics and metrics files
- **Sidebar**: Connection status, log level control, and quick metrics

## Usage

### Workflow Behavior

The application processes your input through a multi-stage workflow:

1. **Triage**: Classifies your intent (question, ingestion, or both) and extracts metadata (domain, tags)
2. **Knowledge Lookup**: Searches existing knowledge base using extracted tags
3. **Conditional Routing**:
   - **Question** → Synthesizes answer from retrieved context
   - **Ingestion** → Generates preview of proposed knowledge write (URL index, note, context update)
   - **Both** → Does both operations
4. **Response Formatting**: Structures output with sources, confidence scores, and badges

### CLI Commands

Once running, you can:

1. **Ask questions**: Type any question and press Enter
2. **Analyze URLs**: Paste a URL to fetch and analyze its content
3. **Store knowledge**: Share information to save to the knowledge base
4. **Commands**:
   - `/new` - Start a new conversation
   - `/config` - Show current configuration
   - `/loglevel [level]` - Set logging level (DEBUG, INFO, WARNING, ERROR)
   - `/help` - Show help message
   - `/quit` - Exit the application

### Examples

**Question**:
```
You: Do we have any notes on Kubernetes deployment?
```

**URL Analysis**:
```
You: Analyze https://kubernetes.io/docs/concepts/overview/
```

**Knowledge Ingestion**:
```
You: Save this: Our team uses Python 3.11+ and deploys via GitHub Actions to Azure
```

**Both (URL + Store)**:
```
You: I'd like to save the AI Dev Project Setup Prompts URL in my index: https://notion.so/setup-prompts
```

## Customization

### Instruction Files

Each LLM-backed executor uses an instruction file that defines its behavior. These are **user-editable** and located in `config/instructions/`:

| File | Executor | Purpose | Customizable Elements |
|------|----------|---------|----------------------|
| `triage.md` | TriageExecutor | Classifies user intent & extracts metadata | Intent rules, domain list, tag extraction logic |
| `question_handler.md` | QuestionHandlerExecutor | Synthesizes answers from context | Answer format, citation style, confidence thresholds |
| `ingestion_preview.md` | IngestionPreviewExecutor | Previews knowledge writes | Quality thresholds, action rules, review criteria |

### Configuration (`config/config.yaml`)

Key settings you can customize:

```yaml
models:
  provider: "ollama"  # or "azure_openai"
  ollama:
    host: "http://localhost:11434"
    model_id: "llama3.2:3b"  # Change to your preferred model
  azure_openai:  # Optional: configure for Azure OpenAI
    endpoint: "https://your-endpoint.openai.azure.com"
    deployment_name: "gpt-4"

knowledge:
  context_file: "knowledge/context.md"  # Org-level context
  url_index_file: "knowledge/sources/url_index.yaml"  # Indexed URLs
  notes_topics:
    general:
      directory: "knowledge/notes"  # Notes directory
      description: "General knowledge and documentation"

scraper:
  timeout: 30  # URL fetch timeout (seconds)
  max_content_length: 10000  # Truncate long pages

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: null  # Optional: log to file

metrics:
  enabled: true
  directory: "metrics"
```

### Tool Functions (`app/tools/`)

Standalone sync functions used by executors:

- **`url_scraper.py`**: `fetch_url()` - Fetches and parses web content
- **`knowledge_retrieval.py`**: `get_available_tags()`, `search_by_tags()` - Tag-based search
- **`knowledge_ingestion.py`**: `add_url_to_index()`, `create_note()`, `update_instructions_file()` - Write operations
- **`org_context.py`**: `get_instructions_context()`, `read_note()`, `search_knowledge()` - Read operations

You can add new tools by:
1. Creating a new `.py` file in `app/tools/`
2. Defining sync functions with `Annotated` type hints
3. Decorating with `@track_tool_call("tool_name")`
4. Registering them on the appropriate executor in `app/agents/` or `app/executors/`

### Knowledge Store (`knowledge/`)

All knowledge is stored in structured formats:

- **`context.md`**: High-level organizational context (plain markdown)
- **`sources/url_index.yaml`**: Indexed URLs with metadata (YAML list with title, summary, tags, domain)
- **`notes/_index.yaml`**: Notes index (YAML list with filename, title, summary, tags, domain)
- **`notes/*.md`**: Detailed notes with YAML frontmatter

You can manually edit these files or let the ingestion workflow manage them.

### Switching LLM Providers

**Ollama (default)**:
```yaml
models:
  provider: "ollama"
  ollama:
    host: "http://localhost:11434"
    model_id: "llama3.2:3b"
```

**Azure OpenAI**:
```yaml
models:
  provider: "azure_openai"
  azure_openai:
    endpoint: "https://your-endpoint.openai.azure.com"
    deployment_name: "gpt-4"
    api_version: "2024-02-01"
```

Set the `AZURE_OPENAI_API_KEY` environment variable in `.env`:
```env
AZURE_OPENAI_API_KEY=your-key-here
```

---

# Roadmap

---

## Planned Improvements

### Knowledge Base Enhancements
- [ ] **Improve "show full note" reliability**: When org_context finds a relevant note, ensure it automatically reads and returns the full content without requiring additional user prompts. Currently, the LLM may offer to show a note but fail to call the `read_note` tool on follow-up requests.
- [ ] **Note search improvements**: Better keyword matching and relevance scoring for note searches

### User Experience
- [ ] **Reduce conversational friction**: The assistant should act proactively on clear intent rather than asking for confirmation (e.g., "Do I have notes on X?" should immediately search, not ask if user wants to search)
- [ ] **Consistent follow-up actions**: Only offer actions that tools can actually perform

---


# Changelog
---

### 2026-02-16 (Claude Opus 4.6)
- **Refactored**: TracingConfig field naming for clarity — renamed `otlp_endpoint` (str) to `vs_code_extension_port` (int) to accurately reflect that Agent Framework's `configure_otel_providers()` only accepts a port number and always uses localhost, not a full OTLP endpoint URL. Updated `app/config.py`, `app/tracing.py`, `config/config.yaml`, and tests accordingly. Removed complex URL validation logic in favor of simple Pydantic integer constraints (ge=1, le=65535).

### 2026-02-15 (Claude Opus 4.6 w/AIAgentExpert)
- **Added**: OpenTelemetry tracing support via Agent Framework's built-in `configure_otel_providers()`
  - New `app/tracing.py` module with `configure_tracing()` — auto-instruments chat clients, agents, and workflows (no manual spans needed)
  - New `TracingConfig` Pydantic model in `app/config.py` with `enabled`, `otlp_endpoint`, and `enable_sensitive_data` fields
  - Tracing config section added to `config/config.yaml` (disabled by default)
  - Both CLI and Streamlit entrypoints call `configure_tracing()` on startup
  - Added `opentelemetry-exporter-otlp-proto-grpc` dependency to `pyproject.toml`
  - Integrates with AI Toolkit Agent Inspector trace viewer on `localhost:4317`
- **Updated**: `docs/architecture.md` — replaced outdated coordinator-agent diagram with current WorkflowBuilder graph showing Triage → KnowledgeLookup → [conditional routing] → QuestionHandler/IngestionPreview → ResponseFormatter flow, executor types, tool usage patterns, and data flow with Pydantic models
- **Updated**: README — updated Features, Usage, and added comprehensive Customization section covering:
  - Instruction files (triage, question_handler, ingestion_preview) with purpose and customizable elements
  - Configuration options in `config.yaml` (LLM provider, knowledge paths, scraper settings, logging, metrics)
  - Tool functions in `app/tools/` and how to add new ones
  - Knowledge store structure (`context.md`, URL index, notes with frontmatter)
  - LLM provider switching (Ollama vs Azure OpenAI)
  - Workflow behavior explanation (Triage → Lookup → Conditional Routing → Formatting)
  - Usage examples for questions, URL analysis, knowledge ingestion, and both flows

### 2026-02-14 (Claude Opus 4.6 w/AIAgentExpert)
- **Fixed**: Streamlit debug launch config — changed `cwd` from `${workspaceFolder}/app` to `${workspaceFolder}` and script path from `web.py` to `app/web.py`; resolves `ModuleNotFoundError: No module named 'app.models'` when debugging
- **Fixed**: Updated `WorkflowBuilder` usage in `app/workflows/main_workflow.py` to match current `agent-framework` API — replaced removed constructor kwargs (`start_executor`, `output_executors`) with `register_executor()` factories + `set_start_executor()` + string-based `add_edge()` references
- **Changed**: Ingestion preview section in `web.py` — two-part shields.io-style badges (gray key | colored value) for action, domain, tags, and confidence; colors vary by action type and confidence level
- **Fixed**: URL scraper now detects JS-only / SPA pages (e.g. Notion) that return no usable content and returns a descriptive error instead of garbage text
- **Added**: `tests/test_web.py` — 12 tests covering web module imports, `format_workflow_output` (empty, question, low-confidence, web search, ingestion badges, source deduplication), and `web_runner` entry point
- **Added**: `test_fetch_url_js_only_page` test in `test_url_scraper.py`

### 2026-02-13 (Claude Opus 4.6 w/AIAgentExpert)
- **Architecture**: Migrated from coordinator-agent-as-tool pattern to WorkflowBuilder graph
  - New flow: Triage → KnowledgeLookup → QuestionHandler / IngestionPreview → ResponseFormatter
  - Conditional edge routing based on classified intent (question, ingestion, or both)
  - Triage, QuestionHandler, IngestionPreview are custom `Executor` subclasses wrapping `ChatAgent`
  - KnowledgeLookup and ResponseFormatter are deterministic (no LLM) executors
- **Added**: `app/models.py` — shared Pydantic models (`TriageResult`, `LookupResult`, `QuestionResult`, `IngestionPreviewResult`, `WorkflowOutput`)
- **Added**: `app/tools/` — flat directory of standalone sync tool functions (extracted from old agent wrappers)
  - `url_scraper.py`, `knowledge_retrieval.py`, `knowledge_ingestion.py`, `org_context.py`
- **Added**: `app/executors/` — `KnowledgeLookupExecutor`, `ResponseFormatterExecutor`
- **Added**: `app/agents/triage.py`, `question_handler.py`, `ingestion_preview.py` — LLM-backed Executors
- **Added**: `app/workflows/main_workflow.py` — `build_workflow()` factory wiring the full graph
- **Added**: `app/chat_client.py` — provider-agnostic factory supporting Ollama (default) and Azure OpenAI
- **Added**: Instruction files for new agents (`config/instructions/triage.md`, `question_handler.md`, `ingestion_preview.md`)
- **Changed**: `config.yaml` / `config.py` — replaced coordinator/url_scraper/knowledge_ingestion/org_context agent configs with triage/question_handler/ingestion_preview; added `models.provider`, `models.azure_openai`, and `workflow` config sections
- **Changed**: `web.py` — uses `build_workflow()` + `format_workflow_output()` instead of `CoordinatorAgent`; renders structured WorkflowOutput with source cards and ingestion previews
- **Changed**: `cli.py` — uses `build_workflow()` instead of `CoordinatorAgent`; formats structured output for terminal
- **Removed**: `app/agents/coordinator.py`, `app/agents/tools/` directory (replaced by `app/tools/`)
- **Updated**: Tests — removed coordinator/url_scraper_agent tests; added `test_workflow.py` for routing conditions; updated import paths and mock configs
- **Optimized**: Condensed all agent instruction prompts for faster inference with smaller models

### 2026-02-12 (Claude Opus 4.6)
- **Changed**: Reorganized knowledge folder structure for unified knowledge management
  - Moved `notes/` under `knowledge/notes/` — all knowledge under one tree
  - Renamed `knowledge/instructions.md` → `knowledge/context.md` (avoids confusion with agent instructions)
  - Moved `knowledge/url_index.yaml` → `knowledge/sources/url_index.yaml` (separates provenance from content)
  - Updated all config paths (`context_file`, `url_index_file`, `notes_topics.default.directory`)
- **Added**: `knowledge_retrieval.py` — traditional function-based tool (not agent-as-tool)
  - `get_available_tags()`: Collects all unique tags from notes index and URL index with counts
  - `search_by_tags(tags)`: Returns matching notes/URLs with summaries for given tags
- **Fixed**: Coordinator now strips leaked tool-call syntax (e.g., `<|python_tag|>{...}`) from model output
- **Removed**: Copyright headers from all Python files (project is open source)
- **Added**: Mermaid architecture diagram in `docs/architecture.md`
- **Changed**: Made repo a proper GitHub template by separating sample/example files from runtime-generated data
  - Created `.sample` copies of knowledge files; added runtime-generated files to `.gitignore`

### 2026-02-03 (Claude Opus 4.5)
- **Fixed**: "Event loop is closed" error when sending multiple messages in Streamlit web UI
  - Implemented persistent event loop stored in session state instead of creating/closing per message
- **Added**: "Response complete" INFO-level log when coordinator finishes streaming response
  - Shows total character count and chunk count for visibility
- **Optimized**: URL scraper performance improvements for better responsiveness
  - Connection pooling with HTTP/2 support (reuses connections across requests)
  - Reduced default timeout from 30s to 10s (sufficient for most sites)
  - Switched from `html.parser` to `lxml` for 5-10x faster HTML parsing
- **Added**: Dependencies `lxml>=5.0.0` and `httpx[http2]` to pyproject.toml

### 2026-01-22 (Claude Opus 4.5)
- **Added**: Streamlit web interface (`app/web.py`) as alternative to CLI
  - Chat interface with message history
  - Sidebar with connection status, session controls, log level selector, and metrics
  - Knowledge Base Explorer tab to view instructions, indexed URLs, and notes
  - Metrics Dashboard tab showing session stats and metrics files
  - Run with `workflow-web` or `streamlit run app/web.py`
- **Added**: "Reload Config" button in web UI sidebar to apply config.yaml changes at runtime
  - Reloads config singleton, reinitializes coordinator with new model settings
  - Displays toast notification with new model name
- **Added**: `reload_config()` function in `app/config.py` to refresh cached configuration
- **Added**: Agent instructions now loaded from external markdown files in `config/instructions/`
  - Users can customize agent behavior by editing `coordinator.md`, `org_context.md`, `url_scraper.md`, `knowledge_ingestion.md`
  - Supports template variables (e.g., `{confidence_threshold}`) that are filled at runtime
  - Falls back to embedded defaults if instruction files are missing
- **Added**: `load_instructions()` helper function in `app/config.py` for loading instruction files
- **Added**: `instructions_file` field to `AgentConfig` model
- **Added**: Metrics tracking for tool function calls via `@track_tool_call` decorator
  - All tool functions in `org_context`, `url_scraper`, and `knowledge_ingestion` now record metrics
  - Includes operation duration, input/output lengths, success/failure status
  - Metrics appear alongside coordinator metrics in daily `.jsonl` files
- **Fixed**: Updated agent-framework API from `create_agent()` to `as_agent()` to match latest version

### 2026-01-12 (Claude Opus 4.5)
- **Fixed**: Coordinator now immediately searches knowledge base when user asks about notes/documentation instead of asking for permission
- **Fixed**: Updated org_context agent instructions to automatically read full notes when found, rather than just summarizing
- **Added**: "Don't offer what you can't do" guidance in coordinator instructions
- **Added**: Roadmap section with planned improvements for note retrieval reliability

### 2026-01-27 (Claude Opus 4.5)
- **Added**: Streamlit frontend
- **Added**: Knowledge ingestion decision guidelines for when to use each tool function
- **Added**: Enhance CoordinatorAgent logging
- **Fixed**: Implement persistent event loop to maintain conversation state across multiple user inputs
