import asyncio
import resource
import time

import psutil

from app.core.config import settings
from app.models.schemas import JudgeMode, JudgeStatus, JudgeTestCase, Language
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
        self.execution_time = execution_time  # in milliseconds
        self.memory_usage = memory_usage  # in KB
        self.output = output
        self.error = error


async def monitor_process_memory(pid: int, stop_event: asyncio.Event) -> int:
    """Monitor process memory usage periodically until stop_event is set."""
    max_memory = 0
    try:
        process = psutil.Process(pid)
        while not stop_event.is_set():
            try:
                # Get memory usage in KB (RSS - Resident Set Size)
                memory = process.memory_info().rss // 1024
                max_memory = max(max_memory, memory)
                await asyncio.sleep(0.01)  # 10ms interval
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
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

    if language == Language.PYTHON:
        # Pass code directly using -c flag
        cmd = ["python", "-c", executable_path_or_code]
    else:  # C or C++
        # For compiled languages, use the executable path
        cmd = [executable_path_or_code]

    return await _execute_with_limits(cmd, test_case.input, time_limit_sec, memory_limit_bytes)


async def _execute_with_limits(
    cmd: list[str], input_data: str, time_limit_sec: float, memory_limit_bytes: int
) -> ExecutionResult:
    r"""Execute a command with resource constraints."""

    # Define the resource limit function for the subprocess
    def set_limits():
        # Set CPU time limit (add a small buffer)
        resource.setrlimit(resource.RLIMIT_CPU, (int(time_limit_sec) + 1, int(time_limit_sec) + 1))

        # Set memory limit
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))

        # Limit number of processes/threads
        resource.setrlimit(resource.RLIMIT_NPROC, (settings.MAX_PROCESSES, settings.MAX_PROCESSES))

        # Prevent any file creation
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (settings.MAX_OUTPUT_SIZE, settings.MAX_OUTPUT_SIZE)
        )

    start_time = time.time()
    stop_event = asyncio.Event()

    try:
        # Run the command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=set_limits,
        )

        # pid = process.pid

        # Start memory monitoring in parallel FIXME: memory monitoring is dsiabled
        # memory_task = asyncio.create_task(monitor_process_memory(pid, stop_event))

        # Set a timeout using asyncio
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input_data.encode()),
                timeout=time_limit_sec + 1,  # Give some extra time for process creation
            )

            execution_time = (time.time() - start_time) * 1000  # Convert to ms

            # End memory monitoring and get result
            stop_event.set()
            memory_usage = 0  # FIXME: memory monitoring is dsiabled

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            if process.returncode != 0:
                return ExecutionResult(
                    status=JudgeStatus.RUNTIME_ERROR,
                    execution_time=execution_time,
                    memory_usage=memory_usage,
                    output=stderr_str,  # Use stdout for error output
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
            memory_usage = 0  # FIXME: memory monitoring is dsiabled

            try:
                process.kill()
            except Exception:
                pass

            return ExecutionResult(
                status=JudgeStatus.TIME_LIMIT_EXCEEDED,
                execution_time=time_limit_sec * 1000,  # We report the full time limit
                memory_usage=memory_usage,
                output="",
                error="Time limit exceeded",
            )

    except Exception as e:
        stop_event.set()
        return ExecutionResult(status=JudgeStatus.SYSTEM_ERROR, error=f"Execution error: {str(e)}")
