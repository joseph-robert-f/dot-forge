"""Bounded native FreeCAD solid adapter. No GUI, downloads, or request code.

This tested distro profile uses the native FreeCAD Python modules through system
Python: the installed freecadcmd launcher is not required and is not invoked.
"""
from pathlib import Path
import math
import os
import platform
import tempfile
from .base import AdapterError, RuntimeUnavailable
from ..common import ForgeError, load_json, write_json, sha256, safe_file
from ..execution import run_process

SCRIPT = Path(__file__).with_name('freecad_scene.py')
PYTHON = Path('/usr/bin/python3')
MODULE = Path('/usr/lib/freecad/lib/FreeCAD.so')
GENERATOR = 'freecad-stepped-block'
NATIVE_LIBRARIES = ('FreeCAD.so', 'Part.so', 'MeshPart.so', 'libFreeCADApp.so', 'libFreeCADBase.so')


def _run(mode, run):
    return run_process([PYTHON, '-I', '-B', SCRIPT, mode, run], run,
                       Path(run) / 'logs' / f'freecad-{mode}.log', timeout=120)


def discover():
    report = {'backend': 'freecad', 'status': 'unavailable', 'smoke_status': 'not_run',
              GENERATOR: 'unavailable', 'runtime_kind': 'system-python-native-freecad'}
    try:
        if not PYTHON.is_file() or not os.access(PYTHON, os.X_OK) or not MODULE.is_file():
            raise RuntimeUnavailable('Installed system Python/FreeCAD modules unavailable; no runtime was downloaded')
        with tempfile.TemporaryDirectory(prefix='printkit-freecad-discover-') as temporary:
            run = Path(temporary)
            _run('discover', run)
            native = load_json(run / 'runtime.json')
        supported = (native['version'] == '1.0.0' and native['occ_version'] == '7.8.1'
                     and platform.system() == 'Linux' and platform.machine() == 'x86_64')
        report.update(version=native['version'], occ_version=native['occ_version'],
                      python_version=native['python_version'], executable=PYTHON.name,
                      binary_sha256=sha256(PYTHON), native_module_sha256=sha256(MODULE),
                      native_library_sha256={name: sha256(MODULE.parent / name) for name in NATIVE_LIBRARIES},
                      status='unverified' if supported else 'incompatible')
        report[GENERATOR] = report['status']
        if not supported:
            report['reason'] = 'Requires tested Linux x86_64 FreeCAD 1.0.0 / OCC 7.8.1 native profile'
    except (ForgeError, OSError, KeyError, ValueError) as exc:
        report['reason'] = str(exc)
    return report


def _check(request):
    if not isinstance(request, dict):
        raise AdapterError('FreeCAD request must be an object')
    if request.get('generator_id') != GENERATOR or request.get('backend') != 'freecad':
        raise AdapterError('Unknown reviewed FreeCAD generator/backend')
    params = request.get('parameters')
    keys = ('width_mm', 'depth_mm', 'height_mm')
    if not isinstance(params, dict) or set(params) != set(keys):
        raise AdapterError('FreeCAD requires width_mm/depth_mm/height_mm only')
    if any(type(params[k]) not in (int, float) or not 5 <= params[k] <= 100 or not math.isfinite(params[k]) for k in keys):
        raise AdapterError('FreeCAD dimensions must be finite numbers within 5–100 mm')


def generate(request, run_dir):
    _check(request)
    supplied = Path(run_dir).absolute()
    if any(path.is_symlink() for path in (supplied, *supplied.parents)):
        raise AdapterError('Symlink run directory is not supported')
    run = supplied.resolve()
    run.mkdir(parents=True, exist_ok=True)
    # Reject stale evidence, unsafe paths and prior exports before any execution.
    outputs = ('native/model.FCStd', 'exports/model.step', 'exports/model.stl',
               'native/generation.json', 'native/reopen.json')
    for name in ('logs/freecad-generate.log', 'logs/freecad-reopen.log'):
        if safe_file(run, name).exists():
            raise AdapterError('Refusing to overwrite existing FreeCAD logs')
    for name in outputs:
        if safe_file(run, name).exists():
            raise AdapterError('Refusing to overwrite existing FreeCAD artifacts or evidence')
    request_file = safe_file(run, 'request.json')
    if request_file.exists():
        if load_json(request_file) != request:
            raise AdapterError('Existing request differs from requested generation')
    else:
        write_json(request_file, request)
    capability = discover()
    if capability.get(GENERATOR) != 'unverified':
        raise RuntimeUnavailable(capability.get('reason', 'FreeCAD runtime unavailable'))
    for folder in ('native', 'exports', 'logs'):
        safe_file(run, folder).mkdir(exist_ok=True)
    metrics = {'generation': _run('generate', run), 'native_reopen': _run('reopen', run)}
    checks = load_json(run / 'native/reopen.json')
    generated = load_json(run / 'native/generation.json')
    if checks.get('status') != 'pass' or checks.get('fresh_process') is not True or generated.get('status') != 'pass':
        raise AdapterError('FreeCAD evidence is incomplete or failed')
    for name in outputs:
        path = safe_file(run, name)
        if not path.is_file() or path.stat().st_size == 0:
            raise AdapterError('FreeCAD did not produce a required artifact')
    return {'status': 'pass', 'artifacts': {'fcstd': 'native/model.FCStd',
            'step': 'exports/model.step', 'stl': 'exports/model.stl'},
            'native_checks': checks, 'native_generation': generated, 'metrics': metrics,
            'provenance': {'generator_id': GENERATOR, 'generator_version': '1',
                          'implementation': 'dot-forge-original-reviewed-native',
                          'runtime_kind': capability['runtime_kind'],
                          'freecad_version': capability['version'], 'occ_version': capability['occ_version'],
                          'python_version': capability['python_version'],
                          'binary_sha256': capability['binary_sha256'],
                          'native_module_sha256': capability['native_module_sha256'],
                          'native_library_sha256': capability['native_library_sha256'],
                          'script_sha256': sha256(SCRIPT)}}
