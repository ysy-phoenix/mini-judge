import multiprocessing

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Mini Judge"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PREFIX: str = "mini_judge"
    REDIS_SUBMISSION_QUEUE: str = f"{REDIS_PREFIX}:queue:submissions"
    REDIS_RESULT_QUEUE: str = f"{REDIS_PREFIX}:queue:results"
    REDIS_PROCESSED_COUNT: str = f"{REDIS_PREFIX}:processed_count"
    REDIS_SUBMITTED_COUNT: str = f"{REDIS_PREFIX}:submitted_count"
    REDIS_FETCHED_COUNT: str = f"{REDIS_PREFIX}:fetched_count"

    # Judge settings
    MAX_EXECUTION_TIME: int = 30  # seconds
    MAX_MEMORY: int = 4 * 1024  # MB
    MAX_PROCESSES: int = 4
    MAX_OUTPUT_SIZE: int = 16 * 1024 * 1024  # 16 MB

    # Security settings
    ALLOWED_HOSTS: list[str] = ["*"]
    SECURITY_CHECK: bool = True

    # Code execution
    CODE_EXECUTION_DIR: str = "/tmp/mini_judge"

    # Worker settings
    MAX_WORKERS: int = multiprocessing.cpu_count()
    MAX_LATENCY: int = 180
    MAX_TASK_EXECUTION_TIME: int = 150
    RESULT_EXPIRY_TIME: int = 3600

    # Manager settings
    MONITOR_INTERVAL: int = 10
    RECOVER_INTERVAL: float = 0.2
    CLEANUP_INTERVAL: int = 900

    # Resource limits
    MEMORY_HIGH_THRESHOLD: float = 85.0  # 85% memory utilization
    MEMORY_LOW_THRESHOLD: float = 75.0  # 75% memory utilization
    RESOURCE_CHECK_INTERVAL: int = 1  # seconds

    # Shutdown settings
    SHUTDOWN_TIMEOUT: int = 30  # Maximum seconds to wait for graceful shutdown
    SHUTDOWN_CLEANUP_TIMEOUT: int = 5  # Maximum seconds to wait for cleanup operations
    TASK_COMPLETION_TIMEOUT: int = 10  # Maximum seconds to wait for current task
    SHUTDOWN_SIGNAL_DELAY: float = 0.1  # Delay between shutdown signals

    model_config = {"env_file": ".env"}


settings = Settings()
