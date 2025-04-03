import asyncio
import functools
import traceback
from typing import Any, TypeVar

from app.utils.logger import logger

T = TypeVar("T")
R = TypeVar("R")


def with_error_handling(
    default_return: Any = None,
    error_message: str = "Operation failed",
    log_traceback: bool = True,
    retry_count: int = 0,
    retry_delay: float = 1.0,
):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            remaining_retries = retry_count

            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if log_traceback:
                        logger.error(f"{error_message}: {str(e)}\n{traceback.format_exc()}")
                    else:
                        logger.error(f"{error_message}: {str(e)}")

                    if remaining_retries > 0:
                        remaining_retries -= 1
                        logger.info(
                            f"Retrying {func.__name__}"
                            f"({retry_count - remaining_retries}/{retry_count})..."
                        )
                        import asyncio

                        await asyncio.sleep(retry_delay)
                    else:
                        break

            # All retries failed
            return default_return

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            remaining_retries = retry_count

            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if log_traceback:
                        logger.error(f"{error_message}: {str(e)}\n{traceback.format_exc()}")
                    else:
                        logger.error(f"{error_message}: {str(e)}")

                    if remaining_retries > 0:
                        remaining_retries -= 1
                        logger.info(
                            f"Retrying {func.__name__}"
                            f"({retry_count - remaining_retries}/{retry_count})..."
                        )
                        import time

                        time.sleep(retry_delay)
                    else:
                        break

            # All retries failed
            return default_return

        # Choose the correct wrapper based on the function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
