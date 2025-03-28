import asyncio
import time

from app.core.config import settings
from app.models.schemas import (
    JudgeMode,
    JudgeResult,
    JudgeStatus,
    Submission,
    TestCaseResult,
)
from app.services.compiler import compile_code
from app.services.executor import execute_code
from app.services.utils import (
    MAX_TEST_CASE_RESULTS,
    STATUS_PRIORITY,
    normalize_output,
    truncate_output,
)
from app.utils.logger import logger
from app.utils.security import (
    clean_execution_directory,
    create_secure_execution_directory,
    is_code_safe,
)


async def process_judge_task(submission: Submission) -> JudgeResult:
    r"""Process a judging task directly, without fetching data from Redis"""
    if settings.SECURITY_CHECK and not is_code_safe(submission.code, submission.language):
        logger.error(
            f"Code contains potentially unsafe operations: [red]{submission.task_id}[/red]"
        )
        return JudgeResult(
            status=JudgeStatus.SYSTEM_ERROR,
            error_message="Code contains potentially unsafe operations",
        )

    working_dir = create_secure_execution_directory()

    try:
        executable_path_or_code, compile_error = await compile_code(
            submission.code,
            submission.mode,
            submission.language,
            working_dir,
            submission.entry_point,
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
        start_time = time.time()
        execution_results = await asyncio.gather(*execution_tasks)
        end_time = time.time()
        execution_time = end_time - start_time

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
                if submission.mode == JudgeMode.ACM:
                    normalized_output = normalize_output(result.actual_output)
                    normalized_expected = normalize_output(test_case.expected)
                    result.error_message = (
                        f"Expected:\n{normalized_expected[:100]}\n"
                        f"Actual:\n{normalized_output[:100]}"
                    )

                    if normalized_output != normalized_expected:
                        result.status = JudgeStatus.WRONG_ANSWER
                    else:
                        passed_cases += 1
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
                        error_message=truncate_output(result.error_message)
                        if result.error_message
                        else None,
                        expected_output=truncate_output(str(test_case.expected)),
                        actual_output=truncate_output(result.actual_output)
                        if result.actual_output
                        else None,
                    )
                )

        error_message = None
        if overall_status != JudgeStatus.ACCEPTED:
            error_message = test_case_results[0].error_message
        status_color = "green" if overall_status == JudgeStatus.ACCEPTED else "red"
        logger.info(
            f"[cyan] Submission {submission.task_id.split('-')[0]}: [/cyan]"
            f"[bold {status_color}]{overall_status.value}[/bold {status_color}] | "
            f"[magenta]Passed {passed_cases}/{len(submission.test_cases)} cases[/magenta] | "
            f"[yellow]Total time: {execution_time:.2f} seconds[/yellow]"
        )
        if error_message is not None:
            logger.error(f"Error message: {error_message}")

        # Return final response
        return JudgeResult(
            status=overall_status,
            execution_time=max_execution_time,
            memory_usage=max_memory_usage,
            test_case_results=test_case_results,
            task_id=submission.task_id,
            error_message=error_message,
            metadata={
                "passed": passed_cases,
                "total": len(submission.test_cases),
            },
        )

    except Exception as e:
        import traceback

        logger.error(
            f"Judge process error: [red]{submission.task_id.split('-')[0]}[/red] |"
            f" [red]{str(e)}[/red]"
        )
        logger.error(traceback.format_exc())
        return JudgeResult(status=JudgeStatus.SYSTEM_ERROR, error_message=f"Judge error: {str(e)}")

    finally:
        # Clean up execution directory only if it was created
        if working_dir:
            clean_execution_directory(working_dir)
