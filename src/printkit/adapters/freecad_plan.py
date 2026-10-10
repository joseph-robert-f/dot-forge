"""FreeCAD adapter for v2 plans. Same tested runtime profile as the v1 adapter.

The helper runs the fixed interpreter in freecad_plan_scene.py. It reads the
already-validated plan from the run directory; nothing from the plan is
passed on the command line or as an environment value.
"""
from pathlib import Path
from .base import AdapterError, RuntimeUnavailable
from . import freecad
from ..common import ForgeError, load_json, sha256, safe_file
from ..execution import run_process


class PlanFailed(AdapterError):
    def __init__(self, message):
        ForgeError.__init__(self, message, 4, 'plan_step_failed')


SCRIPT = Path(__file__).with_name('freecad_plan_scene.py')
LINEAR_DEFLECTION_MM = 0.05  # Must match LINEAR_DEFLECTION in the helper.
OUTPUTS = ('native/model.FCStd', 'exports/model.step', 'exports/model.stl',
           'native/generation.json', 'native/reopen.json', 'native/measure.json')


def _run(mode, run):
    return run_process([freecad.PYTHON, '-I', '-B', SCRIPT, mode, run], run,
                       Path(run) / 'logs' / f'freecad-plan-{mode}.log', timeout=300)


def generate(run_dir, discover=None):
    run = Path(run_dir).resolve()
    for name in OUTPUTS + ('native/plan-failure.json', 'logs/freecad-plan-generate.log', 'logs/freecad-plan-reopen.log'):
        if safe_file(run, name).exists():
            raise AdapterError('Refusing to overwrite existing FreeCAD artifacts, logs or evidence')
    capability = (discover or freecad.discover)()
    if capability.get('status') != 'unverified':
        raise RuntimeUnavailable(capability.get('reason', 'FreeCAD runtime unavailable'))
    for folder in ('native', 'exports', 'logs'):
        safe_file(run, folder).mkdir(exist_ok=True)
    try:
        metrics = {'generation': _run('generate', run)}
    except ForgeError as exc:
        failure = run / 'native/plan-failure.json'
        if exc.finding == 'runtime_failed' and failure.is_file():
            detail = load_json(failure)
            raise PlanFailed(f"FreeCAD could not build {detail.get('op')} step {detail.get('step')!r}: "
                             f"{detail.get('error')}. Change the plan and build a new attempt.") from exc
        raise
    metrics['native_reopen'] = _run('reopen', run)
    generated = load_json(run / 'native/generation.json')
    reopened = load_json(run / 'native/reopen.json')
    if generated.get('status') != 'pass' or reopened.get('status') != 'pass' or reopened.get('fresh_process') is not True:
        raise AdapterError('FreeCAD plan evidence is incomplete or failed')
    for name in OUTPUTS:
        path = safe_file(run, name)
        if not path.is_file() or path.stat().st_size == 0:
            raise AdapterError('FreeCAD did not produce a required artifact')
    return {'status': 'pass', 'metrics': metrics,
            'artifacts': {'fcstd': 'native/model.FCStd', 'step': 'exports/model.step', 'stl': 'exports/model.stl'},
            'provenance': {'interpreter': 'dot-forge-plan-v1', 'runtime_kind': capability['runtime_kind'],
                           'freecad_version': capability['version'], 'occ_version': capability['occ_version'],
                           'python_version': capability['python_version'],
                           'binary_sha256': capability['binary_sha256'],
                           'native_module_sha256': capability['native_module_sha256'],
                           'native_library_sha256': capability['native_library_sha256'],
                           'script_sha256': sha256(SCRIPT)}}


def measure_step(run_dir, discover=None):
    """Measure input/part.step, a STEP made by any tool, with the same measurer as a build."""
    run = Path(run_dir).resolve()
    for name in ('native', 'exports', 'logs'):
        if safe_file(run, name).exists():
            raise AdapterError('Refusing to overwrite existing FreeCAD artifacts, logs or evidence')
    capability = (discover or freecad.discover)()
    if capability.get('status') != 'unverified':
        raise RuntimeUnavailable(capability.get('reason', 'FreeCAD runtime unavailable'))
    for folder in ('native', 'exports', 'logs'):
        safe_file(run, folder).mkdir()
    try:
        metrics = {'measure': _run('measure', run)}
    except ForgeError as exc:
        if exc.finding == 'runtime_failed':
            raise ForgeError('FreeCAD could not read or measure the STEP file. See logs/freecad-plan-measure.log.',
                             4, 'step_unreadable') from exc
        raise
    source = load_json(run / 'native/source.json')
    if source.get('status') != 'pass' or not (run / 'native/measure.json').is_file():
        raise AdapterError('FreeCAD measurement evidence is incomplete or failed')
    return {'status': 'pass', 'metrics': metrics, 'source': source,
            'provenance': {'measurer': 'dot-forge-plan-v1', 'runtime_kind': capability['runtime_kind'],
                           'freecad_version': capability['version'], 'occ_version': capability['occ_version'],
                           'python_version': capability['python_version'],
                           'binary_sha256': capability['binary_sha256'],
                           'native_module_sha256': capability['native_module_sha256'],
                           'native_library_sha256': capability['native_library_sha256'],
                           'script_sha256': sha256(SCRIPT)}}


def views(run_dir):
    """Five exact projections of the exported solid; the run must already hold a build."""
    run = Path(run_dir).resolve()
    if safe_file(run, 'views').exists():
        raise AdapterError('Refusing to overwrite existing preview views')
    safe_file(run, 'views').mkdir()
    _run('views', run)
    lines = load_json(run / 'views/lines.json')
    if lines.get('status') != 'pass' or set(lines.get('views', {})) != {'front', 'right', 'back', 'top', 'iso'}:
        raise AdapterError('FreeCAD did not produce all five preview views')
    return lines['views']


def raster(run_dir):
    """PNG of views/sheet.svg when FreeCAD's Qt can render it. False means SVG only."""
    run = Path(run_dir).resolve()
    try:
        _run('raster', run)
    except ForgeError:
        return False
    result = load_json(run / 'views/raster.json') if (run / 'views/raster.json').is_file() else {}
    return result.get('status') == 'pass' and (run / 'views/sheet.png').is_file()
