import asyncio

from app.models.schemas import (
    JudgeResult,
    JudgeStatus,
    Language,
    Submission,
    TestCaseResult,
)
from app.services.compiler import compile_code
from app.services.executor import execute_code
from app.utils.logger import logger
from app.utils.security import (
    clean_execution_directory,
    create_secure_execution_directory,
    is_code_safe,
)

STATUS_PRIORITY = {
    JudgeStatus.SYSTEM_ERROR: 1,
    JudgeStatus.COMPILATION_ERROR: 2,
    JudgeStatus.RUNTIME_ERROR: 3,
    JudgeStatus.TIME_LIMIT_EXCEEDED: 4,
    JudgeStatus.MEMORY_LIMIT_EXCEEDED: 5,
    JudgeStatus.WRONG_ANSWER: 6,
    JudgeStatus.ACCEPTED: 7,
}
MAX_TEST_CASE_RESULTS = 3


def truncate_output(output: str, max_length: int = 256) -> str:
    if len(output) <= max_length:
        return output
    else:
        return output[: max_length // 2] + "[... truncated ...]" + output[-max_length // 2 :]


async def process_judge_task(submission: Submission) -> JudgeResult:
    r"""Process a judging task directly, without fetching data from Redis"""
    if not is_code_safe(submission.code, submission.language):
        logger.error(
            f"Code contains potentially unsafe operations: [red]{submission.task_id}[/red]"
        )
        return JudgeResult(
            status=JudgeStatus.SYSTEM_ERROR,
            error_message="Code contains potentially unsafe operations",
        )

    working_dir = None
    if submission.language in [Language.C, Language.CPP]:
        working_dir = create_secure_execution_directory()

    try:
        executable_path_or_code, compile_error = await compile_code(
            submission.code, submission.language, working_dir
        )
        if compile_error:
            logger.error(
                f"Compilation error: [red]{submission.task_id}[/red] | [red]{compile_error}[/red]"
            )
            return JudgeResult(status=JudgeStatus.COMPILATION_ERROR, error_message=compile_error)

        # all test cases are executed concurrently
        execution_tasks = [
            execute_code(
                executable_path_or_code,
                submission.language,
                submission.mode,
                test_case,
                submission.time_limit,
                submission.memory_limit,
            )
            for test_case in submission.test_cases
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
        for _, (test_case, result) in enumerate(
            zip(submission.test_cases, execution_results, strict=False)
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

            # Update stats
            max_execution_time = max(max_execution_time, result.execution_time)
            max_memory_usage = max(max_memory_usage, result.memory_usage)

            # Update overall status (prioritize error states)
            if result.status != JudgeStatus.ACCEPTED:
                # Prioritize errors in a specific order
                if STATUS_PRIORITY.get(result.status, 0) < STATUS_PRIORITY.get(overall_status, 7):
                    overall_status = result.status

            # FIXME: Add 3 false test case results
            if (
                result.status != JudgeStatus.ACCEPTED
                and len(test_case_results) < MAX_TEST_CASE_RESULTS
            ):
                test_case_results.append(
                    TestCaseResult(
                        status=result.status,
                        execution_time=result.execution_time,
                        memory_usage=result.memory_usage,
                        error_message=truncate_output(result.error) if result.error else None,
                        expected_output=truncate_output(test_case.expected),
                        actual_output=truncate_output(result.output),
                    )
                )

        status_color = "green" if overall_status == JudgeStatus.ACCEPTED else "red"
        logger.info(
            f"[cyan] Results of submission {submission.task_id.split('-')[0]}: [/cyan]"
            f"[bold {status_color}]{overall_status.value}[/bold {status_color}]\t"
            f"[magenta]Passed {passed_cases}/{len(submission.test_cases)} cases[/magenta]"
        )

        # Return final response
        return JudgeResult(
            status=overall_status,
            execution_time=max_execution_time,
            memory_usage=max_memory_usage,
            test_case_results=test_case_results,
            task_id=submission.task_id,
        )

    except Exception as e:
        logger.error(f"Judge process error: [red]{submission.task_id}[/red] | [red]{str(e)}[/red]")
        return JudgeResult(status=JudgeStatus.SYSTEM_ERROR, error_message=f"Judge error: {str(e)}")

    finally:
        # Clean up execution directory only if it was created
        if working_dir:
            clean_execution_directory(working_dir)


def _normalize_output(output: str) -> str:
    r"""Normalize output for comparison.
    - Trim leading/trailing whitespace
    - Normalize line endings
    - Remove empty lines
    """
    # First remove trailing newlines explicitly
    while output.endswith("\n"):
        output = output[:-1]
    lines = output.strip().replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.strip() for line in lines if line.strip())
