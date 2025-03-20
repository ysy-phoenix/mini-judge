import os
import re
import tempfile
from re import Pattern

from app.core.config import settings

DANGEROUS_PYTHON_IMPORTS: dict[str, list[str]] = {
    "os": ["system", "popen", "spawn", "exec"],
    "subprocess": ["*"],
    "pty": ["*"],
    "shutil": ["*"],
    "importlib": ["*"],
    "__import__": ["*"],
    "eval": ["*"],
    "exec": ["*"],
    "pickle": ["*"],
    "socket": ["*"],
    "requests": ["*"],
}

DANGEROUS_CPP_FUNCTIONS: set[str] = {
    r"system\s*\(",
    r"popen\s*\(",
    r"fork\s*\(",
    r"exec\w*\s*\(",
    r"ProcessBuilder",
    r"Runtime\.getRuntime",
    r"socket\s*\(",
}

PYTHON_IMPORT_PATTERNS: list[Pattern] = [
    # standard import: import module [as alias]
    re.compile(r"^\s*import\s+(\w+(?:\s*,\s*\w+)*)", re.MULTILINE),
    # from module import name [as alias] [, name2 [as alias2]]
    re.compile(r"^\s*from\s+(\w+)(?:\.\w+)*\s+import\s+([^#\n]+)", re.MULTILINE),
    # __import__ function call
    re.compile(r'__import__\s*\(\s*[\'"](\w+)[\'"]', re.MULTILINE),
    # dynamic import: importlib.import_module('modulename')
    re.compile(r'importlib\.import_module\s*\(\s*[\'"](\w+)[\'"]', re.MULTILINE),
]

# match commented out code
COMMENT_PATTERN: Pattern = re.compile(r"^\s*#.*$|#.*$", re.MULTILINE)

# match eval and exec function calls
DANGEROUS_EXEC_PATTERN: Pattern = re.compile(r"\b(eval|exec)\s*\(", re.MULTILINE)


def is_code_safe(code: str, language: str) -> bool:
    r"""Check if the submitted code is safe to execute."""
    if language == "python":
        return is_python_code_safe(code)
    elif language in ["c", "cpp"]:
        return is_cpp_code_safe(code)
    return False


def is_python_code_safe(code: str) -> bool:
    r"""Check if Python code is safe to execute using strict regex patterns."""
    code_without_comments = COMMENT_PATTERN.sub("", code)

    # check direct dangerous function calls (eval/exec)
    if DANGEROUS_EXEC_PATTERN.search(code_without_comments):
        return False
    return True

    # check dangerous imports
    for pattern in PYTHON_IMPORT_PATTERNS:
        for match in pattern.finditer(code_without_comments):
            # extract module name and imported functions according to different patterns
            if pattern == PYTHON_IMPORT_PATTERNS[0]:  # standard import
                modules = [m.strip() for m in match.group(1).split(",")]
                for module in modules:
                    module = module.split(" as ")[0].strip()
                    if module in DANGEROUS_PYTHON_IMPORTS:
                        return False

            elif pattern == PYTHON_IMPORT_PATTERNS[1]:  # from module import
                module = match.group(1).strip()
                if module in DANGEROUS_PYTHON_IMPORTS:
                    imports = [
                        i.strip().split(" as ")[0].strip() for i in match.group(2).split(",")
                    ]

                    dangerous_items = DANGEROUS_PYTHON_IMPORTS[module]
                    # if all imports of the module are marked as dangerous
                    if "*" in dangerous_items:
                        return False

                    # check specific dangerous imports
                    for imp in imports:
                        if imp in dangerous_items:
                            return False

            else:  # __import__ or dynamic import
                module = match.group(1).strip()
                if module in DANGEROUS_PYTHON_IMPORTS:
                    return False

    # check possible direct usage (e.g. os.system)
    for module, dangerous_funcs in DANGEROUS_PYTHON_IMPORTS.items():
        if "*" in dangerous_funcs:
            # if all functions are marked as dangerous, find direct module usage
            pattern = re.compile(rf"\b{re.escape(module)}\.(\w+)\s*\(", re.MULTILINE)
            if pattern.search(code_without_comments):
                return False
        else:
            # if only specific dangerous functions are marked, check them
            for func in dangerous_funcs:
                pattern = re.compile(
                    rf"\b{re.escape(module)}\.{re.escape(func)}\s*\(", re.MULTILINE
                )
                if pattern.search(code_without_comments):
                    return False

    return True


def is_cpp_code_safe(code: str) -> bool:
    r"""Check if C/C++ code is safe to execute using strict regex patterns."""
    # remove C/C++ style comments
    # single line comment: //
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    # multi-line comment: /* ... */
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)

    # check dangerous functions
    for danger_pattern in DANGEROUS_CPP_FUNCTIONS:
        if re.search(rf"\b{danger_pattern}", code):
            return False

    # check other common dangerous patterns
    # 1. system command execution
    if re.search(r"\bsystem\s*\([^)]*\)", code):
        return False

    # 2. file operation
    if re.search(r'\b(fopen|open|ofstream|ifstream)\s*\([^)]*,\s*["\']w', code):
        return False

    # 3. network socket
    if re.search(r"\bsocket\s*\(", code):
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
