"""Bounded reviewed-code subprocesses. This is explicitly not a sandbox."""
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
from .common import ForgeError

DEFAULT_BUDGET = {"wall_seconds": 600, "memory_bytes": 4294967296,
                  "output_bytes": 536870912, "threads": 2, "max_triangles": 10000}

def output_size(path):
    total = 0
    for file in Path(path).rglob("*"):
        if file.is_symlink():
            raise ForgeError("Output contains a symlink", 4, "unsafe_artifact_path")
        if file.is_file():
            total += file.stat().st_size
    return total

def run_process(argv, cwd, log_path, *, timeout=600, memory_bytes=4294967296, threads=2, env_extra=None, output_bytes=536870912):
    """Run a trusted fixed argv; preserve log, kill process group on timeout.

    RLIMIT_AS and RLIMIT_FSIZE are per process, not process-tree aggregate limits.
    Total directory size is polled. No network or filesystem isolation is claimed.
    """
    cwd = Path(cwd).resolve()
    cwd.mkdir(parents=True, exist_ok=True)
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(cwd), "TMPDIR": str(cwd),
           "LANG": "C.UTF-8", "OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads),
           "PYTHONNOUSERSITE": "1"}
    if env_extra:
        allowed = {"PYTHONPATH", "BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS", "BLENDER_USER_DATAFILES", "HBCB_BLENDER_BINARY"}
        if set(env_extra) - allowed:
            raise ForgeError("Unsupported child environment variable")
        env.update(env_extra)
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with log_path.open("wb") as log:
        try:
            child = subprocess.Popen([str(x) for x in argv], cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                     env=env, start_new_session=True, preexec_fn=limits)
        except OSError as exc:
            raise ForgeError(f"Runtime could not start: {exc}", 3, "runtime_unavailable") from exc
        try:
            while child.poll() is None:
                if time.monotonic() - started > timeout:
                    raise ForgeError("Execution exceeded wall-time budget", 6, "execution_timeout")
                if output_size(cwd) > output_bytes:
                    raise ForgeError("Execution exceeded output budget", 4, "output_budget")
                time.sleep(0.1)
            if output_size(cwd) > output_bytes:
                raise ForgeError("Execution exceeded output budget", 4, "output_budget")
        finally:
            # Kill any descendants left in this process group, even after parent exit.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    metrics = {"wall_seconds": time.monotonic() - started,
               "cpu_seconds": (after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime),
               "peak_rss_bytes": None, "peak_rss_scope": "unavailable: cumulative child high-water mark cannot isolate this run",
               "cpu_scope": "waited-for child processes; descendant accounting is OS-dependent",
               "exit_code": child.returncode,
               "controls": {"process_group_timeout": True, "sanitized_environment": True,
                            "per_process_address_space_limit": memory_bytes, "thread_environment_limit": threads,
                            "network_isolation": False, "filesystem_isolation": False,
                            "aggregate_process_tree_memory_limit": False, "process_count_limit": False}}
    if child.returncode:
        raise ForgeError(f"Runtime exited {child.returncode}; see retained stage log", 3, "runtime_failed")
    return metrics
