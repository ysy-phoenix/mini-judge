import os
import re
import tempfile
from re import Pattern

from app.core.config import settings

DANGEROUS_PYTHON_IMPORTS: set[str] = {
    "os.system",
    "subprocess",
    "pty",
    "shutil",
    "importlib",
    "__import__",
    "eval",
    "exec",
    "pickle",
    "socket",
    "requests",
}

DANGEROUS_CPP_FUNCTIONS: set[str] = {
    "system",
    "popen",
    "fork",
    "exec",
    "ProcessBuilder",
    "Runtime.getRuntime",
    "socket",
}

PYTHON_IMPORT_PATTERN: Pattern = re.compile(
    r"^(?:from\s+([^.]+)(?:\..+)?\s+import\s+.+|import\s+([^.]+)(?:\..+)?)",
    re.MULTILINE,
)


def is_code_safe(code: str, language: str) -> bool:
    r"""Check if the submitted code is safe to execute."""
    if language == "python":
        return is_python_code_safe(code)
    elif language in ["c", "cpp"]:
        return is_cpp_code_safe(code)
    return False


def is_python_code_safe(code: str) -> bool:
    r"""Check if Python code is safe to execute."""
    # Check for dangerous imports
    for line in code.split("\n"):
        line = line.strip()
        if any(danger in line for danger in DANGEROUS_PYTHON_IMPORTS):
            return False

    return True


def is_cpp_code_safe(code: str) -> bool:
    r"""Check if C/C++ code is safe to execute."""
    # Check for dangerous functions
    for danger in DANGEROUS_CPP_FUNCTIONS:
        if re.search(rf"\b{re.escape(danger)}\s*\(", code):
            return False

    return True


def create_secure_execution_directory() -> str:
    r"""Create a secure directory for code execution."""
    base_dir = os.path.expanduser(settings.CODE_EXECUTION_DIR)
    os.makedirs(base_dir, exist_ok=True)

    # Create a unique temporary directory
    temp_dir = tempfile.mkdtemp(dir=base_dir)
    os.chmod(temp_dir, 0o700)  # Restrict permissions

    return temp_dir


def clean_execution_directory(directory: str) -> None:
    r"""Clean up the execution directory."""
    import shutil

    if os.path.exists(directory) and os.path.isdir(directory):
        shutil.rmtree(directory)
