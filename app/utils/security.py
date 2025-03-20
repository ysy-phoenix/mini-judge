import os
import re
import tempfile
from re import Pattern

from app.core.config import settings
from app.utils.logger import logger

DANGEROUS_PYTHON_IMPORTS: dict[str, list[str]] = {
    "os": [
        "system",
        "popen",
        "spawn",
        "exec",
        "execl",
        "execlp",
        "execle",
        "execv",
        "execvp",
        "execve",
        "kill",
        "killpg",
        "pclose",
        "putenv",
        "remove",
        "removedirs",
        "rmdir",
        "setuid",
        "setsid",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "unlink",
        "fork",
        "forkpty",
    ],
    "subprocess": ["*"],
    "pty": ["*"],
    "shutil": ["rmtree", "move", "copy", "copyfile", "copytree", "rmtree", "make_archive"],
    "importlib": ["*"],
    "__import__": ["*"],
    "eval": ["*"],
    "exec": ["*"],
    "pickle": ["*"],
    "socket": ["*"],
    "requests": ["*"],
}

ALLOWED_OS_SUBMODULES = {
    "path": "*",
    "environ": "*",
    "read": True,
    "write": True,
    "fstat": True,
    "getcwd": True,
    "listdir": True,
    "mkdir": True,
    "makedirs": True,
    "stat": True,
    "access": True,
    "name": True,
    "sep": True,
    "linesep": True,
    "curdir": True,
    "pardir": True,
    "pathsep": True,
    "devnull": True,
    "altsep": True,
    "extsep": True,
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
    # Standard import: import module [as alias]
    re.compile(r"^\s*import\s+(\w+(?:\s*,\s*\w+)*)", re.MULTILINE),
    # From module import: from module import name [as alias] [, name2 [as alias2]]
    re.compile(r"^\s*from\s+(\w+)(?:\.\w+)*\s+import\s+([^#\n]+)", re.MULTILINE),
    # __import__ function call
    re.compile(r'__import__\s*\(\s*[\'"](\w+)[\'"]', re.MULTILINE),
    # Dynamic import: importlib.import_module('modulename')
    re.compile(r'importlib\.import_module\s*\(\s*[\'"](\w+)[\'"]', re.MULTILINE),
]

# Match commented out code
COMMENT_PATTERN: Pattern = re.compile(r"^\s*#.*$|#.*$", re.MULTILINE)

# Use multiple simple regex patterns instead of complex backtracking
# 1. Match all eval and exec function calls
EXEC_CALL_PATTERN: Pattern = re.compile(r"\b(eval|exec)\s*\(", re.MULTILINE)

# 2. Collect user-defined functions
FUNC_DEF_PATTERN: Pattern = re.compile(r"def\s+(\w+)\s*\(", re.MULTILINE)

# 3. Check variable assignments, e.g. x = eval
VAR_ASSIGN_PATTERN: Pattern = re.compile(r"\b(\w+)\s*=\s*eval|exec\b", re.MULTILINE)

# 4. Check indirect calls
INDIRECT_EXEC_PATTERN: Pattern = re.compile(
    r"__builtins__\s*(\[|\.)[\'\"]?(eval|exec)[\'\"]?(\]|\))", re.MULTILINE
)

# Check dangerous dynamic attribute access
DANGEROUS_ATTR_PATTERN = re.compile(
    r"getattr\s*\(\s*os\s*,\s*['\"](\w+)['\"]|\w+\s*=\s*getattr\s*\(\s*os\s*,", re.MULTILINE
)


def is_code_safe(code: str, language: str) -> bool:
    r"""Check if the submitted code is safe to execute."""
    if language == "python":
        return is_python_code_safe(code)
    elif language in ["c", "cpp"]:
        return is_cpp_code_safe(code)
    return False


def is_python_code_safe(code: str) -> bool:
    r"""Check if Python code is safe to execute using strict regex patterns."""
    code = code.split("def check(candidate):")[0]  # FIXME: remove check for LeetCode
    code_without_comments = COMMENT_PATTERN.sub("", code)

    # Collect all user-defined functions and variables
    user_defined = set()
    for match in FUNC_DEF_PATTERN.finditer(code_without_comments):
        user_defined.add(match.group(1))

    for match in VAR_ASSIGN_PATTERN.finditer(code_without_comments):
        user_defined.add(match.group(1))

    # Check each eval or exec call
    for match in EXEC_CALL_PATTERN.finditer(code_without_comments):
        func_name = match.group(1)
        # Get the position of the function call
        pos = match.start()

        # Check if it's a user-defined function
        if func_name in user_defined:
            continue

        # Check if it's an object method call (e.g. obj.eval)
        if pos > 0 and code_without_comments[pos - 1] == ".":
            continue

        # Check if it's part of a variable name (e.g. my_eval)
        is_part_of_var = False
        if pos > 0:
            char_before = code_without_comments[pos - 1]
            if char_before.isalnum() or char_before == "_":
                is_part_of_var = True

        if not is_part_of_var:
            logger.warning(f"Dangerous function call detected: {func_name}")
            return False

    # Check indirect access to dangerous functions
    if INDIRECT_EXEC_PATTERN.search(code_without_comments):
        logger.warning("Indirect access to dangerous functions detected")
        return False

    # Check dangerous dynamic attribute access to os
    for match in DANGEROUS_ATTR_PATTERN.finditer(code_without_comments):
        attr = match.group(1) if match.group(1) else "unknown"
        logger.warning(f"Detected dynamic access to os attributes: {attr}")
        return False

    # Check dangerous imports
    for pattern in PYTHON_IMPORT_PATTERNS:
        for match in pattern.finditer(code_without_comments):
            # Extract module name and imported functions according to different patterns
            if pattern == PYTHON_IMPORT_PATTERNS[0]:  # Standard import: import module [as alias]
                modules = [m.strip() for m in match.group(1).split(",")]
                for module in modules:
                    module = module.split(" as ")[0].strip()
                    # If it's the os module, allow the import, but check function calls later
                    if module in DANGEROUS_PYTHON_IMPORTS and module != "os":
                        logger.warning(f"Standard import detected: {module}")
                        return False

            elif pattern == PYTHON_IMPORT_PATTERNS[1]:  # from module import name [as alias]
                module = match.group(1).strip()
                if module in DANGEROUS_PYTHON_IMPORTS:
                    imports = [
                        i.strip().split(" as ")[0].strip() for i in match.group(2).split(",")
                    ]

                    dangerous_items = DANGEROUS_PYTHON_IMPORTS[module]

                    # Special handling for the os module
                    if module == "os":
                        for imp in imports:
                            # If the imported is in the blacklist
                            if imp in dangerous_items:
                                logger.warning(f"Dangerous os function import detected: {imp}")
                                return False
                            if imp == "*":
                                logger.warning("Wildcard import from os is not allowed")
                                return False
                    else:
                        # Other module handling
                        if "*" in dangerous_items:
                            logger.warning(f"from module import detected: {module}")
                            return False

                        for imp in imports:
                            if imp in dangerous_items:
                                logger.warning(f"from module import detected: {module}.{imp}")
                                return False

            else:  # __import__ or dynamic import
                module = match.group(1).strip()
                if module in DANGEROUS_PYTHON_IMPORTS and module != "os":
                    logger.warning(f"__import__ or dynamic import detected: {module}")
                    return False

    # Check possible direct usage (e.g. os.system)
    for module, dangerous_funcs in DANGEROUS_PYTHON_IMPORTS.items():
        if module == "os":
            # Special handling for the os module, check dangerous function calls
            for func in dangerous_funcs:
                pattern = re.compile(rf"\bos\.{re.escape(func)}\s*\(", re.MULTILINE)
                if pattern.search(code_without_comments):
                    logger.warning(f"Dangerous os function call detected: {func}")
                    return False

            # Check if non-whitelisted os functions or submodules are used
            pattern = re.compile(r"\bos\.(\w+)(?:\s*\(|\s*$|\s+|\.)", re.MULTILINE)
            for match in pattern.finditer(code_without_comments):
                attr = match.group(1)
                # If the attribute is not in the whitelist
                if attr not in ALLOWED_OS_SUBMODULES:
                    logger.warning(f"Disallowed os attribute access: {attr}")
                    return False

        elif "*" in dangerous_funcs:
            # Other module handling
            pattern = re.compile(rf"\b{re.escape(module)}\.(\w+)\s*\(", re.MULTILINE)
            if pattern.search(code_without_comments):
                logger.warning(f"Dangerous module usage detected: {module}")
                return False
        else:
            for func in dangerous_funcs:
                pattern = re.compile(
                    rf"\b{re.escape(module)}\.{re.escape(func)}\s*\(", re.MULTILINE
                )
                if pattern.search(code_without_comments):
                    logger.warning(f"Dangerous function call detected: {module}.{func}")
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


if __name__ == "__main__":
    code = """
import collections
import string
import math
import datetime

from typing import *
from functools import *
from collections import *
from itertools import *
from heapq import *
from bisect import *
from string import *
from operator import *
from math import *

inf = float('inf')



class Solution:
    def evaluate(self, expression: str) -> int:
        def parseVar():
            nonlocal i
            j = i
            while i < n and expression[i] not in " )":
                i += 1
            return expression[j:i]

        def parseInt():
            nonlocal i
            sign, v = 1, 0
            if expression[i] == "-":
                sign = -1
                i += 1
            while i < n and expression[i].isdigit():
                v = v * 10 + int(expression[i])
                i += 1
            return sign * v

        def eval():
            nonlocal i
            if expression[i] != "(":
                return scope[parseVar()][-1] if expression[i].islower() else parseInt()
            i += 1
            if expression[i] == "l":
                i += 4
                vars = []
                while 1:
                    var = parseVar()
                    if expression[i] == ")":
                        ans = scope[var][-1]
                        break
                    vars.append(var)
                    i += 1
                    scope[var].append(eval())
                    i += 1
                    if not expression[i].islower():
                        ans = eval()
                        break
                for v in vars:
                    scope[v].pop()
            else:
                add = expression[i] == "a"
                i += 4 if add else 5
                a = eval()
                i += 1
                b = eval()
                ans = a + b if add else a * b
            i += 1
            return ans

        i, n = 0, len(expression)
        scope = defaultdict(list)
        return eval()


def check(candidate):
    assert candidate(expression = "(let x 2 (mult x (let x 3 y 4 (add x y))))") == 14
    assert candidate(expression = "(let x 3 x 2 x)") == 2
    assert candidate(expression = "(let x 1 y 2 x (add x y) (add x y))") == 5
    """
    print(is_code_safe(code, "python"))
