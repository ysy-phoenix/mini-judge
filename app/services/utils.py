import asyncio
import faulthandler
import os
import resource
import signal
from contextlib import asynccontextmanager

import psutil

from app.core.config import settings
from app.models.schemas import JudgeStatus
from app.utils.logger import logger

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

_process_groups: dict[int, int] = {}


def truncate_output(output: str, max_length: int = 256) -> str:
    if output is None:
        return None
    if len(output) <= max_length:
        return output
    else:
        return output[: max_length // 2] + "[... truncated ...]" + output[-max_length // 2 :]


async def monitor_process_memory(pid: int, stop_event: asyncio.Event) -> int:
    r"""Monitor process memory usage periodically until stop_event is set."""
    max_memory = 0
    try:
        process = psutil.Process(pid)
        while not stop_event.is_set():
            try:
                # Get memory usage in MB (RSS - Resident Set Size)
                memory = process.memory_info().rss // 1024 // 1024
                max_memory = max(max_memory, memory)
                await asyncio.sleep(0.01)  # 10ms interval
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.error(f"Error monitoring memory: {str(e)}")
    return max_memory


def reliability_guard(time_limit_sec: float, memory_limit_bytes: int):
    r"""Set resource limits for the subprocess."""
    # Set CPU time limit (add a small buffer)
    resource.setrlimit(resource.RLIMIT_CPU, (int(time_limit_sec) + 1, int(time_limit_sec) + 1))

    # Set memory limit
    resource.setrlimit(resource.RLIMIT_DATA, (memory_limit_bytes, memory_limit_bytes))
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))

    # Limit number of processes/threads
    resource.setrlimit(resource.RLIMIT_NPROC, (settings.MAX_PROCESSES, settings.MAX_PROCESSES))

    # Prevent any file creation
    resource.setrlimit(resource.RLIMIT_FSIZE, (settings.MAX_OUTPUT_SIZE, settings.MAX_OUTPUT_SIZE))

    faulthandler.disable()

    import builtins

    builtins.exit = None
    builtins.quit = None

    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["GOTO_NUM_THREADS"] = "1"

    os.kill = None
    os.system = None
    os.putenv = None
    os.remove = None
    os.removedirs = None
    os.rmdir = None
    os.fchdir = None
    os.setuid = None
    os.fork = None
    os.forkpty = None
    os.killpg = None
    os.rename = None
    os.renames = None
    os.truncate = None
    os.replace = None
    os.unlink = None
    os.fchmod = None
    os.fchown = None
    os.chmod = None
    os.chown = None
    os.chroot = None
    os.fchdir = None
    os.lchflags = None
    os.lchmod = None
    os.lchown = None
    os.getcwd = None
    os.chdir = None
    builtins.open = None

    import shutil

    shutil.rmtree = None
    shutil.move = None
    shutil.chown = None

    import subprocess

    subprocess.Popen = None  # type: ignore

    __builtins__["help"] = None

    import sys

    sys.modules["ipdb"] = None
    sys.modules["joblib"] = None
    sys.modules["resource"] = None
    sys.modules["psutil"] = None
    sys.modules["tkinter"] = None


async def enforce_memory_limit(
    pid: int, memory_limit_bytes: int, stop_event: asyncio.Event
) -> None:
    warning_threshold = 0.85
    kill_threshold = 0.95

    try:
        process = psutil.Process(pid)
        while not stop_event.is_set():
            try:
                memory_info = process.memory_info().rss
                if memory_info > memory_limit_bytes * kill_threshold:
                    ratio = memory_info / memory_limit_bytes
                    logger.warning(
                        f"Process {pid} reached {ratio:.1%} of memory limit, terminating"
                    )
                    await cleanup_process(pid)
                    break
                elif memory_info > memory_limit_bytes * warning_threshold:
                    ratio = memory_info / memory_limit_bytes
                    logger.warning(f"Process {pid} approaching memory limit ({ratio:.1%})")
                await asyncio.sleep(0.05)
            except psutil.NoSuchProcess:
                break
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.error(f"Memory enforcement error for PID {pid}: {str(e)}")


async def cleanup_process(pid: int) -> None:
    try:
        # Try process group termination first if available
        pgid = _process_groups.get(pid)

        if pgid:
            try:
                # Try to terminate the entire process group
                os.killpg(pgid, signal.SIGKILL)
                logger.debug(f"Killed process group {pgid}")
            except (ProcessLookupError, PermissionError, OSError) as e:
                # Process group kill might fail, fall back to individual process kill
                logger.debug(f"Process group termination failed: {e}")

        # Always try direct process termination as backup
        try:
            process = psutil.Process(pid)

            # First terminate children (bottom-up cleanup)
            children = process.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                    logger.debug(f"Killed child process {child.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Then terminate the main process
            process.kill()
            logger.debug(f"Killed main process {pid}")

        except psutil.NoSuchProcess:
            # Process already gone
            pass
        except psutil.AccessDenied:
            # Try with os.kill as last resort
            try:
                os.kill(pid, signal.SIGKILL)
                logger.debug(f"Killed process {pid} with os.kill")
            except (ProcessLookupError, PermissionError):
                pass

        # Clean up tracking dictionary
        if pid in _process_groups:
            del _process_groups[pid]

    except Exception as e:
        logger.error(f"Process cleanup error for PID {pid}: {str(e)}")


def create_process_group() -> int:
    return os.getpid()


def setup_process_group(pgid: int) -> None:
    try:
        # Create a new process group with this process as leader
        os.setpgid(0, 0)  # Use 0 to create a new group with PID as PGID
    except OSError as e:
        # This is expected in certain environments (Docker, etc.)
        # Log but continue with other isolation mechanisms
        logger.debug(f"Could not create process group: {e}")


def child_process_setup(time_limit_sec: float, memory_limit_bytes: int, pgid: int) -> None:
    # Try to set up process group (may fail in some environments)
    setup_process_group(pgid)

    # Apply resource limits (should work in most environments)
    reliability_guard(time_limit_sec, memory_limit_bytes)


@asynccontextmanager
async def managed_process_execution(time_limit_sec: float, memory_limit_bytes: int):
    stop_event = asyncio.Event()
    pgid = create_process_group()
    process_id = None
    monitoring_tasks = []

    execution_context = {
        "pgid": pgid,
        "stop_event": stop_event,
        "register_process": lambda pid: register_process(pid, pgid),
        "setup_child_process": lambda: child_process_setup(
            time_limit_sec, memory_limit_bytes, pgid
        ),
        "start_monitoring": lambda pid: start_monitoring(
            pid, memory_limit_bytes, stop_event, monitoring_tasks
        ),
    }

    try:
        yield execution_context

    finally:
        stop_event.set()

        if monitoring_tasks:
            await asyncio.gather(*monitoring_tasks, return_exceptions=True)

        if process_id:
            await cleanup_process(process_id)


def register_process(pid: int, pgid: int) -> None:
    _process_groups[pid] = pgid


def start_monitoring(
    pid: int, memory_limit_bytes: int, stop_event: asyncio.Event, tasks_list: list[asyncio.Task]
) -> None:
    memory_task = asyncio.create_task(monitor_process_memory(pid, stop_event))
    tasks_list.append(memory_task)
    enforce_task = asyncio.create_task(enforce_memory_limit(pid, memory_limit_bytes, stop_event))
    tasks_list.append(enforce_task)
