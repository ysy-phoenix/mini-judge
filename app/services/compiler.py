import os
import subprocess
from types import ModuleType

from app.models.schemas import JudgeMode, Language
from app.services.leetcode.template import SCRIPT


async def compile_leetcode_code(code: str, entry_point: str = None) -> tuple[str, str | None]:
    code = SCRIPT.format(user_code=code)
    try:
        tmp_module = ModuleType("tmp_solution", "")
        exec(code, tmp_module.__dict__)
        compiled_obj = None
        if "class Solution" in code:
            compiled_obj = tmp_module.Solution()
        else:
            compiled_obj = tmp_module
        if entry_point:
            if hasattr(compiled_obj, entry_point):
                fn = getattr(compiled_obj, entry_point)
            elif entry_point in tmp_module.__dict__:
                fn = tmp_module.__dict__[entry_point]
            else:
                return "", f"Entry point '{entry_point}' not found"
            if not callable(fn):
                return "", f"Entry point '{entry_point}' is not callable"
            return fn, None
        else:
            return "", "No entry point specified"
    except Exception as e:
        return "", f"Compilation error: {str(e)}"


async def compile_code(
    code: str, mode: JudgeMode, language: Language, working_dir: str, entry_point: str = None
) -> tuple[str, str | None]:
    r"""Compile the submitted code if needed and return the executable path or code itself."""
    if language == Language.PYTHON:
        if mode != JudgeMode.LEETCODE:
            file_path = os.path.join(working_dir, "solution.py")
            with open(file_path, "w") as f:
                f.write(code)
            return file_path, None
        else:  # JudgeMode.LEETCODE
            return await compile_leetcode_code(code, entry_point)
    elif language == Language.C:
        return await _compile_c(code, working_dir)
    elif language == Language.CPP:
        return await _compile_cpp(code, working_dir)
    else:
        raise ValueError(f"Unsupported language: {language}")


async def _compile_c(code: str, working_dir: str) -> tuple[str, str | None]:
    r"""Compile C code and return the executable path."""
    source_path = os.path.join(working_dir, "solution.c")
    executable_path = os.path.join(working_dir, "solution")

    # Write code to file
    with open(source_path, "w") as f:
        f.write(code)

    # Compile with gcc
    proc = subprocess.run(
        ["gcc", "-o", executable_path, source_path, "-Wall", "-O2"],
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        return "", proc.stderr

    return executable_path, None


async def _compile_cpp(code: str, working_dir: str) -> tuple[str, str | None]:
    r"""Compile C++ code and return the executable path."""
    source_path = os.path.join(working_dir, "solution.cpp")
    executable_path = os.path.join(working_dir, "solution")

    # Write code to file
    with open(source_path, "w") as f:
        f.write(code)

    # Compile with g++
    proc = subprocess.run(
        ["g++", "-o", executable_path, source_path, "-Wall", "-O2", "-std=c++17"],
        capture_output=True,
        text=True,
    )

    if proc.returncode != 0:
        return "", proc.stderr

    return executable_path, None
