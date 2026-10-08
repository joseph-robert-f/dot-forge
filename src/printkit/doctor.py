"""Linux read-only discovery; explicit smoke executes a reviewed workflow."""
from pathlib import Path
import os
import platform
import shutil
import sys
import tempfile
from .common import ForgeError
from .adapters import blender, freecad

def doctor(smoke=None, backend="blender"):
    if backend not in ("blender", "freecad"):
        raise ForgeError("Unsupported backend")
    with tempfile.TemporaryDirectory(prefix="printkit-doctor-") as directory:
        path=Path(directory)/"probe"
        path.write_text("ok")
        writable=path.read_text()=="ok"
    report={"schema_version":"1", "selected_backend":backend,
            "python":platform.python_version(), "python_compatible":sys.version_info>=(3,11),
            "platform":{"system":platform.system(),"architecture":platform.machine()},
            "resources":{"available_cpu_count":os.cpu_count(),"scratch_free_bytes":shutil.disk_usage(tempfile.gettempdir()).free,
                         "available_memory_bytes":None,"scratch_writable":writable},
            "blender":blender.discover(), "freecad":freecad.discover(),
            "security":{"sandbox":False,"reviewed_generators_only":True},
            "full_architecture_mvp":"blocked: Lane A runtime acceptance remains outstanding",
            "print_readiness":"never established by doctor"}
    if smoke:
        from .orchestrator import run_all
        is_cad=backend=="freecad"
        request={"schema_version":"1","generator_id":"freecad-stepped-block" if is_cad else "calibration-block",
          "generator_version":"1","backend":backend,
          "units":"mm","parameters":{"width_mm":20,"depth_mm":20,"height_mm":10},"dimensions_mm":[20,20,10],
          "tolerance_mm":0.05,"allowed_components":1,"part_count":1,
          "export_formats":["stl","fcstd","step"] if is_cad else ["stl","blend"],
          "render_profile":"five-view","validation_profile":"solid-single-part","printer_profile":None}
        result=run_all(request,smoke)
        passed=result["geometry_state"]=="geometry_validated"
        report[backend]["smoke_status"]="pass" if passed else "fail"
        report[backend][request["generator_id"]]="available" if passed else "incompatible"
        report[backend]["status"]="available" if passed else "incompatible"
        report["smoke_geometry_state"]=result["geometry_state"]
    return report
