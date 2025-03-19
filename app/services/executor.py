import asyncio
import time

import psutil

from app.core.config import settings
from app.models.schemas import JudgeMode, JudgeStatus, JudgeTestCase, Language
from app.services.utils import reliability_guard
from app.utils.logger import logger


class ExecutionResult:
    def __init__(
        self,
        status: JudgeStatus,
        execution_time: float = 0,
        memory_usage: int = 0,
        output: str = "",
        error: str = "",
    ):
        self.status = status
        self.execution_time = execution_time  # in seconds
        self.memory_usage = memory_usage  # in MB
        self.output = output
        self.error = error


async def monitor_process_memory(pid: int, stop_event: asyncio.Event) -> int:
    """Monitor process memory usage periodically until stop_event is set."""
    max_memory = 0
    try:
        process = psutil.Process(pid)
        while not stop_event.is_set():
            try:
                # Get memory usage in MB (RSS - Resident Set Size)
                memory = process.memory_info().rss // 1024 // 1024
                max_memory = max(max_memory, memory)
                await asyncio.sleep(0.01)  # 10ms interval
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.error(f"Error monitoring memory: {str(e)}")
    return max_memory


async def execute_code(
    executable_path_or_code: str,
    language: Language,
    mode: JudgeMode,
    test_case: JudgeTestCase,
    time_limit_sec: int = settings.MAX_EXECUTION_TIME,
    memory_limit_mb: int = settings.MAX_MEMORY,
) -> ExecutionResult:
    r"""Execute code with specified constraints and return the result."""
    memory_limit_bytes = memory_limit_mb * 1024 * 1024
    cmd = []
    input_data = test_case.input
    if language == Language.PYTHON:
        if mode == JudgeMode.LEETCODE:
            expected = test_case.expected
            executable_path_or_code = executable_path_or_code(
                input_data=f"{input_data=}", expected=f"{expected=}"
            )
            input_data = ""  # FIXME: For LeetCode, input_data is None
        cmd = ["python", "-c", executable_path_or_code]
    else:  # C or C++
        # For compiled languages, use the executable path
        cmd = [executable_path_or_code]
    return await _execute_with_limits(cmd, input_data, time_limit_sec, memory_limit_bytes)


async def _execute_with_limits(
    cmd: list[str], input_data: str, time_limit_sec: float, memory_limit_bytes: int
) -> ExecutionResult:
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

            stdout_str = stdout.decode("utf-8", errors="replace").strip()
            stderr_str = stderr.decode("utf-8", errors="replace").strip()

            if process.returncode != 0:
                if process.returncode == 137:
                    status = JudgeStatus.MEMORY_LIMIT_EXCEEDED
                else:
                    status = JudgeStatus.RUNTIME_ERROR
                stderr_str = f"Process returned code {process.returncode}\n{stderr_str}"
                return ExecutionResult(
                    status=status,
                    execution_time=execution_time,
                    memory_usage=memory_usage,
                    output=stdout_str,
                    error=stderr_str,
                )

            return ExecutionResult(
                status=JudgeStatus.ACCEPTED,  # This will be compared against expected output later
                execution_time=execution_time,
                memory_usage=memory_usage,
                output=stdout_str,
                error=stderr_str,
            )

        except asyncio.TimeoutError:
            # Kill the process if it timed out
            stop_event.set()
            memory_usage = await memory_task

            try:
                process.kill()
            except Exception:
                pass

            return ExecutionResult(
                status=JudgeStatus.TIME_LIMIT_EXCEEDED,
                execution_time=time_limit_sec,  # We report the full time limit
                memory_usage=memory_usage,
                output="",
                error="Time limit exceeded",
            )

    except Exception as e:
        stop_event.set()
        logger.error(f"Execution error: {str(e)}")
        return ExecutionResult(status=JudgeStatus.SYSTEM_ERROR, error=f"Execution error: {str(e)}")
