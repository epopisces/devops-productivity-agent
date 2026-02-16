# Multi-Agent Workflow Assistant - AI Coding Instructions

When taking actions to modify or extend code, add a brief summary of actions taken to the changelog section of the README.md file in the root of the repository, with a date stamp and the model(s) used.  The summary can be merged with existing entries of the same date stamp.

## Architecture Overview

This is a **Microsoft Agent Framework** application using a WorkflowBuilder graph:

```
CLI (app/cli.py) / Web (app/web.py)
    → WorkflowBuilder Graph (app/workflows/main_workflow.py)
        → TriageExecutor → KnowledgeLookupExecutor
            → QuestionHandlerExecutor (intent: question/both)
            → IngestionPreviewExecutor (intent: ingestion/both)
        → ResponseFormatterExecutor
```

- **WorkflowBuilder Graph** ([app/workflows/main_workflow.py](../app/workflows/main_workflow.py)): Directed acyclic graph of executors with conditional routing based on classified intent.
- **LLM-backed Executors** ([app/agents/](../app/agents/)): `Executor` subclasses wrapping `ChatAgent` instances (Triage, QuestionHandler, IngestionPreview). Each gets its own `ChatClient` instance.
- **Deterministic Executors** ([app/executors/](../app/executors/)): Pure Python logic (KnowledgeLookup, ResponseFormatter).
- **Tools** ([app/tools/](../app/tools/)): Standalone sync functions bound to ChatAgents or called directly.
- **Multi-Provider LLM**: `create_chat_client()` factory supports Ollama (default), OpenAI, and Azure OpenAI.
- **Ingestion Refinement**: `refine_ingestion_preview()` in [app/agents/ingestion_preview.py](../app/agents/ingestion_preview.py) allows iterative preview editing via chat before approval.

## Key Patterns

### Executor Pattern (WorkflowBuilder)
Executors are registered as lambda factories and wired with conditional edges:
```python
workflow = (
    WorkflowBuilder()
    .register_executor(lambda: TriageExecutor(id="triage"), name="triage")
    .set_start_executor("triage")
    .add_edge("triage", "knowledge_lookup")
    .add_edge("knowledge_lookup", "question_handler", condition=_route_to_question)
    .add_edge("knowledge_lookup", "ingestion_preview", condition=_route_to_ingestion)
    .build()
)
```

### Configuration via Pydantic + YAML
- Config models in [app/config.py](../app/config.py) use Pydantic `BaseModel`
- Runtime config from [config/config.yaml](../config/config.yaml) merged with env vars (`.env`)
- Access config via `get_config()` singleton—never instantiate `AppConfig` directly
- Multi-provider model config under `models.providers` with `models.default_provider` selector
- Per-domain knowledge config under `knowledge.domains`

### Tool Functions Must Be Synchronous
Functions registered as tools (e.g., `fetch_url` in url_scraper) must be **sync**, not async:
```python
def fetch_url(url: Annotated[str, Field(description="...")]) -> str:
    # Sync httpx client, not async
    with httpx.Client(...) as client:
        response = client.get(url)
```

### Knowledge Store Structure (Per-Domain)
Knowledge data lives outside the app repo (`../knowledge/`) to version code and data independently:
```
../knowledge/<domain>/
├── context.md          # Domain-level org context
├── url_index.yaml      # Indexed URLs with metadata
├── note_template.md    # Per-domain note template (auto-generated from base)
└── notes/
    ├── _index.yaml     # Notes index with metadata
    └── *.md            # Individual notes with YAML frontmatter
```
Domains are defined in `config/config.yaml` under `knowledge.domains`.

### Ingestion Preview → Approval Flow
- IngestionPreviewExecutor only **proposes** writes (outputs `IngestionPreviewResult`)
- Pending previews stored in `st.session_state.pending_ingestions`
- While pending, chat messages route to `refine_ingestion_preview()` (refinement mode)
- User clicks Approve → `execute_ingestion()` dispatches to tool functions
- User clicks Dismiss → preview discarded

## Development Workflow

### Setup
```bash
uv venv --python=3.13.11
.venv\Scripts\activate  # Windows
uv pip install -e ".[dev]" --pre  # --pre required for agent-framework preview
```

### Running
```bash
ollama serve  # Terminal 1
python -m app.cli  # Terminal 2 (CLI mode)
streamlit run app/web.py  # Terminal 2 (Web mode)
```

### Testing
```bash
pytest  # Uses pytest-asyncio with asyncio_mode="auto"
```

Tests use fixture-based mocking from [tests/conftest.py](../tests/conftest.py):
- `mock_config`: Returns `AppConfig` with test values
- `mock_get_config`: Patches `app.config.get_config` globally
- `mock_chat_client`: Mocked `OllamaChatClient` with async methods

### Logging Hierarchy
All loggers under `workflow.*` namespace:
- `workflow.cli`, `workflow.web`, `workflow.triage`, `workflow.ingestion_preview`, etc.
- Set level via `/loglevel debug` in CLI or `logging.level` in config.yaml

## Adding New Executors

1. Create executor module in `app/agents/new_executor.py` (LLM-backed) or `app/executors/new_executor.py` (deterministic)
2. For LLM-backed: subclass `Executor`, wrap a `ChatAgent` with tool functions
3. For deterministic: subclass `Executor`, implement `@handler` with sync logic
4. Register in `build_workflow()` in `app/workflows/main_workflow.py`:
   ```python
   .register_executor(lambda: NewExecutor(id="new"), name="new")
   .add_edge("upstream", "new", condition=optional_condition)
   ```
5. Update agent instruction files in `config/instructions/` if LLM-backed

## Adding New Tool Functions

1. Create or add to a module in `app/tools/`
2. Define sync functions with `Annotated[type, Field(description=...)]` signatures
3. Bind to a ChatAgent in the relevant executor's `__init__`

## Dependencies

- `agent-framework-ollama`: Microsoft Agent Framework with Ollama provider (**preview package**)
- `agent-framework-devui`: DevUI integration for tracing/debugging
- `httpx`: HTTP client (sync for tools)
- `lxml`: Fast HTML parsing
- `beautifulsoup4`: HTML parsing
- `pydantic`: Config validation and tool parameter schemas
- `pyyaml`: YAML config/knowledge store parsing
- `opentelemetry-sdk`: Tracing instrumentation
- `opentelemetry-exporter-otlp-proto-grpc`: OTLP trace export

## Common Issues

- **JSON escaping errors on tool calls**: Use larger model (qwen3:4b recommended over 1.7b)
- **Chat outputs tool calls as text**: Some models may output tool calls as text; switch to recommended models for proper tool calling
- **Slow responses**: Model inference is local; expect 5-15s depending on hardware
- **Config not loading**: Check `config/config.yaml` exists and `models.default_provider` is set
- **Wrong domain selection**: Ensure triage/ingestion_preview instruction files include `{domain_list}` placeholder
