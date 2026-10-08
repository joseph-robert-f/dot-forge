"""Blender native fixtures and immutable upstream Lane A CLI integration."""
from __future__ import annotations
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from .base import AdapterError, RuntimeUnavailable
from ..execution import run_process
from ..common import write_json, load_json

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).with_name('native_scene.py')
VIEWS = ('front','side','back','top','oblique')


def lock():
    return json.loads((ROOT/'upstream.lock.json').read_text())


def verify_upstream(source):
    # The executable source directory must be the fetch helper's selected tree,
    # not a full checkout: PYTHONPATH can import any root package or extension.
    supplied=Path(source).absolute()
    if any(path.is_symlink() for path in (supplied,*supplied.parents)):
        raise AdapterError('Upstream source path contains a symlink')
    source=supplied.resolve()
    pin=lock()
    expected=set(pin['files'])
    allowed_dirs={parent.as_posix() for name in expected
                  for parent in Path(name).parents if parent != Path('.')}
    if not source.is_dir():raise AdapterError('Pinned upstream source is missing')
    actual=set()
    for path in source.rglob('*'):
        relative=path.relative_to(source).as_posix()
        if path.is_symlink():raise AdapterError('Upstream symlink rejected')
        if path.is_dir():
            if relative not in allowed_dirs:
                raise AdapterError('Unpinned upstream directory; import selected source with fetch-upstream.py')
        elif path.is_file():
            if relative not in expected:
                raise AdapterError('Unpinned upstream file; import selected source with fetch-upstream.py')
            actual.add(relative)
        else:raise AdapterError('Upstream special file rejected')
    if actual != expected:raise AdapterError('Pinned upstream source file set differs')
    for name,digest in pin['files'].items():
        path=source/name
        if any(parent.is_symlink() for parent in (path,*path.parents)):
            raise AdapterError('Pinned source path contains a symlink')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise AdapterError('Pinned upstream source mismatch: '+name)
    return {'status':'pass','commit':pin['commit'],'repository':pin['repository'],
            'files_verified':len(pin['files']),'license':pin['license']}


def _binary(blender=None):
    value=blender or os.environ.get('PRINTKIT_BLENDER') or shutil.which('blender')
    if not value:raise RuntimeUnavailable('Blender is not installed; no runtime was downloaded')
    path=Path(value).resolve()
    if not path.is_file() or not os.access(path,os.X_OK):raise RuntimeUnavailable('Blender executable unavailable')
    return path


def discover(blender=None, upstream=None):
    report={'backend':'blender','status':'unavailable','smoke_status':'not_run',
            'calibration-block':'unavailable','geometric-mascot':'unavailable','lane-a-character':'unavailable'}
    try:
        binary=_binary(blender)
        result=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=15,
                              env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        version=result.stdout.splitlines()[0].removeprefix('Blender ').strip()
        report.update(version=version,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                      status='unverified',executable=binary.name)
        for model in ('calibration-block','geometric-mascot'):
            report[model]='unverified' if version=='4.3.2' and platform.system()=='Linux' and platform.machine()=='x86_64' else 'incompatible'
        if version!='4.5.12 LTS':
            report['lane-a-character']='incompatible'
            report['lane_a_reason']='Pinned upstream CLI requires Blender 4.5.12 LTS; its guard is not patched'
        source=upstream or os.environ.get('PRINTKIT_UPSTREAM') or ROOT/'vendor/upstream'
        try:report['upstream']=verify_upstream(source)
        except (AdapterError,OSError) as exc:report['upstream']={'status':'unavailable','reason':str(exc)}
        if version=='4.5.12 LTS' and report['upstream']['status']=='pass':report['lane-a-character']='unverified'
    except (OSError,subprocess.SubprocessError,RuntimeUnavailable,IndexError) as exc:
        report['reason']=str(exc)
    return report


def _run(mode,run,blender=None):
    run=Path(run).resolve()
    binary=_binary(blender)
    return run_process([binary,'--background','--factory-startup','--offline-mode',
                        '--disable-autoexec','--threads','2','--python-exit-code','1',
                        '--python',SCRIPT,'--',mode,run],run,run/'logs'/f'{mode}.log',
                       env_extra={'BLENDER_USER_CONFIG':str(run/'.blender-config'),
                                  'BLENDER_USER_SCRIPTS':str(run/'.blender-scripts')})


def generate(request,run_dir,blender=None,upstream=None):
    run=Path(run_dir).resolve();run.mkdir(parents=True,exist_ok=True)
    model=request['generator_id']
    capability=discover(blender,upstream)
    if capability.get(model) not in ('unverified','available'):
        raise RuntimeUnavailable(capability.get('lane_a_reason') if model=='lane-a-character'
                                 else 'This generator requires tested Blender 4.3.2')
    if (run/'native/model.blend').exists() or (run/'exports/model.stl').exists():
        raise AdapterError('Refusing to overwrite existing generation artifacts')
    if (run/'request.json').exists():
        if load_json(run/'request.json') != request:raise AdapterError('Existing request differs from requested generation')
    else:
        write_json(run/'request.json',request)
    if model=='lane-a-character':
        return _lane_a(request,run,blender,upstream)
    if model not in ('calibration-block','geometric-mascot'):raise AdapterError('Unknown reviewed generator')
    metrics={'generation':_run('generate',run,blender),'native_reopen':_run('reopen',run,blender)}
    return {'status':'pass','artifacts':{'blend':'native/model.blend','stl':'exports/model.stl'},
            'native_checks':json.loads((run/'native/reopen.json').read_text()),'metrics':metrics,
            'native_generation':json.loads((run/'native/generation.json').read_text()),
            'provenance':{'generator_id':model,'generator_version':'1',
                          'implementation':'dot-forge-original-reviewed-native',
                          'script_sha256':hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
                          'blender_version':capability['version'],'binary_sha256':capability['binary_sha256']}}


def render(request,run_dir,blender=None):
    run=Path(run_dir).resolve()
    metrics=_run('preview',run,blender)
    for view in VIEWS:
        path=run/'previews'/f'{view}.png'
        if not path.is_file() or path.stat().st_size<100:raise AdapterError('Preview missing')
    return {'status':'pass','views':[f'previews/{v}.png' for v in VIEWS],'metrics':metrics,
            'subject':'exact exported printing STL','visual_completeness':'unknown'}


def smoke(run_dir,blender=None,upstream=None):
    request={'schema_version':'1','generator_id':'calibration-block','generator_version':'1',
      'backend':'blender','units':'mm','parameters':{'width_mm':20,'depth_mm':20,'height_mm':20},
      'dimensions_mm':[20,20,20],'tolerance_mm':.1,'allowed_components':1,'part_count':1,
      'export_formats':['stl','blend'],'render_profile':'five-view','validation_profile':'solid-single-part',
      'printer_profile':None}
    result=generate(request,run_dir,blender,upstream)
    result['preview']=render(request,run_dir,blender)
    from ..validation import validate_mesh
    result['validation']=validate_mesh(Path(run_dir)/'exports/model.stl',request)
    result['smoke_status']='pass' if result['validation']['geometry_state']=='geometry_validated' else 'fail'
    return result


def _lane_a(request,run,blender,upstream):
    source=Path(upstream or os.environ.get('PRINTKIT_UPSTREAM') or ROOT/'vendor/upstream').resolve()
    provenance=verify_upstream(source)
    upstream_request={'request_version':'build/v1','generator':'geometric-character@1.0.0',
      'spec':{'spec_version':'character/v1','name':'Dot Forge Facet','slug':'dot-forge-facet',
       'style':'geometric','height_mm':95,'pose':'standing',
       'palette':['#287B8E','#F4D58D'],'proportions':{'head_scale':1.2,'body_scale':.95,'limb_scale':.95},
       'material_preset':'matte','eye_preset':'round','components':['antenna-pair','chest-badge'],
       'base':{'preset':'round','width_mm':52,'depth_mm':52,'height_mm':5}},
      'output_profile':'complete-v1','render_profile':'diagnostic-v1','quality_profile':'geometry-v1'}
    request_path=run/'upstream-request.json';request_path.write_text(json.dumps(upstream_request)+'\n')
    env={'PYTHONPATH':str(source),'HBCB_BLENDER_BINARY':str(_binary(blender))}
    metrics={}
    for stage in ('build','verify'):
        metrics[stage]=run_process([sys.executable,'-S','-B','-m','builder_cli',stage,'--request',request_path,
                                   '--output',run/'upstream'],run,run/'logs'/f'upstream-{stage}.log',env_extra=env)
    for folder in ('native','exports'):(run/folder).mkdir(exist_ok=True)
    shutil.copy2(run/'upstream/model.blend',run/'native/model.blend')
    shutil.copy2(run/'upstream/model.stl',run/'exports/model.stl')
    return {'status':'pass','artifacts':{'blend':'native/model.blend','stl':'exports/model.stl'},
            'native_checks':{'status':'pass','method':'unmodified upstream CLI build and verify'},
            'upstream_findings':json.loads((run/'upstream/manifest.json').read_text()),
            'provenance':provenance,'metrics':metrics}
