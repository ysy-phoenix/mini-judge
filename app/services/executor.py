import asyncio
import os
import time
from collections.abc import Callable

from app.core.config import settings
from app.models.schemas import JudgeMode, JudgeStatus, JudgeTestCase, Language, TestCaseResult
from app.services.leetcode import judge_leetcode
from app.services.utils import (
    cleanup_process,
    managed_process_execution,
)
from app.utils.logger import logger


async def execute_code(
    executable_path_or_code: str | Callable,
    language: Language,
    mode: JudgeMode,
    test_case: JudgeTestCase,
    time_limit_sec: int = settings.MAX_EXECUTION_TIME,
    memory_limit_mb: int = settings.MAX_MEMORY,
) -> TestCaseResult:
    r"""Execute code with specified constraints and return the result."""
    memory_limit_bytes = memory_limit_mb * 1024 * 1024
    input_data = test_case.input

    # Set up environment variables for Python processes to improve memory management
    env = None
    if language == Language.PYTHON:
        env = os.environ.copy()
        env["PYTHONMALLOC"] = "malloc"  # Use system malloc, easier to monitor
        env["PYTHONMALLOCSTATS"] = "1"  # Enable memory statistics
        env["MPLCONFIGDIR"] = "/tmp"  # Prevent matplotlib cache issues

        if mode == JudgeMode.LEETCODE:
            return await judge_leetcode(
                executable_path_or_code,
                input_data,
                test_case.expected,
                time_limit_sec,
                memory_limit_bytes,
            )
        else:
            cmd = ["python", executable_path_or_code]
    else:  # C or C++
        # For compiled languages, use the executable path
        cmd = [executable_path_or_code]

    return await execute_with_limits(cmd, input_data, time_limit_sec, memory_limit_bytes, env)


async def execute_with_limits(
    cmd: list[str],
    input_data: str,
    time_limit_sec: float,
    memory_limit_bytes: int,
    env: dict = None,
) -> TestCaseResult:
    start_time = time.time()
    memory_usage = 0

    # Use the managed process execution context for better resource control
    async with managed_process_execution(time_limit_sec, memory_limit_bytes) as ctx:
        process_id = None

        try:
            # Run the command with process group setup
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=ctx["setup_child_process"],
                env=env,
            )

            process_id = process.pid
            # Register and monitor the process
            ctx["register_process"](process.pid)
            ctx["start_monitoring"](process.pid)

            # Set a timeout using asyncio
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input_data.encode()),
                    timeout=time_limit_sec + 0.5,  # Reduced buffer time for more responsive killing
                )

                execution_time = time.time() - start_time

                # Extract memory usage from monitoring tasks if available
                for task in ctx.get("monitoring_tasks", []):
                    if not task.done():
                        continue
                    try:
                        result = task.result()
                        if isinstance(result, int) and result > memory_usage:
                            memory_usage = result
                    except Exception:
                        pass

                # Process the results
                status = JudgeStatus.ACCEPTED
                stdout_str = stdout.decode("utf-8", errors="replace").strip()
                stderr_str = stderr.decode("utf-8", errors="replace").strip()

                if process.returncode != 0:
                    # Handle various error conditions based on return code
                    if process.returncode in (-6, -11):  # SIGABRT, SIGSEGV
                        status = JudgeStatus.MEMORY_LIMIT_EXCEEDED
                    elif process.returncode == -9:  # SIGKILL
                        status = JudgeStatus.TIME_LIMIT_EXCEEDED
                    elif process.returncode == 1 and "AssertionError" in stderr_str:
                        status = JudgeStatus.WRONG_ANSWER
                    else:
                        status = JudgeStatus.RUNTIME_ERROR

                    stderr_str = f"Process return code {process.returncode}\n{stderr_str}"

                return TestCaseResult(
                    status=status,
                    execution_time=execution_time,
                    memory_usage=memory_usage,
                    actual_output=stdout_str,
                    error_message=stderr_str,
                )

            except asyncio.TimeoutError:
                # Always explicitly clean up on timeout
                if process_id:
                    await cleanup_process(process_id)

                return TestCaseResult(
                    status=JudgeStatus.TIME_LIMIT_EXCEEDED,
                    execution_time=time_limit_sec,
                    memory_usage=memory_usage,
                    error_message="Time limit exceeded",
                )

        except Exception as e:
            # Ensure any process is cleaned up in case of error
            if process_id:
                await cleanup_process(process_id)

            logger.error(f"Execute with limits exception: {str(e)}")
            return TestCaseResult(
                status=JudgeStatus.SYSTEM_ERROR, error_message=f"Execution error: {str(e)}"
            )
