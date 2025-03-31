import psutil

from app.core.config import settings
from app.utils.logger import logger


class ResourceMonitor:
    """Monitor system resources and provide throttling decisions."""

    @staticmethod
    def get_cpu_usage() -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=0.1)

    @staticmethod
    def get_memory_usage() -> float:
        """Get current memory usage percentage."""
        return psutil.virtual_memory().percent

    @staticmethod
    def should_throttle() -> bool:
        """Check if the system should throttle new tasks."""
        memory_usage = ResourceMonitor.get_memory_usage()

        should_throttle = memory_usage > settings.MEMORY_HIGH_THRESHOLD

        if should_throttle:
            logger.warning(
                f"System resource threshold exceeded - Memory: {memory_usage:.1f}% "
                f"(threshold: {settings.MEMORY_HIGH_THRESHOLD}%)"
            )

        return should_throttle

    @staticmethod
    def can_resume() -> bool:
        """Check if the system can resume processing tasks."""
        memory_usage = ResourceMonitor.get_memory_usage()

        # Only resume when both CPU and memory are below the low thresholds
        can_resume = memory_usage < settings.MEMORY_LOW_THRESHOLD

        if can_resume:
            logger.info(
                f"System resources back to normal - Memory: {memory_usage:.1f}% "
                f"(threshold: {settings.MEMORY_LOW_THRESHOLD}%)"
            )

        return can_resume
