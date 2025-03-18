from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    PYTHON = "python"
    CPP = "cpp"
    C = "c"


class JudgeMode(str, Enum):
    LEETCODE = "leetcode"
    ACM = "acm"


class JudgeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    SYSTEM_ERROR = "system_error"


class JudgeTestCase(BaseModel):
    input: str
    expected: str


class JudgeRequest(BaseModel):
    code: str = Field(..., description="Source code to be judged")
    language: Language
    mode: JudgeMode
    test_cases: list[JudgeTestCase]
    time_limit: int | None = 1  # seconds
    memory_limit: int | None = 256  # MB


class TestCaseResult(BaseModel):
    status: JudgeStatus
    execution_time: float | None = None  # ms
    memory_usage: int | None = None  # KB
    error_message: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None


class JudgeResponse(BaseModel):
    status: JudgeStatus
    execution_time: float | None = None  # ms
    memory_usage: int | None = None  # KB
    error_message: str | None = None
    test_case_results: list[TestCaseResult] | None = None
    task_id: str | None = None  # for async tasks
