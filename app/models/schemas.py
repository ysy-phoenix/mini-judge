import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Language(str, Enum):
    PYTHON = "python"
    CPP = "cpp"
    C = "c"


class JudgeMode(str, Enum):
    LEETCODE = "leetcode"
    ACM = "acm"
    FULLCODE = "fullcode"
    EXECUTION = "execution"


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
    input: str | list[Any]
    expected: Any


def generate_uuid():
    return str(uuid.uuid4())


class Submission(BaseModel):
    code: str = Field(..., description="Source code to be judged")
    language: Language
    mode: JudgeMode
    test_cases: list[JudgeTestCase]
    time_limit: int | None = 1  # seconds
    memory_limit: int | None = 256  # MB
    task_id: str | None = Field(default_factory=generate_uuid)
    entry_point: str | None = None
    security_check: bool = True


class TestCaseResult(BaseModel):
    status: JudgeStatus
    execution_time: float | None = None  # seconds
    memory_usage: int | None = None  # MB
    error_message: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None


class JudgeResult(BaseModel):
    status: JudgeStatus
    execution_time: float | None = None  # seconds
    memory_usage: int | None = None  # MB
    error_message: str | None = None
    test_case_results: list[TestCaseResult] | None = None
    task_id: str | None = None
    metadata: dict[str, Any] | None = None
