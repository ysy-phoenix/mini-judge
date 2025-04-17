import asyncio
import time
from collections.abc import Callable
from typing import Any

import psutil

from app.core.config import settings
from app.models.schemas import JudgeStatus, TestCaseResult
from app.services.stdout import check_equal
from app.services.utils import monitor_process_memory
from app.utils.logger import logger


async def judge_leetcode(
    fn: Callable, inp: list[Any], out: Any, time_limit_sec: int, memory_limit_bytes: int
) -> TestCaseResult:
    r"""Execute LeetCode style test cases with resource constraints."""
    # Create event for memory monitoring
    stop_event = asyncio.Event()

    try:
        # Start memory monitoring in background
        process = psutil.Process()
        memory_task = asyncio.create_task(monitor_process_memory(process.pid, stop_event))

        # Execute function with timeout
        start_time = time.time()
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, fn, *inp), timeout=time_limit_sec + 1
        )
        execution_time = time.time() - start_time

        # Stop memory monitoring
        stop_event.set()
        memory_usage = await memory_task

        # Check memory limit
        if memory_usage > memory_limit_bytes:
            return TestCaseResult(
                status=JudgeStatus.MEMORY_LIMIT_EXCEEDED,
                execution_time=execution_time,
                memory_usage=memory_usage,
                error_message=f"Memory limit exceeded: {memory_usage}MB used",
            )

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
            status=JudgeStatus.ACCEPTED, execution_time=execution_time, memory_usage=memory_usage
        )

    except asyncio.TimeoutError:
        stop_event.set()
        memory_usage = await memory_task
        return TestCaseResult(
            status=JudgeStatus.TIME_LIMIT_EXCEEDED,
            execution_time=settings.MAX_EXECUTION_TIME,
            memory_usage=memory_usage if memory_usage else 0,
            error_message="Time Limit Exceeded",
        )
    except Exception as e:
        stop_event.set()
        memory_usage = await memory_task
        import traceback

        logger.error(traceback.format_exc())
        return TestCaseResult(
            status=JudgeStatus.RUNTIME_ERROR,
            execution_time=0,
            memory_usage=memory_usage if memory_usage else 0,
            error_message=f"Runtime Error: {str(e)}",
        )
