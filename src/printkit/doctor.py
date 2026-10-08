"""Bounded Linux discovery and explicitly requested native smoke acceptance."""
from pathlib import Path
import os
import platform
import shutil
import sys
import tempfile
from .common import ForgeError, load_json
from .adapters import blender, freecad

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = {'calibration-block': ('blender', 'calibration-part'),
            'geometric-mascot': ('blender', 'geometric-mascot'),
            'freecad-stepped-block': ('freecad', 'freecad-stepped-part')}


def optional_inventory():
    """File discovery only: an installed medical-imaging app is not a print slicer."""
    candidates = []
    on_path = shutil.which('Slicer')
    if on_path:
        candidates.append(Path(on_path))
    root = Path('/opt/slicer')
    if root.is_dir():
        candidates.extend(sorted(root.glob('*/Slicer')))
    found = [str(path) for path in candidates if path.is_file() and os.access(path, os.X_OK)]
    return {'slicer': {'status': 'experimental-unverified' if found else 'unavailable',
            'required_for_default': False, 'detected_executables': sorted(set(found)),
            'detection_scope': 'Executable file discovery only; version and startup not verified',
            'workflow': 'No supported generator, print slicer or toolpath acceptance integration'}}


def _profile(report):
    compatible = (report['python_compatible'] and report['resources']['scratch_writable']
                  and report['platform'] == {'system': 'Linux', 'architecture': 'x86_64'}
                  and all(report[backend].get(model) in ('unverified', 'available')
                          for model, (backend, _) in EXAMPLES.items()))
    return {'name': 'dot-native', 'status': 'unverified' if compatible else 'blocked',
            'scope': 'Observed Linux baseline; each computer requires fresh smoke acceptance',
            'required_generators': list(EXAMPLES), 'smoke_status': 'not_run',
            'optional_profiles': ['lane-a-linux-x86_64', 'slicer-experimental'],
            'print_readiness': 'unknown'}


def _smoke_result(report, model, run):
    from .orchestrator import run_all
    from .bundle import create_bundle, verify_bundle
    backend, example = EXAMPLES[model]
    request = load_json(ROOT / 'examples' / example / 'request.json')
    result = run_all(request, run)
    passed = result['geometry_state'] == 'geometry_validated'
    bundle_status = 'not_run'
    if passed:
        create_bundle(run)
        bundle_status = verify_bundle(Path(run).with_suffix('.zip'))['status']
        passed = bundle_status == 'pass'
    report[backend][model] = 'available' if passed else 'incompatible'
    # A successful calibration smoke does not certify the separate mascot family.
    report[backend]['smoke_status'] = 'pass' if passed else 'fail'
    report[backend]['status'] = 'available' if passed else 'incompatible'
    return {'generator_id': model, 'status': 'pass' if passed else 'fail',
            'geometry_state': result['geometry_state'], 'overall_state': result['overall_state'],
            'bundle_integrity': bundle_status, 'run': str(run),
            'printing_and_manual_checks': 'unknown; not established by smoke'}


def doctor(smoke=None, backend='blender', all_smoke=None):
    if backend not in ('blender', 'freecad'):
        raise ForgeError('Unsupported backend')
    if smoke and all_smoke:
        raise ForgeError('Choose --smoke or --all-smoke, not both')
    with tempfile.TemporaryDirectory(prefix='printkit-doctor-') as directory:
        path=Path(directory)/'probe'
        path.write_text('ok')
        writable=path.read_text()=='ok'
    report={'schema_version':'1', 'selected_backend':backend,
            'python':platform.python_version(), 'python_compatible':sys.version_info>=(3,11),
            'platform':{'system':platform.system(),'architecture':platform.machine()},
            'resources':{'available_cpu_count':os.cpu_count(),'scratch_free_bytes':shutil.disk_usage(tempfile.gettempdir()).free,
                         'available_memory_bytes':None,'scratch_writable':writable},
            'blender':blender.discover(), 'freecad':freecad.discover(),
            'security':{'sandbox':False,'reviewed_generators_only':True},
            'full_architecture_mvp':'blocked: historical Lane A runtime acceptance remains outstanding; outside default profile',
            'print_readiness':'never established by doctor'}
    report['optional_tools'] = optional_inventory()
    report['default_profile'] = _profile(report)
    # FreeCAD's complete workflow also requires the native Blender preview profile.
    if report['freecad']['status'] == 'unverified' and report['blender'].get('calibration-block') not in ('unverified', 'available'):
        report['freecad']['status'] = 'incompatible'
        report['freecad']['reason'] = 'Native FreeCAD discovered, but full workflow requires the Blender 4.3.2 preview profile'
    if smoke:
        model = 'freecad-stepped-block' if backend == 'freecad' else 'calibration-block'
        result = _smoke_result(report, model, Path(smoke))
        report['smoke_geometry_state'] = result['geometry_state']
        report['smoke_result'] = result
    if all_smoke:
        directory = Path(all_smoke).absolute()
        if any(path.is_symlink() for path in (directory, *directory.parents)):
            raise ForgeError('All-smoke directory must not contain symlinks')
        directory.mkdir(parents=True, exist_ok=False)
        results = []
        for model in EXAMPLES:
            try:
                result = _smoke_result(report, model, directory / model)
            except (ForgeError, OSError, ValueError, KeyError, TypeError) as exc:
                result = {'generator_id': model, 'status': 'fail', 'reason': str(exc),
                          'geometry_state': 'blocked', 'bundle_integrity': 'not_run'}
                report[EXAMPLES[model][0]][model] = 'incompatible'
            results.append(result)
        passed = all(item['status'] == 'pass' for item in results)
        report['smoke_results'] = results
        report['default_profile']['status'] = 'available' if passed else 'blocked'
        report['default_profile']['smoke_status'] = 'pass' if passed else 'fail'
        for name in ('blender', 'freecad'):
            ok = all(item['status'] == 'pass' for item in results if EXAMPLES[item['generator_id']][0] == name)
            report[name]['status'] = 'available' if ok else 'incompatible'
            report[name]['smoke_status'] = 'pass' if ok else 'fail'
    return report
