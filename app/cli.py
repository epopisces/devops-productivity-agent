"""Command Line Interface for Multi-Agent Workflow.

Simple CLI chat interface using the WorkflowBuilder-based graph.
"""

import asyncio
import logging
import sys
import time

from app.config import get_config, validate_knowledge_domains, initialize_domain
from app.logging_config import setup_logging, LOGGER_ROOT
from app.metrics import configure_metrics, get_metrics_collector
from app.models import WorkflowOutput, QuestionResult, IngestionPreviewResult
from app.tracing import configure_tracing
from app.workflows import build_workflow

# CLI logger
logger = logging.getLogger("workflow.cli")


def print_welcome():
    """Print welcome message and instructions."""
    print("\n" + "=" * 60)
    print("  Multi-Agent Workflow Assistant (MVP)")
    print("=" * 60)
    print("\nCommands:")
    print("  /new     - Start a new conversation")
    print("  /config  - Show current configuration")
    print("  /metrics - Show current session metrics")
    print("  /loglevel <level> - Set logging level (e.g., /loglevel debug)")
    print("  /quit    - Exit the application")
    print("  /help    - Show this help message")
    print("\nTip: Paste a URL to analyze its content!")
    print("-" * 60 + "\n")


def print_config():
    """Print current configuration."""
    config = get_config()
    root_logger = logging.getLogger(LOGGER_ROOT)
    print("\n--- Configuration ---")
    print(f"Provider: {config.models.provider}")
    if config.models.provider == "ollama":
        print(f"Ollama Host: {config.models.ollama.host}")
        print(f"Model: {config.models.get_active_model_id()}")
    else:
        print(f"Azure OpenAI Endpoint: {config.models.azure_openai.endpoint}")
        print(f"Deployment: {config.models.get_active_model_id()}")
    print(f"Scraper Timeout: {config.scraper.timeout}s")
    print(f"Log Level: {logging.getLevelName(root_logger.level)}")
    print(f"Metrics: {'enabled' if config.metrics.enabled else 'disabled'}")
    print(f"Progress Indicators: {'enabled' if config.progress.enabled else 'disabled'}")
    print("-" * 20 + "\n")


def set_log_level(level_name: str):
    """Set logging level dynamically."""
    root_logger = logging.getLogger(LOGGER_ROOT)
    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        print(f"\nInvalid log level: {level_name}\n")
        return
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)
    print(f"\n--- Logging set to {logging.getLevelName(level)} ---\n")
    logger.info(f"Logging level changed to {logging.getLevelName(level)}")


def print_metrics():
    """Print current session metrics."""
    collector = get_metrics_collector()
    summary = collector.get_summary()
    print("\n--- Session Metrics ---")
    print(f"Total Operations: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Total Time: {summary['total_time_seconds']:.2f}s")
    print(f"Average Time: {summary['average_time_seconds']:.2f}s")
    print("-" * 22 + "\n")


async def chat_loop(workflow):
    """Main chat loop.

    Args:
        workflow: The built Workflow instance.
    """
    print_welcome()
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith("/"):
                command = user_input.lower()

                if command == "/quit" or command == "/exit":
                    logger.info("User requested exit")
                    print("\nGoodbye!")
                    break
                elif command == "/new":
                    print("\n--- New conversation started ---\n")
                    continue
                elif command == "/config":
                    print_config()
                    continue
                elif command.startswith("/loglevel "):
                    level_name = command.split(" ", 1)[-1].strip()
                    set_log_level(level_name)
                    continue
                elif command == "/help":
                    print_welcome()
                    continue
                elif command == "/metrics":
                    print_metrics()
                    continue
                else:
                    print(f"Unknown command: {user_input}")
                    print("Type /help for available commands.\n")
                    continue
            
            # Process user message through workflow
            config = get_config()
            metrics_collector = get_metrics_collector()
            
            print("\nAssistant: ", end="", flush=True)
            
            try:
                start_time = time.time()
                
                events = await workflow.run(user_input)
                outputs = [o for o in events.get_outputs() if isinstance(o, WorkflowOutput)]
                
                # Format and display
                response = _format_cli_output(outputs)
                print(response)
                print()  # Blank line for spacing
                
                # Record metrics
                duration = time.time() - start_time
                model_id = config.models.get_active_model_id()
                metrics_collector.record(
                    operation="query",
                    agent="workflow",
                    duration_seconds=duration,
                    success=True,
                    input_length=len(user_input),
                    output_length=len(response),
                    model=model_id,
                )
                
            except Exception as e:
                duration = time.time() - start_time if 'start_time' in dir() else 0
                model_id = config.models.get_active_model_id()
                metrics_collector.record(
                    operation="query",
                    agent="workflow",
                    duration_seconds=duration,
                    success=False,
                    error_message=str(e),
                    input_length=len(user_input),
                    model=model_id,
                )
                
                error_msg = str(e)
                if "invalid character" in error_msg and "escape code" in error_msg:
                    logger.error(f"Tool call JSON error: {e}", exc_info=True)
                    print(f"\n\nError: The model generated malformed JSON for a tool call.")
                    print("This is common with smaller models when handling complex content.")
                    print("\nSuggestions:")
                    print("  1. Try a more capable model: ollama pull qwen3:8b")
                    print("  2. Update config.yaml: model_id: \"qwen3:8b\"")
                    print("  3. Or try: llama3.2:3b, mistral:7b, or qwen3:4b")
                    print("\nYou can also try rephrasing your request more simply.\n")
                else:
                    logger.error(f"Error during workflow execution: {e}", exc_info=True)
                    print(f"\n\nError: {e}")
                    print("Check that the LLM provider is running and accessible.")
                    if config.models.provider == "ollama":
                        print(f"Try: ollama pull {config.models.get_active_model_id()}\n")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type /quit to exit.\n")
        except EOFError:
            logger.info("EOF received, exiting")
            print("\nGoodbye!")
            break


def _format_cli_output(outputs: list[WorkflowOutput]) -> str:
    """Format WorkflowOutput list for terminal display."""
    if not outputs:
        return "(no response generated)"

    parts: list[str] = []
    question: QuestionResult | None = None
    ingestion: IngestionPreviewResult | None = None

    for out in outputs:
        if out.question_result and not question:
            question = out.question_result
        if out.ingestion_result and not ingestion:
            ingestion = out.ingestion_result

    if question:
        parts.append(question.answer)
        if question.suggest_web_search and question.search_query:
            parts.append(f"\n  [Web search suggested: {question.search_query}]")

    if ingestion:
        parts.append(f"\n--- Ingestion Preview ---")
        parts.append(f"  Action: {ingestion.action}")
        parts.append(f"  Title:  {ingestion.title}")
        if ingestion.tags:
            parts.append(f"  Tags:   {', '.join(ingestion.tags)}")
        parts.append(f"  Confidence: {ingestion.confidence:.0%}")
        if ingestion.requires_review:
            parts.append("  ⚠ Requires human review")

    return "\n".join(parts)


async def async_main():
    """Async main entry point."""
    config = get_config()
    
    # Setup logging from config
    setup_logging(
        level=config.logging.level,
        log_file=config.logging.file,
    )
    logger.info("Multi-Agent Workflow CLI starting")
    
    # Configure metrics collection
    configure_metrics(
        metrics_dir=config.metrics.directory,
        enabled=config.metrics.enabled,
    )
    if config.metrics.enabled:
        logger.info(f"Metrics collection enabled: {config.metrics.directory}")
    
    # Configure tracing
    configure_tracing(config.tracing)

    # Validate knowledge domains
    domain_results = validate_knowledge_domains(config)
    uninitialized = [r for r in domain_results if not r.ok]
    if uninitialized:
        print("\n⚠  Some knowledge domains are not initialized:")
        for result in uninitialized:
            print(f"   • {result.key}: missing {', '.join(result.missing)}")
        answer = input("\nCreate missing folders/files now? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            for result in uninitialized:
                created = initialize_domain(result.key, config.knowledge.domains[result.key])
                for p in created:
                    print(f"   ✓ Created {p}")
            print()
        else:
            print("  Skipped — you can create them later.\n")

    provider = config.models.provider
    model_id = config.models.get_active_model_id()
    if provider == "ollama":
        print(f"\nConnecting to Ollama at {config.models.ollama.host}...")
        print(f"Using model: {model_id}")
    else:
        print(f"\nUsing {provider} model: {model_id}")
    print(f"Logging level: {config.logging.level}")
    
    try:
        workflow = build_workflow()
        await chat_loop(workflow)
    except Exception as e:
        logger.error(f"Failed to initialize workflow: {e}", exc_info=True)
        print(f"\nError initializing workflow: {e}")
        print("\nTroubleshooting:")
        if provider == "ollama":
            print("1. Make sure Ollama is running: ollama serve")
            print(f"2. Pull the model: ollama pull {config.models.get_active_model_id()}")
        else:
            print(f"1. Check {provider} configuration")
            print("2. Ensure authentication is configured")
        print("3. Check your .env or config/config.yaml settings")
        sys.exit(1)
    
    # Save session metrics on shutdown
    metrics_collector = get_metrics_collector()
    metrics_file = metrics_collector.save_session()
    if metrics_file:
        print(f"\nSession metrics saved to: {metrics_file}")
    
    logger.info("CLI shutdown complete")


def main():
    """Main entry point for CLI."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
