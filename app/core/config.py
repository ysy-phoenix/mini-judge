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

    model_config = {"env_file": ".env"}


settings = Settings()
