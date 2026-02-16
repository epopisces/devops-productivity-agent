# Software Requirements Specification: Multi-Agent Workflow Assistant

## System Design

- **Application Type**: Single-user local-first web application
- **Runtime**: Python 3.11+ with Streamlit frontend
- **Deployment**: Local workstation (primary), optional remote hosting (future)
- **Core Pattern**: WorkflowBuilder graph orchestrating specialized executors via Microsoft Agent Framework

### High-Level Components
- **Streamlit UI Layer**: Chat interface, knowledge explorer, metrics dashboard, ingestion approval
- **WorkflowBuilder Graph**: Directed acyclic graph of executors for structured processing
- **Executor Registry**: LLM-backed and deterministic executors registered as factories
- **Knowledge Layer**: Per-domain YAML-indexed markdown stores for organizational context
- **Model Abstraction**: Provider-agnostic ChatClient factory supporting Ollama (local), OpenAI (cloud), and Azure OpenAI (enterprise)
- **Tracing**: OpenTelemetry instrumentation with OTLP gRPC export

---

## Architecture Pattern

- **Pattern**: WorkflowBuilder Graph (Microsoft Agent Framework)
- **Style**: Executor pipeline with conditional routing and structured Pydantic data models

### Component Structure
```
app/
├── cli.py                 # CLI chat interface
├── web.py                 # Streamlit web interface
├── config.py              # Pydantic config models + loader + domain validation
├── chat_client.py         # Provider-agnostic ChatClient factory
├── models.py              # Shared Pydantic models (TriageResult, LookupResult, etc.)
├── tracing.py             # OpenTelemetry tracing setup
├── metrics.py             # Metrics collection
├── logging_config.py      # Logging hierarchy (workflow.*)
├── agents/
│   ├── triage.py          # TriageExecutor (LLM: classify intent)
│   ├── question_handler.py # QuestionHandlerExecutor (LLM: answer questions)
│   └── ingestion_preview.py # IngestionPreviewExecutor + refine_ingestion_preview()
├── executors/
│   ├── knowledge_lookup.py # KnowledgeLookupExecutor (deterministic: tag search)
│   └── response_formatter.py # ResponseFormatterExecutor (deterministic: format output)
├── tools/
│   ├── url_scraper.py     # fetch_url() — HTTP fetch + HTML parsing
│   ├── knowledge_retrieval.py # get_available_tags(), search_by_tags()
│   ├── knowledge_ingestion.py # create_note(), add_url_to_index(), update_instructions_file()
│   └── org_context.py     # get_instructions_context(), read_note(), search_knowledge()
├── workflows/
│   └── main_workflow.py   # build_workflow() — graph construction
└── config/
    ├── config.yaml        # Runtime configuration
    ├── instructions/      # Agent instruction files (markdown with template variables)
    └── templates/         # Base note template
```

### Executor Registration Pattern
- Executors are registered as lambda factories with `WorkflowBuilder.register_executor()`
- Lazy instantiation avoids shared state across workflow runs
- LLM-backed executors wrap `ChatAgent` instances with bound tool functions
- Deterministic executors use pure Python logic (no LLM calls)

---

## State Management

### Application State (Streamlit Session State)
- `st.session_state.initialized`: App initialization flag
- `st.session_state.messages`: Current chat message history
- `st.session_state.workflow`: Built `Workflow` instance
- `st.session_state.config`: Loaded `AppConfig` instance
- `st.session_state.processing`: Whether a request is in-flight
- `st.session_state.pending_ingestions`: List of `IngestionPreviewResult` awaiting approval
- `st.session_state.event_loop`: Persistent asyncio event loop
- `st.session_state.metrics_enabled`: Metrics toggle
- `st.session_state.total_queries`: Session query counter
- `st.session_state.session_start`: Session start timestamp

### Persistent State (Local Storage)
- **Knowledge Stores**: Per-domain directories under `../knowledge/` with YAML indexes and markdown files
- **Metrics**: JSONL files in `metrics/` directory
- **User Config**: `config/config.yaml` for preferences

### State Flow
```
User Input → Streamlit chat_input → Session State Update
     ↓
[If pending_ingestions] → Refinement Mode (refine_ingestion_preview)
[Else]                 → Full Workflow (build_workflow → run)
     ↓
WorkflowOutput → format_workflow_output → Chat Message + Pending Ingestion
     ↓
[Approve] → execute_ingestion → Knowledge Store Write
[Dismiss] → Discard Preview
```

---

## Data Flow

### Message Processing Flow
```
1. User Input (text, URL, or content to store)
        ↓
2. UI Layer captures input (Streamlit or CLI)
        ↓
3. Check for pending ingestions:
   - If pending → Refinement Mode (refine_ingestion_preview)
   - If none   → Full workflow (steps 4-7)
        ↓
4. TriageExecutor classifies intent:
   - question: User wants an answer
   - ingestion: User wants to store content
   - both: User wants both
        ↓
5. KnowledgeLookupExecutor searches across all domains for matching tags
        ↓
6. Conditional routing based on intent:
   ├─→ QuestionHandlerExecutor: Synthesizes answer from context
   └─→ IngestionPreviewExecutor: Proposes knowledge write (no actual write)
        ↓
7. ResponseFormatterExecutor merges into WorkflowOutput
        ↓
8. UI renders response + pending ingestion (if any)
        ↓
9. User approves/dismisses/refines pending ingestion
```

### Knowledge Ingestion Flow
```
1. User provides content (URL/text/facts)
        ↓
2. TriageExecutor identifies as "ingestion" or "both"
        ↓
3. IngestionPreviewExecutor proposes action:
   - create_note: New markdown note with structured content
   - add_url: Index a URL with summary and tags
   - update_context: Append to domain context file
   - skip: Content not worth storing
        ↓
4. Preview displayed in UI with Approve/Dismiss buttons
        ↓
5. [Optional] User refines via chat (refinement loop)
        ↓
6. User approves → execute_ingestion() dispatches to:
   - create_note() → writes markdown file + updates _index.yaml
   - add_url_to_index() → adds entry to url_index.yaml
   - update_instructions_file() → appends section to context.md
```

---

## Technical Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Streamlit 1.x |
| **Backend** | Python 3.11+ |
| **Agent Framework** | Microsoft Agent Framework (`agent-framework-ollama`, `agent-framework-devui`) |
| **Local LLM** | Ollama |
| **Cloud LLM** | OpenAI API (optional) |
| **Enterprise LLM** | Azure OpenAI (optional) |
| **Knowledge Store** | YAML-indexed markdown files (per-domain) |
| **Web Scraping** | httpx + lxml |
| **Data Validation** | Pydantic v2 |
| **Config Management** | PyYAML + Pydantic |
| **Tracing** | OpenTelemetry (OTLP gRPC) |
| **Metrics** | Custom JSONL collector |

### Dependencies
```
agent-framework-ollama>=0.0.1a1
agent-framework-devui>=1.0.0b1
streamlit>=1.28
httpx[http2]
lxml>=5.0.0
beautifulsoup4
pydantic>=2.0
pyyaml
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-grpc
```

---

## Authentication Process

### Local Mode (Primary)
- **No authentication required** for single-user local deployment
- File system permissions govern access to knowledge stores

### Model Provider Authentication
- **Ollama**: No auth (localhost)
- **OpenAI**: API key via `config.yaml` or `OPENAI_API_KEY` environment variable
- **Azure OpenAI**:
  - Endpoint configured in `config.yaml` or `AZURE_OPENAI_ENDPOINT` env var
  - Authentication via `DefaultAzureCredential` (supports managed identity, CLI login, etc.)

### Configuration Security
```yaml
# config.yaml (secrets via env vars or inline)
models:
  default_provider: "ollama"
  providers:
    ollama:
      host: "http://localhost:11434"
      default_model: "llama3.1:8b"
    openai:
      api_key: null  # or set OPENAI_API_KEY env var
      default_model: "gpt-4o-mini"
    azure_openai:
      endpoint: null  # or set AZURE_OPENAI_ENDPOINT env var
      default_model: null  # deployment name
```

### Future Considerations
- Optional basic auth for remote-hosted instances
- API key management for third-party tool integrations

---

## Route Design

### Streamlit Page Structure (Tabbed Single-Page App)
- **No traditional routing**—Streamlit manages view state internally

### Tab Layout
| Tab | Component | Content |
|-----|-----------|---------|
| 💬 Chat | Main chat interface | Message history, refinement mode banner, pending ingestion approvals |
| 📚 Knowledge Base | Knowledge explorer | Org context, URL index, Notes browser (per-domain) |
| 📊 Metrics | Metrics dashboard | Session stats, metrics file listing |

### Sidebar
| Component | Description |
|-----------|-------------|
| Connection Status | Provider, host/model info, reload button |
| Session Controls | New Chat, Clear buttons |
| Logging | Log level selector |
| Session Metrics | Query count, success/fail, avg time, duration |
| Knowledge Status | Context size, URL count, note count |

### Navigation Flow
```
App Load → Initialize (config, logging, metrics, tracing, domains, workflow)
    ↓
Tab: Chat → Chat input → [Refinement or Workflow] → Response
    ↓
Tab: Knowledge Base → Browse domains, URLs, notes
    ↓
Tab: Metrics → View session and historical stats
```

---

## API Design

### Internal Service APIs (Python Interfaces)

#### ChatClient Factory
```python
def create_chat_client(purpose: str = "agent") -> ChatClient:
    """Create provider-appropriate ChatClient based on config.models.default_provider."""
    # Supports: ollama, openai, azure_openai
```

#### Executor Interface (Microsoft Agent Framework)
```python
class MyExecutor(Executor):
    agent: ChatAgent  # LLM-backed executors wrap a ChatAgent

    @handler
    async def handle(self, input: InputModel, ctx: WorkflowContext[OutputModel]) -> None:
        result = await self.agent.run(prompt)
        await ctx.send_message(parsed_result)
```

#### Workflow Factory
```python
def build_workflow() -> Workflow:
    """Build the WorkflowBuilder graph with all executors and edges."""
```

#### Ingestion Refinement
```python
async def refine_ingestion_preview(
    current: IngestionPreviewResult,
    user_feedback: str,
) -> IngestionPreviewResult:
    """Refine a pending ingestion preview based on user chat feedback."""
```

### External API Integrations

#### Ollama (Local)
- **Endpoint**: `http://localhost:11434/api/chat`
- **Method**: POST (streaming)
- **SDK**: `agent-framework-ollama`

#### OpenAI (Cloud)
- **Endpoint**: `https://api.openai.com/v1`
- **Auth**: API key
- **SDK**: `agent-framework-openai`

#### Azure OpenAI (Enterprise)
- **Endpoint**: User-configured Azure endpoint
- **Auth**: `DefaultAzureCredential`
- **SDK**: `agent-framework-azure-ai`

---

## Knowledge Store Design

### Storage Architecture
Knowledge data lives **outside** the application repository (`../knowledge/`) so code and data can be versioned independently.

```
../knowledge/                          # Separate from app code
├── general/                           # Domain: general
│   ├── context.md                     # Domain-level org context
│   ├── url_index.yaml                 # Indexed URLs with metadata
│   ├── note_template.md               # Per-domain note template (auto-generated)
│   └── notes/
│       ├── _index.yaml                # Notes index with metadata
│       └── YYYYMMDD-slug.md           # Individual notes
├── technology/                        # Domain: technology
│   ├── context.md
│   ├── url_index.yaml
│   ├── note_template.md
│   └── notes/
│       ├── _index.yaml
│       └── *.md
├── social/                            # Domain: social
│   └── ...
└── entertainment/                     # Domain: entertainment
    └── ...
```

### Domain Configuration (config.yaml)
```yaml
knowledge:
  confidence_threshold: 0.7
  relevance_threshold: 0.6
  domains:
    general:
      description: "General notes and documentation"
      notes_directory: "../knowledge/general/notes"
      context_file: "../knowledge/general/context.md"
      url_index_file: "../knowledge/general/url_index.yaml"
      template: "../knowledge/general/note_template.md"
      frontmatter_defaults:
        category: "general"
        priority: "medium"
        reviewed: false
```

### Domain Validation & Initialization
- On startup, `validate_knowledge_domains()` checks each domain's directory structure
- Missing stores are auto-initialized in web mode; CLI prompts interactively
- `initialize_domain()` creates directories + seed files + customized note template from base template

### Note Frontmatter Schema
```yaml
---
title: "Document Title"
date: "2026-02-16"
domain: "technology"
tags: [kubernetes, deployment]
category: "technology"
priority: "medium"
reviewed: false
source: "user"
confidence: 0.9
relevance: 0.85
---
# Content here...
```

### URL Index Schema (url_index.yaml)
```yaml
urls:
  - url: "https://docs.example.com/guide"
    title: "Example Guide"
    domain: "technology"
    context: "Team reference documentation"
    summary: "Comprehensive guide covering..."
    tags: [documentation, reference]
    added: "2026-02-16"
    confidence: 0.9
    relevance: 0.85
```

### Notes Index Schema (_index.yaml)
```yaml
notes:
  - filename: "20260216-kubernetes-best-practices.md"
    title: "Kubernetes Best Practices"
    domain: "technology"
    summary: "Key practices for production Kubernetes deployments"
    tags: [kubernetes, best-practices]
    created: "2026-02-16"
    source: "user"
    confidence: 0.9
    relevance: 0.85
```

### Query Strategy
1. **Tag-based search**: `search_by_tags()` scans all domain `_index.yaml` and `url_index.yaml` files
2. **Domain filtering**: Results annotated with `_domain_key` for cross-domain aggregation
3. **Confidence scoring**: Results ranked by confidence and relevance scores
4. **Threshold gating**: Content below configured thresholds flagged for human review

---

*Document Version: 2.0*
*Last Updated: February 2026*
