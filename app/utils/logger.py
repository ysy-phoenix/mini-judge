import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Define custom theme
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
        "critical": "red reverse",
    }
)

# Create console and handler
console = Console(theme=custom_theme)
rich_handler = RichHandler(
    console=console,
    rich_tracebacks=True,
    tracebacks_show_locals=True,
    show_path=True,
    markup=True,
)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    handlers=[rich_handler],
)

logger = logging.getLogger("mini_judge")
