"""Hard process budget around trusted independent geometry validation.

Resource containment only: this subprocess is not a security sandbox.
"""
import multiprocessing
import os
import resource
import signal
from .common import ForgeError


def _worker(connection, mesh, request):
    try:
        os.setsid()
        resource.setrlimit(resource.RLIMIT_AS, (536870912, 536870912))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        from .validation import validate_mesh
        result = validate_mesh(mesh, request)
        connection.send((True, result))
    except BaseException as exc:
        connection.send((False, {"type": type(exc).__name__, "message": str(exc)}))
    finally:
        connection.close()


def validate_bounded(mesh, request, timeout=35):
    # The tested runtime profile is Linux. Fork avoids third-party package/startup
    # imports while launching the already reviewed validator implementation.
    context = multiprocessing.get_context("fork")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(sender, str(mesh), request))
    process.start()
    sender.close()
    try:
        if not receiver.poll(timeout):
            raise ForgeError("Independent validator exceeded hard deadline", 4, "validator_timeout")
        try:
            success, result = receiver.recv()
        except EOFError as exc:
            raise ForgeError("Independent validator crashed without a report", 4, "validator_crash") from exc
        if not success:
            raise ForgeError("Independent validator failed: " + result["type"], 4, "validator_crash")
        return result
    finally:
        receiver.close()
        if process.is_alive():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                process.kill()
        process.join()
