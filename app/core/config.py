from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Mini Judge"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PREFIX: str = "mini_judge:"

    # Judge settings
    MAX_EXECUTION_TIME: int = 5  # seconds
    MAX_MEMORY: int = 256 * 1024 * 1024  # 256MB
    MAX_PROCESSES: int = 5
    MAX_OUTPUT_SIZE: int = 1024 * 1024  # 1MB

    # Security settings
    ALLOWED_HOSTS: list[str] = ["*"]

    # Code execution
    CODE_EXECUTION_DIR: str = "/tmp/mini_judge"

    model_config = {"env_file": ".env"}


settings = Settings()
