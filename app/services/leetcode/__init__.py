import asyncio
import time
from collections.abc import Callable
from typing import Any

import psutil

from app.models.schemas import JudgeStatus, TestCaseResult
from app.services.stdout import check_equal
from app.services.utils import managed_process_execution
from app.utils.logger import logger


async def judge_leetcode(
    fn: Callable, inp: list[Any], out: Any, time_limit_sec: int, memory_limit_bytes: int
) -> TestCaseResult:
    r"""Execute LeetCode style test cases with resource constraints and improved robustness."""
    start_time = time.time()
    memory_usage = 0

    # Use the managed process execution context for better resource monitoring
    async with managed_process_execution(time_limit_sec, memory_limit_bytes) as ctx:
        try:
            # Get current process and set up monitoring
            process = psutil.Process()
            ctx["register_process"](process.pid)
            ctx["start_monitoring"](process.pid)

            # Execute function with timeout
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, fn, *inp), timeout=time_limit_sec
            )

            execution_time = time.time() - start_time

            # Try to get memory usage from monitoring tasks
            stop_event = ctx.get("stop_event")
            if stop_event and not stop_event.is_set():
                # Give a moment for memory monitoring to catch up
                await asyncio.sleep(0.1)

            # Check result correctness
            if not check_equal(result, out):
                error_message = f"Expected:\n{str(out)[:100]}\nActual:\n{str(result)[:100]}"
                return TestCaseResult(
                    status=JudgeStatus.WRONG_ANSWER,
                    execution_time=execution_time,
                    memory_usage=memory_usage,
                    actual_output=str(result),
                    expected_output=str(out),
                    error_message=error_message,
                )

            return TestCaseResult(
                status=JudgeStatus.ACCEPTED,
                execution_time=execution_time,
                memory_usage=memory_usage,
            )

        except asyncio.TimeoutError:
            # Function execution timed out
            return TestCaseResult(
                status=JudgeStatus.TIME_LIMIT_EXCEEDED,
                execution_time=time_limit_sec,
                memory_usage=memory_usage,
                error_message="Time Limit Exceeded",
            )

        except MemoryError:
            # Explicit memory error caught
            return TestCaseResult(
                status=JudgeStatus.MEMORY_LIMIT_EXCEEDED,
                execution_time=time.time() - start_time,
                memory_usage=memory_usage,
                error_message="Memory Limit Exceeded",
            )

        except Exception as e:
            # Any other exception during function execution
            import traceback

            error_trace = traceback.format_exc()
            logger.error(error_trace)

            return TestCaseResult(
                status=JudgeStatus.RUNTIME_ERROR,
                execution_time=time.time() - start_time,
                memory_usage=memory_usage,
                error_message=f"Runtime Error: {str(e)}\n{error_trace[:500]}",
            )
