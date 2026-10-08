"""Fixed reviewed backend selection; request values never become import paths."""
from ..common import ForgeError


def adapter(backend):
    if backend == "blender":
        from . import blender
        return blender
    if backend == "freecad":
        from . import freecad
        return freecad
    raise ForgeError("Backend is not in the reviewed allowlist")


def native_artifacts(request):
    if request["backend"] == "blender":
        return ["native/model.blend", "exports/model.stl"]
    if request["backend"] == "freecad":
        return ["native/model.FCStd", "exports/model.step", "exports/model.stl"]
    raise ForgeError("Backend is not in the reviewed allowlist")
