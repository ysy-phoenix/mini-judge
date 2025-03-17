import logging
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
        "critical": "red reverse",
        "judge.success": "green bold",
        "judge.failure": "red bold",
        "judge.compile": "blue",
        "judge.execute": "blue",
    }
)

console = Console(theme=custom_theme)

rich_handler = RichHandler(
    console=console,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
    show_path=True,
    markup=True,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    handlers=[rich_handler],
)

logger = logging.getLogger("mini_judge")


def truncate_task_id(task_id: str) -> str:
    r"""Truncate the task ID to the first 8 characters."""
    return task_id.split("-")[0]


def log_with_context(message: str, context: dict[str, Any] = None, level: str = "info") -> None:
    r"""Log with context."""
    ctx_str = ""
    if context:
        if "task_id" in context:
            context["task_id"] = truncate_task_id(context["task_id"])
        ctx_items = [f"[bold]{k}[/bold]={v}" for k, v in context.items()]
        ctx_str = " | ".join(ctx_items)

    if level == "info":
        logger.info(f"{message} {ctx_str}")
    elif level == "warning":
        logger.warning(f"{message} {ctx_str}")
    elif level == "error":
        logger.error(f"{message} {ctx_str}")
    elif level == "critical":
        logger.critical(f"{message} {ctx_str}")


def log_judge_start(task_id: str, language: str, mode: str) -> None:
    r"""Log the start of a judge task."""
    logger.info(
        f"[judge.execute]Starting judge task: {truncate_task_id(task_id)} | "
        f"Language: {language} | Mode: {mode}"
    )


def log_judge_compile(task_id: str, success: bool, error: str = None) -> None:
    r"""Log the compile result."""
    task_id = truncate_task_id(task_id)
    if success:
        logger.info(f"[judge.compile]Compilation successful: [bold]{task_id}[/bold]")
    else:
        logger.error(f"[judge.compile]Compilation failed: [bold]{task_id}[/bold] | Error: {error}")


def log_judge_execute(
    task_id: str, test_case_index: int, status: str, time_ms: float, memory_kb: int
) -> None:
    r"""Log the test case execution result."""
    status_color = "green" if status == "accepted" else "red"
    logger.info(
        f"[judge.execute]Test case #{test_case_index}: "
        f"[bold {status_color}]{status}[/bold {status_color}] | "
        f"Time: {time_ms:.2f}ms | Memory: {memory_kb}KB | Task ID: {truncate_task_id(task_id)}"
    )


def log_judge_result(task_id: str, status: str, total_cases: int, passed_cases: int) -> None:
    r"""Log the final judge result."""
    # Status color is used in conditional logic below, so it's needed
    status_color = "green" if status == "accepted" else "red"
    logger.info(
        f"[judge.success]Judge completed: [bold]{truncate_task_id(task_id)}[/bold] | "
        f"Status: [bold {status_color}]{status}[/bold {status_color}] | "
        f"Passed: {passed_cases}/{total_cases}"
    )
