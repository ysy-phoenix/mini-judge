import asyncio
import uuid

from app.models.schemas import (
    JudgeRequest,
    JudgeResponse,
    JudgeStatus,
    TestCaseResult,
)
from app.services.compiler import compile_code
from app.services.executor import execute_code
from app.utils.logger import (
    log_judge_compile,
    log_judge_execute,
    log_judge_result,
    log_judge_start,
    log_with_context,
)
from app.utils.redis import add_to_queue, get_task, set_task
from app.utils.security import (
    clean_execution_directory,
    create_secure_execution_directory,
    is_code_safe,
)


async def judge_submission(request: JudgeRequest) -> JudgeResponse:
    r"""Judge a code submission. This is the main entry point for the judge service."""
    # Generate a unique task ID
    task_id = str(uuid.uuid4())

    log_judge_start(task_id, request.language.value, request.mode.value)

    # Store task in Redis
    try:
        await set_task(task_id, request.model_dump())
    except Exception as e:
        log_with_context(
            f"Error setting task in Redis: {str(e)}", {"task_id": task_id}, level="error"
        )
        return JudgeResponse(
            status=JudgeStatus.SYSTEM_ERROR, error_message=f"Error setting task in Redis: {str(e)}"
        )

    # Add task to queue
    try:
        await add_to_queue("judge_tasks", task_id)
    except Exception as e:
        log_with_context(
            f"Error adding task to queue: {str(e)}", {"task_id": task_id}, level="error"
        )
        return JudgeResponse(
            status=JudgeStatus.SYSTEM_ERROR, error_message=f"Error adding task to queue: {str(e)}"
        )

    # Return initial response with task ID
    return JudgeResponse(status=JudgeStatus.PENDING, task_id=task_id)


async def process_judge_task(task_id: str) -> JudgeResponse:
    r"""Process a judge task from the queue."""
    # Get task data from Redis
    task_data = await get_task(task_id)
    if not task_data:
        log_with_context("Task not found", {"task_id": task_id}, level="error")
        return JudgeResponse(status=JudgeStatus.SYSTEM_ERROR, error_message="Task not found")

    # Convert to JudgeRequest
    request = JudgeRequest(**task_data)

    # Check if code is safe
    if not is_code_safe(request.code, request.language):
        log_with_context(
            "Code contains potentially unsafe operations", {"task_id": task_id}, level="error"
        )
        return JudgeResponse(
            status=JudgeStatus.SYSTEM_ERROR,
            error_message="Code contains potentially unsafe operations",
        )

    # Create a secure execution directory
    working_dir = create_secure_execution_directory()

    try:
        # Compile code if needed
        executable_path, compile_error = await compile_code(
            request.code, request.language, working_dir
        )

        if compile_error:
            log_judge_compile(task_id, False, compile_error)
            return JudgeResponse(status=JudgeStatus.COMPILATION_ERROR, error_message=compile_error)

        log_judge_compile(task_id, True)

        # all test cases are executed concurrently
        execution_tasks = [
            execute_code(
                executable_path,
                request.language,
                request.mode,
                test_case,
                request.time_limit,
                request.memory_limit,
            )
            for test_case in request.test_cases
        ]

        # Wait for all test cases to be executed
        execution_results = await asyncio.gather(*execution_tasks)

        # Process the execution results
        test_case_results = []
        max_execution_time = 0
        max_memory_usage = 0
        overall_status = JudgeStatus.ACCEPTED
        passed_cases = 0

        # Pair the test cases with the execution results
        for i, (test_case, result) in enumerate(
            zip(request.test_cases, execution_results, strict=False)
        ):
            # Compare the output with expected output
            if result.status == JudgeStatus.ACCEPTED:
                # Normalize output (trim whitespace, etc.)
                normalized_output = _normalize_output(result.output)
                normalized_expected = _normalize_output(test_case.expected)

                if normalized_output != normalized_expected:
                    result.status = JudgeStatus.WRONG_ANSWER
                else:
                    passed_cases += 1

            log_judge_execute(
                task_id, i + 1, result.status.value, result.execution_time, result.memory_usage
            ) if i == 0 else None  # FIXME: only log the first test case result

            # Update stats
            max_execution_time = max(max_execution_time, result.execution_time)
            max_memory_usage = max(max_memory_usage, result.memory_usage)

            # Update overall status (prioritize error states)
            if result.status != JudgeStatus.ACCEPTED:
                # Prioritize errors in a specific order
                status_priority = {
                    JudgeStatus.SYSTEM_ERROR: 1,
                    JudgeStatus.COMPILATION_ERROR: 2,
                    JudgeStatus.RUNTIME_ERROR: 3,
                    JudgeStatus.TIME_LIMIT_EXCEEDED: 4,
                    JudgeStatus.MEMORY_LIMIT_EXCEEDED: 5,
                    JudgeStatus.WRONG_ANSWER: 6,
                    JudgeStatus.ACCEPTED: 7,
                }

                if status_priority.get(result.status, 0) < status_priority.get(overall_status, 7):
                    overall_status = result.status

            # Add the test case result
            test_case_results.append(
                TestCaseResult(
                    status=result.status,
                    execution_time=result.execution_time,
                    memory_usage=result.memory_usage,
                    error_message=result.error if result.error else None,
                    actual_output=result.output,
                )
            )

        log_judge_result(task_id, overall_status.value, len(request.test_cases), passed_cases)

        # Return final response
        return JudgeResponse(
            status=overall_status,
            execution_time=max_execution_time,
            memory_usage=max_memory_usage,
            test_case_results=test_case_results,
            task_id=task_id,
        )

    except Exception as e:
        log_with_context(f"Judge process error: {str(e)}", {"task_id": task_id}, level="error")
        return JudgeResponse(
            status=JudgeStatus.SYSTEM_ERROR, error_message=f"Judge error: {str(e)}"
        )

    finally:
        # Clean up execution directory
        clean_execution_directory(working_dir)


def _normalize_output(output: str) -> str:
    r"""Normalize output for comparison.
    - Trim leading/trailing whitespace
    - Normalize line endings
    - Remove empty lines
    """
    lines = output.strip().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.strip() for line in lines if line.strip())
