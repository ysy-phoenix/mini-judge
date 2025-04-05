import asyncio
import time
from collections.abc import Callable

import psutil

from app.core.config import settings
from app.models.schemas import JudgeMode, JudgeStatus, JudgeTestCase, Language, TestCaseResult
from app.services.leetcode import judge_leetcode
from app.services.utils import monitor_process_memory, reliability_guard
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
    if language == Language.PYTHON:
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
    return await execute_with_limits(cmd, input_data, time_limit_sec, memory_limit_bytes)


async def execute_with_limits(
    cmd: list[str], input_data: str, time_limit_sec: float, memory_limit_bytes: int
) -> TestCaseResult:
    r"""Execute a command with resource constraints."""
    start_time = time.time()
    stop_event = asyncio.Event()

    try:
        # Run the command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=lambda: reliability_guard(time_limit_sec, memory_limit_bytes),
        )

        # Start memory monitoring in parallel FIXME: memory monitoring is enabled
        memory_task = asyncio.create_task(monitor_process_memory(process.pid, stop_event))

        # Set a timeout using asyncio
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input_data.encode()),
                timeout=time_limit_sec + 1,  # Give some extra time for process creation
            )

            execution_time = time.time() - start_time  # seconds

            # End memory monitoring and get result
            stop_event.set()
            memory_usage = await memory_task

            status = JudgeStatus.ACCEPTED
            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode != 0:
                if process.returncode == -11:
                    status = JudgeStatus.MEMORY_LIMIT_EXCEEDED
                elif process.returncode == -9:
                    status = JudgeStatus.TIME_LIMIT_EXCEEDED
                elif process.returncode == 1 and "AssertionError" in stderr_str:
                    status = JudgeStatus.WRONG_ANSWER  # FIXME: for fullcode mode
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
            # Kill the process if it timed out
            stop_event.set()
            memory_usage = await memory_task

            try:
                for child in psutil.Process(process.pid).children(recursive=True):
                    child.kill()
                process.kill()
            except Exception as e:
                logger.error(f"Error killing process: {e}")

            return TestCaseResult(
                status=JudgeStatus.TIME_LIMIT_EXCEEDED,
                execution_time=time_limit_sec,  # We report the full time limit
                memory_usage=memory_usage,
                error_message="Time limit exceeded",
            )

    except Exception as e:
        stop_event.set()
        logger.error(f"Execute with limits exception: {str(e)}")
        return TestCaseResult(
            status=JudgeStatus.SYSTEM_ERROR, error_message=f"Execution error: {str(e)}"
        )
